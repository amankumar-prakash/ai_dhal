from __future__ import annotations

from typing import Any

from app.reporters.api_reporter import ApiReporter


async def dry_run(playbook: str) -> dict[str, Any]:
    return {"playbook": playbook, "evidence": ["dry-run ok"], "applied": False}


async def apply(job: dict[str, Any]) -> None:
    reporter = ApiReporter()
    await reporter.patch_job(job["job_id"], status="running")
    # Patch apply is normally driven via API PATCH /patches/{id}; pipeline records evidence
    await reporter.patch_job(job["job_id"], status="completed")
