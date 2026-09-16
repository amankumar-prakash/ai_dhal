"""Hierarchical recon orchestration package."""

from __future__ import annotations

from typing import Any, TYPE_CHECKING

if TYPE_CHECKING:
    from app.reporters.api_reporter import ApiReporter
    from app.settings import WorkerSettings


async def run_recon(
    job: dict[str, Any],
    target: str,
    settings: "WorkerSettings",
    reporter: "ApiReporter | None" = None,
) -> list[dict[str, Any]]:
    from app.orchestration.orchestrator import run_recon as _run_recon

    return await _run_recon(job, target, settings, reporter)


__all__ = ["run_recon"]
