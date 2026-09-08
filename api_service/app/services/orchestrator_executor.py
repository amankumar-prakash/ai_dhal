"""Orchestrator Executor — manages stateful execution of attack plan stages and steps."""
from __future__ import annotations

import asyncio
import logging
import uuid
from datetime import datetime
from typing import Any

import httpx

from app.config import Settings
from app.schemas.orchestrator import (
    ExecutePlanRequest,
    FindingSummary,
    OrchestratorRunState,
    PlanStage,
    RunControlRequest,
    Severity,
    StageExecutionLog,
    StepExecutionLog,
)

log = logging.getLogger(__name__)

# ─── In-memory run registry ──────────────────────────────────────────────────
# For production, swap with a DB-backed store.

_RUNS: dict[str, dict[str, Any]] = {}
_FINDINGS: dict[str, list[FindingSummary]] = {}  # keyed by run_id


# ─── Helpers ─────────────────────────────────────────────────────────────────

def _now() -> datetime:
    return datetime.utcnow()


def _infer_severity(stdout: str, tool_id: str) -> Severity:
    """Very basic severity inference from tool output keywords."""
    lower = stdout.lower()
    if any(k in lower for k in ["root", "critical", "rce", "command execution", "unauthenticated"]):
        return "critical"
    if any(k in lower for k in ["high", "exploit", "sqli", "injection", "password found"]):
        return "high"
    if any(k in lower for k in ["medium", "xss", "csrf", "open port", "misconfiguration"]):
        return "medium"
    if any(k in lower for k in ["low", "info disclosure", "banner"]):
        return "low"
    return "info"


async def _execute_step_dry_run(step_id: str, tool_id: str) -> tuple[str, int]:
    """Simulate a tool execution in dry-run mode."""
    await asyncio.sleep(0.3)
    return f"[DRY-RUN] Would execute {tool_id} with step {step_id}. No actual commands sent.", 0


async def _dispatch_to_worker(
    tool_id: str,
    params: dict[str, Any],
    settings: Settings,
) -> tuple[str, int]:
    """Dispatch a tool run to the red_team_backend worker."""
    worker_url = settings.red_worker_url.rstrip("/")
    payload = {
        "tool": tool_id,
        "params": params,
    }
    try:
        async with httpx.AsyncClient(timeout=120.0) as client:
            resp = await client.post(f"{worker_url}/internal/run-tool", json=payload)
            if resp.status_code == 200:
                data = resp.json()
                return data.get("output", data.get("stdout", str(data))), 0
            else:
                return f"Worker returned HTTP {resp.status_code}: {resp.text}", 1
    except Exception as exc:  # noqa: BLE001
        log.warning("Worker dispatch failed for tool %s: %s", tool_id, exc)
        return f"[DISPATCH ERROR] {exc}", 1


# ─── Run lifecycle ────────────────────────────────────────────────────────────

def create_run(req: ExecutePlanRequest) -> OrchestratorRunState:
    run_id = f"run-{uuid.uuid4().hex[:10]}"
    stage_logs = [
        StageExecutionLog(stage_id=s.stage_id, label=s.label, status="pending")
        for s in req.stages
    ]
    state = OrchestratorRunState(
        run_id=run_id,
        plan_id=req.plan_id,
        status="pending",
        stages=stage_logs,
        dry_run=req.dry_run,
    )
    _RUNS[run_id] = {
        "state": state,
        "req": req,
        "control": "run",  # run | pause | abort
    }
    _FINDINGS[run_id] = []
    return state


def get_run_state(run_id: str) -> OrchestratorRunState | None:
    entry = _RUNS.get(run_id)
    return entry["state"] if entry else None


def control_run(run_id: str, req: RunControlRequest) -> bool:
    entry = _RUNS.get(run_id)
    if not entry:
        return False
    entry["control"] = req.action
    if req.action == "abort":
        entry["state"].status = "aborted"
    elif req.action == "pause":
        entry["state"].status = "paused"
    elif req.action == "resume":
        if entry["state"].status == "paused":
            entry["state"].status = "executing"
    return True


def get_findings(run_id: str) -> list[FindingSummary]:
    return _FINDINGS.get(run_id, [])


# ─── Async background execution ───────────────────────────────────────────────

async def run_plan_async(run_id: str, settings: Settings) -> None:
    """Background task: execute all enabled stages and steps sequentially."""
    entry = _RUNS.get(run_id)
    if not entry:
        log.error("run_plan_async: unknown run_id %s", run_id)
        return

    state: OrchestratorRunState = entry["state"]
    req: ExecutePlanRequest = entry["req"]
    state.status = "executing"
    state.started_at = _now()

    # Build a map from stage_id to PlanStage
    plan_stages: dict[str, PlanStage] = {s.stage_id: s for s in req.stages}

    for stage_log in state.stages:
        # Check for abort / pause
        while entry["control"] == "pause":
            await asyncio.sleep(1.0)
            if entry["control"] == "abort":
                break
        if entry["control"] == "abort":
            state.status = "aborted"
            state.finished_at = _now()
            return

        plan_stage = plan_stages.get(stage_log.stage_id)
        if not plan_stage:
            stage_log.status = "skipped"
            continue

        stage_log.status = "running"
        stage_log.started_at = _now()
        state.current_stage_id = stage_log.stage_id

        enabled_steps = [s for s in plan_stage.steps if s.enabled]
        for step in enabled_steps:
            step_log = StepExecutionLog(
                step_id=step.step_id,
                tool_id=step.tool_id,
                tool_name=step.tool_name,
                status="running",
                started_at=_now(),
                params_used=step.params,
            )
            stage_log.steps.append(step_log)

            try:
                if req.dry_run:
                    stdout, exit_code = await _execute_step_dry_run(step.step_id, step.tool_id)
                else:
                    stdout, exit_code = await _dispatch_to_worker(
                        step.tool_id, step.params, settings
                    )

                step_log.stdout = stdout
                step_log.exit_code = exit_code
                step_log.status = "completed" if exit_code == 0 else "failed"
                step_log.finished_at = _now()

                # Extract finding from output
                if stdout and exit_code == 0:
                    severity = _infer_severity(stdout, step.tool_id)
                    if severity in ("critical", "high", "medium"):
                        finding = FindingSummary(
                            id=f"find-{uuid.uuid4().hex[:8]}",
                            run_id=run_id,
                            stage_id=stage_log.stage_id,
                            step_id=step.step_id,
                            tool_name=step.tool_name,
                            title=f"{step.tool_name} finding on {req.target_profile.targets[0] if req.target_profile.targets else 'target'}",
                            severity=severity,
                            description=stdout[:500],
                            evidence=stdout[:1000],
                        )
                        _FINDINGS[run_id].append(finding)

            except Exception as exc:  # noqa: BLE001
                step_log.stderr = str(exc)
                step_log.status = "failed"
                step_log.exit_code = 1
                step_log.finished_at = _now()
                log.error("Step %s failed: %s", step.step_id, exc)

        # Stage complete
        failed_count = sum(1 for s in stage_log.steps if s.status == "failed")
        stage_log.status = "failed" if failed_count == len(stage_log.steps) and stage_log.steps else "completed"
        stage_log.finished_at = _now()

    state.status = "finished"
    state.finished_at = _now()
    state.current_stage_id = None
    log.info("Run %s finished. Findings: %d", run_id, len(_FINDINGS.get(run_id, [])))
