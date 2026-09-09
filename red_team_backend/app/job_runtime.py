"""In-process registry of running worker jobs so /internal/jobs/{id}/cancel can kill them."""
from __future__ import annotations

import asyncio
import logging
from typing import Any, Coroutine

log = logging.getLogger(__name__)

RUNNING_JOBS: dict[str, asyncio.Task[Any]] = {}
JOB_TARGETS: dict[str, str] = {}


class JobCancelled(Exception):
    """Raised when the platform job has been marked cancelled."""


def spawn(job_id: str, coro: Coroutine[Any, Any, None], target: str = "") -> asyncio.Task[Any]:
    async def _wrap() -> None:
        try:
            await coro
        finally:
            RUNNING_JOBS.pop(job_id, None)
            JOB_TARGETS.pop(job_id, None)

    task = asyncio.create_task(_wrap())
    RUNNING_JOBS[job_id] = task
    JOB_TARGETS[job_id] = target or ""
    return task


def cancel_running(job_id: str) -> bool:
    task = RUNNING_JOBS.get(job_id)
    if task is None or task.done():
        return False
    task.cancel()
    return True


def target_for(job_id: str) -> str:
    return JOB_TARGETS.get(job_id, "")
