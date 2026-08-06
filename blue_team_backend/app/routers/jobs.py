from __future__ import annotations

from typing import Any

from fastapi import APIRouter, BackgroundTasks
from pydantic import BaseModel, Field

from app.pipelines import monitor, patch, vuln_scan

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


async def _run(job: dict[str, Any]) -> None:
    profile = job.get("profile") or "vuln-scan"
    if profile in {"monitor"}:
        await monitor.run(job)
    elif profile in {"patch"}:
        await patch.apply(job)
    else:
        await vuln_scan.run(job)


@router.post("/internal/jobs", status_code=202)
async def accept_job(body: InternalJob, background: BackgroundTasks):
    background.add_task(_run, body.model_dump())
    return {"accepted": True, "job_id": body.job_id}
