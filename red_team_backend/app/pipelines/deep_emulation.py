"""Deep emulation — uses LLM stub/client (+ CAI plan disabled)."""
from __future__ import annotations

from typing import Any

# from app.adapters import cai_client  # CAI disabled
from app.adapters import llm_client
from app.guardrails import demo_blocks_profile, in_allowlist
from app.pipelines import surface_recon
from app.reporters.api_reporter import ApiReporter
from app.settings import WorkerSettings, get_settings

_STAGES = ["recon", "initial_access", "execution", "persistence", "exfiltration"]


async def run(job: dict[str, Any], settings: WorkerSettings | None = None) -> None:
    settings = settings or get_settings()
    reporter = ApiReporter(settings)
    job_id = job["job_id"]

    await surface_recon.run(job, settings)

    try:
        profile = job.get("profile") or "deep-emulation"
        assets = job.get("assets") or []
        hosts = [a.get("hostname") or a.get("name") or "" for a in assets]
        in_scope_hosts = [h for h in hosts if in_allowlist(h, settings.target_allowlist)]

        if demo_blocks_profile(profile, settings.demo_safe_mode) or (hosts and not in_scope_hosts):
            await reporter.post_threat_event(
                {
                    "technique": "blocked_by_guardrail",
                    "technique_name": "Deep emulation blocked",
                    "description": "Deep-emulation blocked by demo safe mode or out-of-scope targets",
                    "severity": "info",
                    "status": "blocked_by_guardrail",
                    "team": "red",
                    "source_tag": "blocked_by_guardrail",
                    "source_ip": "0.0.0.0",
                }
            )
            return

        # plan = await cai_client.plan_chain(job, settings)  # CAI disabled
        plan = {"stages": list(_STAGES), "source": "plan-stub"}
        reasoning = await llm_client.complete(f"Summarize red deep-emulation for job {job_id}", settings)
        chain = await reporter.post_attack_chain(
            {
                "name": f"Deep chain {job_id[:8]}",
                "team": "red",
                "scan_id": None,
            }
        )
        if chain and chain.get("id"):
            for i, stage in enumerate(plan.get("stages") or []):
                await reporter.post_chain_step(
                    chain["id"],
                    {
                        "stage": stage,
                        "sequence": i + 1,
                        "title": f"{stage} ({plan.get('source', 'plan-stub')})",
                        "severity": "medium",
                    },
                )
        await reporter.post_threat_event(
            {
                "technique": "T1059",
                "technique_name": "Command and Scripting Interpreter",
                "description": reasoning[:500],
                "severity": "high",
                "team": "red",
                "source_tag": plan.get("source", "plan-stub"),
                "source_ip": "0.0.0.0",
                "raw_payload": {"plan": plan},
            }
        )
    except Exception as exc:
        await reporter.patch_job(job_id, status="failed", error=str(exc))
        raise
