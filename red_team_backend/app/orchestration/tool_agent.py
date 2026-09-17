"""Single-tool agent — fresh chat, exactly one MCP tool bound."""
from __future__ import annotations

import asyncio
import json
import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Callable, Awaitable

from app.adapters.llm_model_factory import build_agent_model
from app.agents.prompt_loader import build_system_prompt, render_user_prompt
from app.orchestration.artifact_store import JobArtifactStore
from app.orchestration.compress import build_tool_summary, compress_for_llm, estimate_tokens
from app.orchestration.model_context import tool_schema_text
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


def _observation_text(result: Any) -> str:
    if result is None:
        return ""
    if isinstance(result, str):
        return result
    try:
        return json.dumps(result, default=str)
    except TypeError:
        return str(result)


@dataclass
class ToolCapture:
    """Filled when the wrapped MCP tool runs, before the observation re-enters the LLM."""

    seq: int | None = None
    args: dict[str, Any] | None = None
    parsed: dict[str, Any] | None = None
    raw_text: str = ""
    llm_compress: dict[str, Any] | None = None
    summary_written: bool = False
    extras: dict[str, Any] = field(default_factory=dict)


def wrap_mcp_tool(
    inner: Any,
    *,
    store: JobArtifactStore,
    tool_name: str,
    phase: str,
    settings: WorkerSettings,
    reserved_tokens: int,
    capture: ToolCapture,
    command_summary: str,
    started_at: str,
) -> Any:
    """Persist raw tool output, then return a budget-capped observation to the LLM."""
    from langchain_core.tools import StructuredTool

    async def _run(**kwargs: Any) -> str:
        payload = kwargs
        if hasattr(inner, "ainvoke"):
            result = await inner.ainvoke(payload)
        else:
            result = inner.invoke(payload)
        raw_text = _observation_text(result)
        parsed = parse_tool_output(result)
        stdout = parsed.get("stdout") or raw_text
        stderr = parsed.get("stderr") or ""
        timed_out = bool(parsed.get("timed_out"))
        partial = bool(parsed.get("partial_results"))
        success = bool(parsed.get("success"))
        exit_code = int(parsed.get("exit_code") if parsed.get("exit_code") is not None else 1)
        seq = store.next_seq()
        store.write_raw(
            seq=seq,
            phase=phase,
            tool_name=tool_name,
            args=payload if isinstance(payload, dict) else {"raw": payload},
            stdout=stdout,
            stderr=stderr,
            success=success and not timed_out,
            exit_code=exit_code,
            command_summary=command_summary or tool_name,
            started_at=started_at,
            finished_at=_now(),
            timed_out=timed_out,
            partial_results=partial or (timed_out and bool(stdout or stderr)),
        )
        compressed = compress_for_llm(raw_text, reserved_tokens=reserved_tokens, settings=settings)
        capture.seq = seq
        capture.args = payload if isinstance(payload, dict) else {"raw": payload}
        capture.parsed = {
            **parsed,
            "stdout": stdout,
            "stderr": stderr,
            "timed_out": timed_out,
            "partial_results": partial or (timed_out and bool(stdout or stderr)),
            "success": success and not timed_out,
            "exit_code": exit_code,
        }
        capture.raw_text = raw_text
        capture.llm_compress = compressed
        if compressed.get("method") != "passthrough":
            log.info(
                "compressed %s observation for LLM: method=%s origin=%s compressed=%s trigger=%s",
                tool_name,
                compressed.get("method"),
                compressed.get("origin_tokens"),
                compressed.get("compressed_tokens"),
                compressed.get("trigger"),
            )
        return compressed["compressed_prompt"]

    tool_kwargs: dict[str, Any] = {
        "name": getattr(inner, "name", None) or tool_name,
        "description": getattr(inner, "description", None) or tool_name,
        "coroutine": _run,
    }
    schema = getattr(inner, "args_schema", None)
    if schema is not None:
        tool_kwargs["args_schema"] = schema
    return StructuredTool.from_function(**tool_kwargs)


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
    seq: int | None = None,
    write_raw: bool = True,
) -> dict[str, Any]:
    if seq is None:
        seq = store.next_seq()
    if write_raw:
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


