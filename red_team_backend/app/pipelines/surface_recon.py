"""Surface recon pipeline with allowlist + guardrails."""
from __future__ import annotations

from typing import Any

from app.adapters import hexstrike_client
from app.guardrails import demo_blocks_profile, in_allowlist
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
            if not in_allowlist(host, settings.target_allowlist):
                await reporter.post_threat_event(
                    {
                        "technique": "blocked_by_guardrail",
                        "technique_name": "Out of scope target",
                        "description": f"Target {host} outside allowlist",
                        "severity": "info",
                        "status": "blocked_by_guardrail",
                        "team": "red",
                        "source_tag": "blocked_by_guardrail",
                        "asset_id": asset.get("id"),
                        "source_ip": "0.0.0.0",
                    }
                )
                continue

            if demo_blocks_profile(job.get("profile") or "", settings.demo_safe_mode):
                await reporter.post_threat_event(
                    {
                        "technique": "blocked_by_guardrail",
                        "technique_name": "Demo safe mode",
                        "description": "Destructive action blocked in demo mode",
                        "severity": "info",
                        "status": "blocked_by_guardrail",
                        "team": "red",
                        "source_tag": "blocked_by_guardrail",
                        "asset_id": asset.get("id"),
                        "source_ip": "0.0.0.0",
                    }
                )
                continue

            result = await hexstrike_client.run_recon(host, asset.get("ip_address"), settings)
            await reporter.post_tool_run(
                {
                    "job_id": job_id,
                    "team": "red",
                    "tool_name": result["tool"],
                    "command_summary": f"recon {host}",
                    "exit_code": 0,
                    "raw_output": result,
                }
            )
            for f in result["findings"]:
                await reporter.post_finding(
                    {
                        "title": f["title"],
                        "severity": f["severity"],
                        "team": "red",
                        "source_tool": f["source_tool"],
                        "evidence": f.get("evidence"),
                        "asset_id": asset.get("id"),
                        "status": "open",
                    }
                )
                await reporter.post_threat_event(
                    {
                        "technique": f.get("technique", "T1046"),
                        "technique_name": f.get("technique_name"),
                        "description": f["title"],
                        "severity": f["severity"],
                        "team": "red",
                        "source_tag": "red_team_backend",
                        "asset_id": asset.get("id"),
                        "source_ip": asset.get("ip_address") or "0.0.0.0",
                    }
                )
    except Exception as exc:
        await reporter.patch_job(job_id, status="failed", error=str(exc))
        raise

    await reporter.patch_job(job_id, status="completed")
