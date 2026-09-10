"""Hierarchical recon orchestrator — phases with per-tool agents + persisted context."""
from __future__ import annotations

import asyncio
import logging
import os
from typing import Any

from app.orchestration.artifact_store import JobArtifactStore, empty_facts
from app.orchestration.compress import update_job_context
from app.orchestration.phase_agent import run_phase
from app.orchestration.phases import RECON_PHASES, phase_by_name
from app.reporters.api_reporter import ApiReporter
from app.settings import WorkerSettings

log = logging.getLogger(__name__)


def _recon_host(target: str) -> str:
    return target.replace("http://", "").replace("https://", "").split("/")[0] or target


async def run_recon(
    job: dict[str, Any],
    target: str,
    settings: WorkerSettings,
    reporter: ApiReporter | None = None,
) -> list[dict[str, Any]]:
    """Drive surface → content → vuln with isolated tool agents.

    Returns the same list[dict] shape as task_discovery.extract_tool_calls so the
    existing reporting loop can post tool runs / findings unchanged.
    """
    from langchain_mcp_adapters.tools import load_mcp_tools

    from app.adapters.mcp_client import create_mcp_client

    settings.require_llm_for_live()
    if settings.openai_api_key:
        os.environ.setdefault("OPENAI_API_KEY", settings.openai_api_key)

    job_id = str(job["job_id"])
    scan_host = _recon_host(target)
    store = JobArtifactStore(settings.artifact_root, job_id)
    ctx = store.read_context()
    ctx["target"] = target
    ctx["scan_host"] = scan_host
    ctx["budget"] = {
        "tools_used": 0,
        "max_tools": settings.max_tools_per_job,
        "phase_loops_used": 0,
        "max_phase_loops": settings.max_phase_loops,
    }
    if not ctx.get("facts"):
        ctx["facts"] = empty_facts()
    store.write_context(ctx)

    async def on_progress(kind: str, message: str, meta: dict[str, Any] | None = None) -> None:
        if reporter is None:
            return
        from app.pipelines.task_discovery import _emit_progress, _ensure_not_cancelled

        await _ensure_not_cancelled(reporter, job_id)
        await _emit_progress(reporter, job_id, kind, message, meta)

    client = create_mcp_client(settings)

    async def _drive() -> list[dict[str, Any]]:
        all_calls: list[dict[str, Any]] = []
        async with client.session("hexstrike-ai") as session:
            mcp_tools = await load_mcp_tools(session)
            if not mcp_tools:
                raise RuntimeError("HexStrike MCP returned no tools")

            # Keep optional ferox available for gobuster fallback inside tool_agent.
            phase_queue = [p.name for p in RECON_PHASES]
            loops_used = 0

            while phase_queue:
                phase_name = phase_queue.pop(0)
                phase = phase_by_name(phase_name)
                if phase is None:
                    continue

                await on_progress("thinking", f"Orchestrator: run phase {phase_name}", None)
                calls, rollup = await run_phase(
                    phase=phase,
                    job=job,
                    target=target,
                    scan_host=scan_host,
                    settings=settings,
                    store=store,
                    mcp_tools=mcp_tools,
                    on_progress=on_progress,
                )
                all_calls.extend(calls)

                ctx = store.read_context()
                ctx = update_job_context(ctx, rollup=rollup, settings=settings)
                store.write_context(ctx)

                # Optional single loop: after vuln, re-enter content once if hints + budget.
                if (
                    phase_name == "vuln"
                    and loops_used < settings.max_phase_loops
                    and rollup.get("next_hints")
                    and int((ctx.get("budget") or {}).get("tools_used") or 0)
                    < settings.max_tools_per_job
                ):
                    # Conservative: do not auto-loop by default unless MAX_PHASE_LOOPS > 0
                    # and there are paths worth re-probing — still require unused budget.
                    if settings.max_phase_loops > 0 and (ctx.get("facts") or {}).get("paths"):
                        loops_used += 1
                        budget = dict(ctx.get("budget") or {})
                        budget["phase_loops_used"] = loops_used
                        ctx["budget"] = budget
                        ctx["loop_count"] = loops_used
                        store.write_context(ctx)
                        # Auto-loop disabled for predictability in v1 — leave hook documented.
                        log.info(
                            "loop budget available (%s) but auto-loop deferred in v1",
                            loops_used,
                        )

        return all_calls

    return await asyncio.wait_for(_drive(), timeout=settings.orchestration_timeout_seconds)
