"""Phase agent — runs allowlisted tool agents sequentially and builds a rollup."""
from __future__ import annotations

import asyncio
import json
import logging
from typing import Any, Awaitable, Callable

from app.orchestration.artifact_store import JobArtifactStore, empty_facts, merge_facts
from app.orchestration.compress import build_phase_rollup, build_tool_summary
from app.orchestration.phases import PhaseSpec
from app.orchestration.tool_agent import run_tool_agent
from app.settings import WorkerSettings

log = logging.getLogger(__name__)

ProgressCb = Callable[[str, str, dict[str, Any] | None], Awaitable[None]]


async def run_phase(
    *,
    phase: PhaseSpec,
    job: dict[str, Any],
    target: str,
    scan_host: str,
    settings: WorkerSettings,
    store: JobArtifactStore,
    mcp_tools: list[Any],
    on_progress: ProgressCb | None = None,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Execute tools in phase order. Returns (reporter tool calls, rollup).

    Per-tool timeouts/failures are recorded and the phase continues to the next tool.
    Job-level CancelledError still aborts the remaining tools after artifacts are saved.
    """
    context = store.read_context()
    prior_facts = context.get("facts") or empty_facts()
    tools_used = int((context.get("budget") or {}).get("tools_used") or 0)
    max_tools_job = settings.max_tools_per_job
    max_tools_phase = settings.max_tools_per_phase

    if on_progress:
        await on_progress("thinking", f"Phase {phase.name}: starting", {"phase": phase.name})

    calls: list[dict[str, Any]] = []
    summaries: list[dict[str, Any]] = []
    tools_run: list[str] = []
    tools_skipped: list[str] = []
    phase_facts = empty_facts()

    for index, spec in enumerate(phase.tools):
        if index >= max_tools_phase or tools_used >= max_tools_job:
            tools_skipped.append(spec.logical_name)
            continue

        try:
            result = await run_tool_agent(
                spec=spec,
                phase=phase.name,
                job=job,
                target=target,
                scan_host=scan_host,
                settings=settings,
                store=store,
                mcp_tools=mcp_tools,
                prior_facts=prior_facts,
                on_progress=on_progress,
            )
        except asyncio.CancelledError:
            # Job wall cancel: tool_agent already wrote raw/summary — fold it into this phase.
            disk_summaries = [
                s
                for s in store.list_summaries()
                if s.get("tool_name") == spec.logical_name and s.get("phase") == phase.name
            ]
            if disk_summaries:
                summary = disk_summaries[-1]
                summaries.append(summary)
                tools_run.append(spec.logical_name)
                tools_used += 1
                calls.append(
                    {
                        "tool_name": spec.logical_name,
                        "args": {},
                        "output": {
                            "success": False,
                            "stdout": "",
                            "command_summary": "cancelled/timed out",
                            "timed_out": True,
                            "exit_code": 130,
                        },
                    }
                )
                prior_facts = merge_facts(prior_facts, summary.get("facts") or empty_facts())
                ctx = store.read_context()
                budget = dict(ctx.get("budget") or {})
                budget["tools_used"] = tools_used
                ctx["budget"] = budget
                ctx["facts"] = merge_facts(
                    ctx.get("facts") or empty_facts(), summary.get("facts") or empty_facts()
                )
                store.write_context(ctx)
            rollup = build_phase_rollup(
                job_id=store.job_id,
                phase=phase.name,
                tools_run=tools_run,
                tools_skipped=tools_skipped + [t.logical_name for t in phase.tools[index + 1 :]],
                summaries=summaries,
                settings=settings,
            )
            store.write_rollup(phase.name, rollup)
            raise
        except Exception as exc:  # noqa: BLE001
            log.exception("phase %s tool %s failed; continuing", phase.name, spec.logical_name)
            seq = store.next_seq()
            err = str(exc)[:500]
            timed_out = "timeout" in err.lower() or "timed out" in err.lower()
            store.write_raw(
                seq=seq,
                phase=phase.name,
                tool_name=spec.logical_name,
                args={},
                stdout="",
                stderr=err,
                success=False,
                exit_code=1,
                command_summary=err,
                timed_out=timed_out,
            )
            summary = build_tool_summary(
                job_id=store.job_id,
                seq=seq,
                phase=phase.name,
                tool_name=spec.logical_name,
                target=target,
                stdout=err,
                success=False,
                timed_out=timed_out,
                settings=settings,
            )
            store.write_summary(seq=seq, tool_name=spec.logical_name, payload=summary)
            result = {
                "tool_name": spec.logical_name,
                "args": {},
                "output": {
                    "success": False,
                    "stdout": err,
                    "command_summary": err,
                    "timed_out": timed_out,
                    "exit_code": 1,
                },
                "summary": summary,
                "skipped": False,
            }
            if on_progress:
                await on_progress(
                    "tool",
                    f"{spec.logical_name} failed — continuing next tool",
                    {"phase": phase.name, "error": err[:200]},
                )

        tools_used += 1
        if result.get("skipped"):
            tools_skipped.append(spec.logical_name)
        else:
            tools_run.append(spec.logical_name)

        calls.append(
            {
                "tool_name": result["tool_name"],
                "args": result.get("args") or {},
                "output": result.get("output") or {},
            }
        )
        summary = result.get("summary") or {}
        summaries.append(summary)
        phase_facts = merge_facts(phase_facts, summary.get("facts") or empty_facts())
        # Forward only compressed facts to the next tool agent (never raw stdout).
        prior_facts = merge_facts(prior_facts, summary.get("facts") or empty_facts())

        # Update budget in context early so cancellations still leave accurate counts.
        ctx = store.read_context()
        budget = dict(ctx.get("budget") or {})
        budget["tools_used"] = tools_used
        budget["max_tools"] = max_tools_job
        ctx["budget"] = budget
        # Merge facts into job context continuously so reports survive mid-job timeout.
        ctx["facts"] = merge_facts(ctx.get("facts") or empty_facts(), summary.get("facts") or empty_facts())
        store.write_context(ctx)

        if on_progress and (result.get("output") or {}).get("timed_out"):
            await on_progress(
                "status",
                f"{spec.logical_name}: EST time reached — continuing with next tool",
                {"phase": phase.name, "tool": spec.logical_name, "timed_out": True},
            )

    rollup = build_phase_rollup(
        job_id=store.job_id,
        phase=phase.name,
        tools_run=tools_run,
        tools_skipped=tools_skipped,
        summaries=summaries,
        settings=settings,
    )
    store.write_rollup(phase.name, rollup)

    if on_progress:
        await on_progress(
            "thinking",
            f"Phase {phase.name} rollup: {json.dumps(rollup.get('facts') or {})[:500]}",
            {"phase": phase.name},
        )

    return calls, rollup
