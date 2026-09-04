from __future__ import annotations

import asyncio
import logging
from typing import Any

from fastapi import APIRouter
from pydantic import BaseModel, Field

from app.adapters.hexstrike_client import terminate_processes_for_target
from app.job_runtime import cancel_running, spawn, target_for
from app.pipelines import deep_emulation, defensive_validation, surface_recon
from app.settings import get_settings

log = logging.getLogger(__name__)

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


def _job_target(body: InternalJob) -> str:
    if body.target:
        return body.target
    if body.assets:
        first = body.assets[0]
        return str(first.get("hostname") or first.get("name") or "")
    return ""


@router.post("/internal/jobs", status_code=202)
async def accept_job(body: InternalJob):
    settings = get_settings()
    if body.allowlist:
        settings.target_allowlist = ",".join(body.allowlist)
    settings.demo_safe_mode = "1" if body.demo_safe_mode else "0"
    spawn(body.job_id, _run(body.model_dump()), target=_job_target(body))
    return {"accepted": True, "job_id": body.job_id}


@router.post("/internal/jobs/{job_id}/cancel")
async def cancel_job(job_id: str):
    target = target_for(job_id)
    cancelled = cancel_running(job_id)
    killed = 0
    try:
        killed = await terminate_processes_for_target(target, get_settings())
    except Exception as exc:  # noqa: BLE001
        log.warning("hexstrike terminate failed: %s", exc)
    return {"cancelled": cancelled, "terminated_processes": killed, "job_id": job_id}