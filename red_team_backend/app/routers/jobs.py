from __future__ import annotations

import asyncio
from typing import Any

from fastapi import APIRouter, BackgroundTasks
from pydantic import BaseModel, Field

from app.pipelines import deep_emulation, defensive_validation, surface_recon
from app.settings import get_settings

router = APIRouter()


class InternalJob(BaseModel):
    job_id: str
    team: str
    profile: str
    asset_ids: list[str] = Field(default_factory=list)
    assets: list[dict[str, Any]] = Field(default_factory=list)
    tools: list[str] | None = None
    callback_base_url: str | None = None
    demo_safe_mode: bool = True
    allowlist: list[str] = Field(default_factory=list)
    task_id: str | None = None
    target: str | None = None
    description: str | None = None
    patch_scope: str | None = None
    scans: list[dict[str, Any]] = Field(default_factory=list)


async def _run(job: dict[str, Any]) -> None:
    profile = job.get("profile") or "surface-recon"
    if profile in {"deep-emulation"}:
        await deep_emulation.run(job)
    elif profile in {"defensive-validation"}:
        await defensive_validation.run(job)
    elif profile in {"task-discovery"}:
        from app.pipelines import task_discovery

        await task_discovery.run(job)
    else:
        await surface_recon.run(job)


@router.post("/internal/jobs", status_code=202)
async def accept_job(body: InternalJob, background: BackgroundTasks):
    settings = get_settings()
    if body.allowlist:
        settings.target_allowlist = ",".join(body.allowlist)
    settings.demo_safe_mode = "1" if body.demo_safe_mode else "0"
    background.add_task(_run, body.model_dump())
    return {"accepted": True, "job_id": body.job_id}