def _persist_from_capture(
    *,
    capture: ToolCapture,
    store: JobArtifactStore,
    phase: str,
    tool_name: str,
    target: str,
    args_hint: dict[str, Any],
    command_summary: str,
    settings: WorkerSettings,
    started_at: str,
) -> dict[str, Any]:
    parsed = capture.parsed or {}
    persisted = _persist_result(
        store=store,
        phase=phase,
        tool_name=tool_name,
        target=target,
        args=capture.args or args_hint,
        stdout=str(parsed.get("stdout") or capture.raw_text or ""),
        stderr=str(parsed.get("stderr") or ""),
        success=bool(parsed.get("success")),
        exit_code=int(parsed.get("exit_code") if parsed.get("exit_code") is not None else 1),
        command_summary=command_summary,
        settings=settings,
        started_at=started_at,
        timed_out=bool(parsed.get("timed_out")),
        partial_results=bool(parsed.get("partial_results")),
        seq=capture.seq,
        write_raw=False,
    )
    capture.summary_written = True
    if capture.llm_compress:
        persisted["summary"].setdefault("token_stats", {})
        persisted["llm_compress"] = {
            "method": capture.llm_compress.get("method"),
            "origin_tokens": capture.llm_compress.get("origin_tokens"),
            "compressed_tokens": capture.llm_compress.get("compressed_tokens"),
            "model": capture.llm_compress.get("model"),
            "window": capture.llm_compress.get("window"),
            "trigger": capture.llm_compress.get("trigger"),
        }
    return persisted


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

    facts_json = json.dumps(prior_facts, default=str)
    schema_text = tool_schema_text(mcp_tool)
    user_skeleton = render_user_prompt(
        spec.prompt_path,
        target=target,
        scan_host=scan_host,
        prior_facts="",
        args_hint=json.dumps(args_hint, default=str),
    )
    reserved_first = (
        estimate_tokens(system) + estimate_tokens(user_skeleton) + estimate_tokens(schema_text)
    )
    facts_compressed = compress_for_llm(facts_json, reserved_tokens=reserved_first, settings=settings)
    user = render_user_prompt(
        spec.prompt_path,
        target=target,
        scan_host=scan_host,
        prior_facts=facts_compressed["compressed_prompt"],
        args_hint=json.dumps(args_hint, default=str),
    )
    reserved_obs = estimate_tokens(system) + estimate_tokens(user) + estimate_tokens(schema_text)

    capture = ToolCapture()
    started = _now()
    command_summary = cmd or str(args_hint)[:500] or spec.logical_name
    bound_tool = wrap_mcp_tool(
        mcp_tool,
        store=store,
        tool_name=spec.logical_name,
        phase=phase,
        settings=settings,
        reserved_tokens=reserved_obs,
        capture=capture,
        command_summary=command_summary,
        started_at=started,
    )

    agent = create_agent(model, [bound_tool], system_prompt=system)
    result: Any
    try:
        result = await agent.ainvoke({"messages": [{"role": "user", "content": user}]})
    except asyncio.CancelledError:
        if capture.parsed is not None and not capture.summary_written:
            _persist_from_capture(
                capture=capture,
                store=store,
                phase=phase,
                tool_name=spec.logical_name,
                target=target,
                args_hint=args_hint,
                command_summary=command_summary,
                settings=settings,
                started_at=started,
            )
        else:
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
                command_summary=command_summary,
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

    if capture.parsed is not None:
        persisted = _persist_from_capture(
            capture=capture,
            store=store,
            phase=phase,
            tool_name=spec.logical_name,
            target=target,
            args_hint=args_hint,
            command_summary=command_summary,
            settings=settings,
            started_at=started,
        )
        timed_out = bool((capture.parsed or {}).get("timed_out"))
        if on_progress:
            suffix = " timed out (partial saved)" if timed_out else " finished"
            await on_progress(
                "tool",
                f"{spec.logical_name}{suffix}",
                {"phase": phase, "timed_out": timed_out, "seq": persisted["summary"].get("seq")},
            )
        return persisted

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
