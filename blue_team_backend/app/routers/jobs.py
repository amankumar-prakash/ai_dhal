from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter
from pydantic import BaseModel, Field

from app.adapters.hexstrike_client import terminate_processes_for_target
from app.job_runtime import cancel_running, spawn, target_for
from app.pipelines import monitor, patch, vuln_scan
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
    profile = job.get("profile") or "vuln-scan"
    if profile in {"monitor"}:
        await monitor.run(job)
    elif profile in {"patch"}:
        await patch.apply(job)
    else:
        await vuln_scan.run(job)


def _job_target(body: InternalJob) -> str:
    if body.target:
        return body.target
    if body.assets:
        first = body.assets[0]
        return str(first.get("hostname") or first.get("name") or "")
    return ""


@router.post("/internal/jobs", status_code=202)
async def accept_job(body: InternalJob):
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