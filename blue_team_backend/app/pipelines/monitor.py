from __future__ import annotations

from typing import Any

from app.adapters import llm_client
from app.reporters.api_reporter import ApiReporter


async def run(job: dict[str, Any]) -> None:
    reporter = ApiReporter()
    note = await llm_client.complete("Summarize blue monitor tick")
    await reporter.post_threat_event(
        {
            "technique": "T1078",
            "technique_name": "Valid Accounts",
            "description": note[:500],
            "severity": "medium",
            "status": "new",
            "team": "blue",
            "source_tag": "blue-monitor",
            "source_ip": "0.0.0.0",
        }
    )
    await reporter.patch_job(job["job_id"], status="completed")
