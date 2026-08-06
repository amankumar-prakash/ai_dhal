from __future__ import annotations

from typing import Any

from app.adapters import hexstrike_client
from app.reporters.api_reporter import ApiReporter
from app.settings import WorkerSettings, get_settings


async def run(job: dict[str, Any], settings: WorkerSettings | None = None) -> None:
    settings = settings or get_settings()
    reporter = ApiReporter(settings)
    job_id = job["job_id"]
    await reporter.patch_job(job_id, status="running")

    try:
        for asset in job.get("assets") or []:
            host = asset.get("hostname") or asset.get("name") or ""
            result = await hexstrike_client.run_vuln_scan(host, settings)
            await reporter.post_tool_run(
                {
                    "job_id": job_id,
                    "team": "blue",
                    "tool_name": result["tool"],
                    "command_summary": f"vuln-scan {host}",
                    "exit_code": 0,
                    "raw_output": result,
                }
            )

            for f in result["findings"]:
                finding = await reporter.post_finding(
                    {
                        "title": f["title"],
                        "severity": f["severity"],
                        "team": "blue",
                        "source_tool": f["source_tool"],
                        "evidence": f.get("evidence"),
                        "status": "open",
                        "asset_id": asset.get("id"),
                        "remediation": f.get("remediation") or "Review and remediate finding",
                    }
                )
                if finding and finding.get("id"):
                    await reporter.post_patch(
                        {
                            "finding_id": finding["id"],
                            "title": "Upgrade vulnerable package",
                            "playbook": "upgrade-package",
                            "asset_id": asset.get("id"),
                        }
                    )
    except Exception as exc:
        await reporter.patch_job(job_id, status="failed", error=str(exc))
        raise

    await reporter.patch_job(job_id, status="completed")
