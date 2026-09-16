"""Single-tool agent — fresh chat, exactly one MCP tool bound."""
from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from typing import Any, Callable, Awaitable

from app.adapters.llm_model_factory import build_agent_model
from app.agents.prompt_loader import build_system_prompt, render_user_prompt
from app.orchestration.artifact_store import JobArtifactStore
from app.orchestration.compress import build_tool_summary
from app.orchestration.phases import ToolSpec
from app.settings import WorkerSettings

log = logging.getLogger(__name__)

ProgressCb = Callable[[str, str, dict[str, Any] | None], Awaitable[None]]


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _stdout_from_output(output: Any) -> str:
    if isinstance(output, dict):
        return str(output.get("stdout") or output.get("content") or json.dumps(output))
    text = str(output or "")
    try:
        data = json.loads(text)
        if isinstance(data, dict):
            return str(data.get("stdout") or text)
    except (json.JSONDecodeError, TypeError):
        pass
    return text


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
    try:
        result = await agent.ainvoke({"messages": [{"role": "user", "content": user}]})
    except Exception as exc:  # noqa: BLE001
        log.exception("tool agent %s failed", spec.logical_name)
        result = {"messages": [], "error": str(exc)}

    from app.pipelines.task_discovery import extract_tool_calls

    calls = extract_tool_calls(result) if isinstance(result, dict) else []
    stdout = ""
    args: dict[str, Any] = args_hint
    success = False
    if calls:
        last = calls[-1]
        stdout = _stdout_from_output(last.get("output"))
        args = last.get("args") or args_hint
        success = True
    elif isinstance(result, dict) and result.get("error"):
        stdout = str(result["error"])
    else:
        # Agent may have answered without tool call — treat as failure
        messages = result.get("messages") if isinstance(result, dict) else []
        if messages:
            content = getattr(messages[-1], "content", None) or ""
            stdout = str(content)[:2000]
        success = False

    command_summary = cmd or str(args)[:500] or spec.logical_name
    seq = store.next_seq()
    store.write_raw(
        seq=seq,
        phase=phase,
        tool_name=spec.logical_name,
        args=args if isinstance(args, dict) else {"raw": args},
        stdout=stdout,
        success=success,
        exit_code=0 if success else 1,
        command_summary=command_summary,
        started_at=started,
        finished_at=_now(),
    )
    summary = build_tool_summary(
        job_id=store.job_id,
        seq=seq,
        phase=phase,
        tool_name=spec.logical_name,
        target=target,
        stdout=stdout,
        success=success,
        settings=settings,
    )
    store.write_summary(seq=seq, tool_name=spec.logical_name, payload=summary)

    if on_progress:
        await on_progress("tool", f"{spec.logical_name} finished", {"phase": phase, "seq": seq})

    return {
        "tool_name": spec.logical_name,
        "args": args if isinstance(args, dict) else {},
        "output": {
            "success": success,
            "stdout": stdout,
            "command_summary": command_summary,
        },
        "summary": summary,
        "skipped": False,
    }
