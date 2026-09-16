"""Single-tool agent — fresh chat, exactly one MCP tool bound."""
from __future__ import annotations

import asyncio
import json
import logging
from datetime import datetime, timezone
from typing import Any, Callable, Awaitable

from app.adapters.llm_model_factory import build_agent_model
from app.agents.prompt_loader import build_system_prompt, render_user_prompt
from app.orchestration.artifact_store import JobArtifactStore
from app.orchestration.compress import build_tool_summary
from app.orchestration.phases import ToolSpec
from app.orchestration.tool_output import parse_tool_output
from app.settings import WorkerSettings

log = logging.getLogger(__name__)

ProgressCb = Callable[[str, str, dict[str, Any] | None], Awaitable[None]]


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _tool_by_name(tools: list[Any], name: str) -> Any | None:
    for tool in tools:
        if getattr(tool, "name", "") == name:
            return tool
    return None


def _command_for_logical(spec: ToolSpec, target: str) -> str | None:
    if spec.logical_name == "httpx_toolkit":
        return (
            f"httpx-toolkit -u {target} -sc -title -tech-detect -server -cl -silent"
        )
    if spec.logical_name == "rest_api_probe":
        paths = " ".join(
            f"{target}{p}"
            for p in ("/rest", "/api", "/api-docs", "/ftp", "/robots.txt", "/metrics")
        )
        return f"httpx-toolkit -u {paths} -sc -title -silent"
    return None


def _persist_result(
    *,
    store: JobArtifactStore,
    phase: str,
    tool_name: str,
    target: str,
    args: dict[str, Any],
    stdout: str,
    stderr: str,
    success: bool,
    exit_code: int,
    command_summary: str,
    settings: WorkerSettings,
    started_at: str,
    timed_out: bool = False,
    partial_results: bool = False,
) -> dict[str, Any]:
    seq = store.next_seq()
    store.write_raw(
        seq=seq,
        phase=phase,
        tool_name=tool_name,
        args=args if isinstance(args, dict) else {"raw": args},
        stdout=stdout,
        stderr=stderr,
        success=success and not timed_out,
        exit_code=exit_code,
        command_summary=command_summary,
        started_at=started_at,
        finished_at=_now(),
        timed_out=timed_out,
        partial_results=partial_results or (timed_out and bool(stdout or stderr)),
    )
    summary = build_tool_summary(
        job_id=store.job_id,
        seq=seq,
        phase=phase,
        tool_name=tool_name,
        target=target,
        stdout=stdout,
        stderr=stderr,
        success=success and not timed_out,
        timed_out=timed_out,
        settings=settings,
    )
    store.write_summary(seq=seq, tool_name=tool_name, payload=summary)
    return {
        "tool_name": tool_name,
        "args": args if isinstance(args, dict) else {},
        "output": {
            "success": success and not timed_out,
            "stdout": stdout,
            "stderr": stderr,
            "command_summary": command_summary,
            "timed_out": timed_out,
            "partial_results": partial_results or (timed_out and bool(stdout or stderr)),
            "exit_code": exit_code,
        },
        "summary": summary,
        "skipped": False,
    }


