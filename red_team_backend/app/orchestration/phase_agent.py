"""Phase agent — runs allowlisted tool agents sequentially and builds a rollup."""
from __future__ import annotations

import json
import logging
from typing import Any, Awaitable, Callable

from app.orchestration.artifact_store import JobArtifactStore, empty_facts, merge_facts
from app.orchestration.compress import build_phase_rollup
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
    """Execute tools in phase order. Returns (reporter tool calls, rollup)."""
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
        store.write_context(ctx)

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
