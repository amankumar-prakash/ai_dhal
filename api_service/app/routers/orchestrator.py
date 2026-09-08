"""Orchestrator router — endpoints for AI Red-Team orchestration."""
from __future__ import annotations

import asyncio
import logging
from typing import Annotated

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query, status
from fastapi.responses import Response

from app.config import Settings, get_settings
from app.deps import Principal, require_jwt
from app.schemas.orchestrator import (
    EnhanceDescriptionRequest,
    EnhanceDescriptionResponse,
    ExecutePlanRequest,
    OrchestratorPlan,
    OrchestratorPlanRequest,
    OrchestratorReport,
    OrchestratorRunState,
    RunControlRequest,
    ToolRegistryResponse,
)
from app.services import orchestrator_enhancer, orchestrator_executor, orchestrator_planner, orchestrator_reporting
from app.services.tool_registry import get_tool_registry

log = logging.getLogger(__name__)

router = APIRouter(prefix="/orchestrator", tags=["orchestrator"])


# ─── Tool Registry ────────────────────────────────────────────────────────────

@router.get(
    "/tools",
    response_model=ToolRegistryResponse,
    summary="List all available attack tools",
)
async def list_tools(
    principal: Principal = Depends(require_jwt),
    settings: Settings = Depends(get_settings),
) -> ToolRegistryResponse:
    """Discover available red-team tools from HexStrike and the built-in catalog."""
    return await get_tool_registry()


# ─── Description Enhancer ────────────────────────────────────────────────────

@router.post(
    "/enhance",
    response_model=EnhanceDescriptionResponse,
    summary="Enhance raw target description into a structured profile",
)
async def enhance_description(
    req: EnhanceDescriptionRequest,
    principal: Principal = Depends(require_jwt),
    settings: Settings = Depends(get_settings),
) -> EnhanceDescriptionResponse:
    """
    Use LLM (or stub) to transform a free-form target description into
    a structured TargetProfile with attack surface notes, compliance flags,
    and port hints.
    """
    return await orchestrator_enhancer.enhance_description(req, settings)


# ─── Planner ─────────────────────────────────────────────────────────────────

@router.post(
    "/plan",
    response_model=OrchestratorPlan,
    summary="Generate a multi-stage attack plan",
)
async def generate_plan(
    req: OrchestratorPlanRequest,
    principal: Principal = Depends(require_jwt),
    settings: Settings = Depends(get_settings),
) -> OrchestratorPlan:
    """
    Use LLM (or stub) to produce a multi-phase engagement plan with tool steps
    derived from the structured target profile and available tool catalog.
    """
    return await orchestrator_planner.generate_plan(req, settings)


# ─── Execution ────────────────────────────────────────────────────────────────

@router.post(
    "/execute",
    response_model=OrchestratorRunState,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Launch orchestrated attack plan execution",
)
async def execute_plan(
    req: ExecutePlanRequest,
    background_tasks: BackgroundTasks,
    principal: Principal = Depends(require_jwt),
    settings: Settings = Depends(get_settings),
) -> OrchestratorRunState:
    """
    Create a new execution run and start processing stages asynchronously.
    Returns the initial run state immediately; poll /runs/{run_id} for updates.
    """
    run_state = orchestrator_executor.create_run(req)
    background_tasks.add_task(
        orchestrator_executor.run_plan_async,
        run_state.run_id,
        settings,
    )
    log.info(
        "Orchestrator run %s started (dry_run=%s, stages=%d)",
        run_state.run_id,
        req.dry_run,
        len(req.stages),
    )
    return run_state


@router.get(
    "/runs/{run_id}",
    response_model=OrchestratorRunState,
    summary="Get run state (poll for progress)",
)
async def get_run_state(
    run_id: str,
    principal: Principal = Depends(require_jwt),
) -> OrchestratorRunState:
    """Poll for the current state of an orchestrator run."""
    state = orchestrator_executor.get_run_state(run_id)
    if not state:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Run not found")
    return state


@router.post(
    "/runs/{run_id}/control",
    response_model=OrchestratorRunState,
    summary="Pause, resume, or abort a run",
)
async def control_run(
    run_id: str,
    req: RunControlRequest,
    principal: Principal = Depends(require_jwt),
) -> OrchestratorRunState:
    """Send a control command (pause | resume | abort) to an active run."""
    if not orchestrator_executor.control_run(run_id, req):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Run not found")
    state = orchestrator_executor.get_run_state(run_id)
    assert state is not None
    return state


# ─── Reporting ────────────────────────────────────────────────────────────────

@router.get(
    "/reports/{run_id}",
    summary="Download report in specified format (json | csv | markdown)",
)
async def get_report(
    run_id: str,
    format: Annotated[str, Query(description="Output format: json, csv, markdown")] = "json",
    principal: Principal = Depends(require_jwt),
) -> Response:
    """Export engagement report for a completed (or in-progress) run."""
    state = orchestrator_executor.get_run_state(run_id)
    if not state:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Run not found")

    findings = orchestrator_executor.get_findings(run_id)
    # We need target_profile / enhanced_description from the stored request
    entry = orchestrator_executor._RUNS.get(run_id)
    req: ExecutePlanRequest = entry["req"]

    report = orchestrator_reporting.build_report(
        run_state=state,
        target_profile=req.target_profile,
        enhanced_description=req.enhanced_description,
        findings=findings,
        plan_id=req.plan_id,
        title=f"Red-Team Engagement — {', '.join(req.target_profile.targets) or run_id}",
    )

    fmt = format.lower().strip()
    if fmt == "csv":
        content = orchestrator_reporting.export_csv(report)
        return Response(
            content=content,
            media_type="text/csv",
            headers={"Content-Disposition": f'attachment; filename="report-{run_id}.csv"'},
        )
    elif fmt in ("markdown", "md"):
        content = orchestrator_reporting.export_markdown(report)
        return Response(
            content=content,
            media_type="text/markdown",
            headers={"Content-Disposition": f'attachment; filename="report-{run_id}.md"'},
        )
    else:
        content = orchestrator_reporting.export_json(report)
        return Response(
            content=content,
            media_type="application/json",
            headers={"Content-Disposition": f'attachment; filename="report-{run_id}.json"'},
        )