async def run_tool_agent(
    *,
    spec: ToolSpec,
    phase: str,
    job: dict[str, Any],
    target: str,
    scan_host: str,
    settings: WorkerSettings,
    store: JobArtifactStore,
    mcp_tools: list[Any],
    prior_facts: dict[str, Any],
    on_progress: ProgressCb | None = None,
) -> dict[str, Any]:
    """Run one tool agent; persist raw+summary; return reporter-shaped tool call."""
    from langchain.agents import create_agent

    mcp_tool = _tool_by_name(mcp_tools, spec.mcp_name)
    if mcp_tool is None:
        # Optional alternate: ferox if gobuster missing
        if spec.logical_name == "gobuster_scan":
            alt = _tool_by_name(mcp_tools, "feroxbuster_scan")
            if alt is not None:
                spec = ToolSpec(
                    logical_name="feroxbuster_scan",
                    mcp_name="feroxbuster_scan",
                    prompt_path="phases/content/tools/feroxbuster_scan",
                    default_args=spec.default_args,
                )
                mcp_tool = alt
        if mcp_tool is None:
            seq = store.next_seq()
            err = f"MCP tool {spec.mcp_name} not available"
            store.write_raw(
                seq=seq,
                phase=phase,
                tool_name=spec.logical_name,
                args={},
                stdout="",
                stderr=err,
                success=False,
                exit_code=1,
                command_summary=err,
            )
            summary = build_tool_summary(
                job_id=store.job_id,
                seq=seq,
                phase=phase,
                tool_name=spec.logical_name,
                target=target,
                stdout=err,
                success=False,
                settings=settings,
            )
            store.write_summary(seq=seq, tool_name=spec.logical_name, payload=summary)
            return {
                "tool_name": spec.logical_name,
                "args": {},
                "output": {"success": False, "stdout": err, "command_summary": err},
                "summary": summary,
                "skipped": True,
            }

    if on_progress:
        await on_progress("tool", f"Calling {spec.logical_name}…", {"phase": phase})

    settings.require_llm_for_live()
    model = build_agent_model(settings)
    system = build_system_prompt(spec.prompt_path)
    args_hint = dict(spec.default_args or {})
    cmd = _command_for_logical(spec, target)
    if cmd:
        args_hint["command"] = cmd
    if spec.logical_name == "nmap_scan":
        args_hint.setdefault("target", scan_host)
    user = render_user_prompt(
        spec.prompt_path,
        target=target,
        scan_host=scan_host,
        prior_facts=json.dumps(prior_facts, default=str)[:2000],
        args_hint=json.dumps(args_hint, default=str),
    )

    agent = create_agent(model, [mcp_tool], system_prompt=system)
    started = _now()
    result: Any
    try:
        result = await agent.ainvoke({"messages": [{"role": "user", "content": user}]})
    except asyncio.CancelledError:
        # Job/wall cancel — still persist a failure artifact, then re-raise.
        _persist_result(
            store=store,
            phase=phase,
            tool_name=spec.logical_name,
            target=target,
            args=args_hint,
            stdout="",
            stderr="Cancelled before tool completed",
            success=False,
            exit_code=130,
            command_summary=cmd or str(args_hint)[:500] or spec.logical_name,
            settings=settings,
            started_at=started,
            timed_out=True,
            partial_results=False,
        )
        if on_progress:
            await on_progress(
                "tool",
                f"{spec.logical_name} cancelled — partial report saved",
                {"phase": phase, "timed_out": True},
            )
        raise
    except Exception as exc:  # noqa: BLE001
        log.exception("tool agent %s failed", spec.logical_name)
        result = {"messages": [], "error": str(exc)}

    from app.pipelines.task_discovery import extract_tool_calls

    calls = extract_tool_calls(result) if isinstance(result, dict) else []
    args: dict[str, Any] = args_hint
    stdout = ""
    stderr = ""
    timed_out = False
    partial_results = False
    success = False
    exit_code = 1

    if calls:
        last = calls[-1]
        parsed = parse_tool_output(last.get("output"))
        stdout = parsed["stdout"]
        stderr = parsed["stderr"]
        timed_out = parsed["timed_out"]
        partial_results = parsed["partial_results"]
        success = parsed["success"]
        exit_code = parsed["exit_code"]
        args = last.get("args") or args_hint
    elif isinstance(result, dict) and result.get("error"):
        err = str(result["error"])
        parsed = parse_tool_output(err)
        stdout = parsed["stdout"]
        stderr = parsed["stderr"] or err
        timed_out = parsed["timed_out"]
        partial_results = parsed["partial_results"]
        success = False
        exit_code = parsed["exit_code"]
    else:
        messages = result.get("messages") if isinstance(result, dict) else []
        if messages:
            content = getattr(messages[-1], "content", None) or ""
            parsed = parse_tool_output(content)
            stdout = parsed["stdout"][:2000]
            stderr = parsed["stderr"]
            timed_out = parsed["timed_out"]
            partial_results = parsed["partial_results"]
            exit_code = parsed["exit_code"]
        success = False
        if not timed_out:
            exit_code = 1

    command_summary = cmd or str(args)[:500] or spec.logical_name
    persisted = _persist_result(
        store=store,
        phase=phase,
        tool_name=spec.logical_name,
        target=target,
        args=args if isinstance(args, dict) else {"raw": args},
        stdout=stdout,
        stderr=stderr,
        success=success,
        exit_code=exit_code,
        command_summary=command_summary,
        settings=settings,
        started_at=started,
        timed_out=timed_out,
        partial_results=partial_results,
    )

    if on_progress:
        suffix = " timed out (partial saved)" if timed_out else " finished"
        await on_progress(
            "tool",
            f"{spec.logical_name}{suffix}",
            {"phase": phase, "timed_out": timed_out, "seq": persisted["summary"].get("seq")},
        )

    return persisted
