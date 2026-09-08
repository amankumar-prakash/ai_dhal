"""Orchestrator Planner — generates a multi-phase attack plan from target profile + tool registry."""
from __future__ import annotations

import json
import logging
import textwrap
import uuid
from datetime import datetime

from app.config import Settings
from app.schemas.orchestrator import (
    OrchestratorPlan,
    OrchestratorPlanRequest,
    PlanStage,
    TargetProfile,
    ToolStep,
)
from app.services.tool_registry import get_tool_registry

log = logging.getLogger(__name__)


# ─── Stub planner ──────────────────────────────────────────────────────────

def _stub_plan(req: OrchestratorPlanRequest) -> OrchestratorPlan:
    """Deterministic 4-phase plan used in stub/offline mode."""
    plan_id = f"plan-{uuid.uuid4().hex[:8]}"
    targets = req.target_profile.targets or ["192.168.1.1"]
    target_str = targets[0]

    stages = [
        PlanStage(
            stage_id="s1",
            name="recon",
            label="Reconnaissance & Asset Discovery",
            description="Map the attack surface: open ports, services, web directories, SSL configuration.",
            depends_on=[],
            steps=[
                ToolStep(
                    step_id="s1-t1",
                    tool_id="nmap_scan",
                    tool_name="Nmap Port Scanner",
                    description=f"Full service/version scan of {target_str}",
                    params={"target": target_str, "ports": "1-65535", "flags": "-sV -O --script=banner"},
                    expected_output="List of open ports, service versions, OS fingerprint",
                ),
                ToolStep(
                    step_id="s1-t2",
                    tool_id="gobuster_dirbusting",
                    tool_name="Gobuster Directory Brute-Force",
                    description=f"Enumerate hidden paths on http://{target_str}",
                    params={"url": f"http://{target_str}", "extensions": "php,html,js,txt,bak"},
                    expected_output="Hidden directories and interesting files",
                ),
                ToolStep(
                    step_id="s1-t3",
                    tool_id="ssl_audit",
                    tool_name="SSL/TLS Audit",
                    description=f"Check TLS configuration and certificate validity on {target_str}",
                    params={"host": target_str, "port": 443},
                    expected_output="TLS version, cipher suites, certificate chain",
                ),
            ],
        ),
        PlanStage(
            stage_id="s2",
            name="vuln_scan",
            label="Vulnerability Scanning",
            description="Systematic vulnerability identification using web scanner and template engine.",
            depends_on=["s1"],
            steps=[
                ToolStep(
                    step_id="s2-t1",
                    tool_id="nikto_scan",
                    tool_name="Nikto Web Scanner",
                    description=f"Web vulnerability scan of http://{target_str}",
                    params={"target": f"http://{target_str}", "port": 80},
                    expected_output="Dangerous files, outdated components, misconfigurations",
                ),
                ToolStep(
                    step_id="s2-t2",
                    tool_id="nuclei_scan",
                    tool_name="Nuclei Template Scanner",
                    description=f"CVE and misconfiguration scan of {target_str}",
                    params={"target": f"http://{target_str}", "templates": "cves,misconfig,exposures"},
                    expected_output="Matched CVE templates and exposure findings",
                ),
            ],
        ),
        PlanStage(
            stage_id="s3",
            name="exploitation",
            label="Exploitation & Verification",
            description="Attempt to verify exploitability of identified vulnerabilities (authorized targets only).",
            depends_on=["s2"],
            steps=[
                ToolStep(
                    step_id="s3-t1",
                    tool_id="sqlmap_scan",
                    tool_name="SQLMap Injection Scanner",
                    description=f"SQL injection test on {target_str} login endpoint",
                    params={"url": f"http://{target_str}/login", "level": 2, "risk": 1},
                    expected_output="SQL injection vulnerability status and proof-of-concept",
                ),
                ToolStep(
                    step_id="s3-t2",
                    tool_id="hydra_bruteforce",
                    tool_name="Hydra Brute-Force",
                    description=f"SSH credential brute-force on {target_str}",
                    params={"target": target_str, "service": "ssh", "wordlist": "/usr/share/wordlists/rockyou.txt"},
                    expected_output="Valid credentials (if any)",
                ),
            ],
        ),
        PlanStage(
            stage_id="s4",
            name="post_exploitation",
            label="Post-Exploitation & AI Analysis",
            description="AI-guided post-exploitation analysis and comprehensive attack chain construction.",
            depends_on=["s3"],
            steps=[
                ToolStep(
                    step_id="s4-t1",
                    tool_id="cai_emulation",
                    tool_name="CAI Red-Team Emulation",
                    description="AI-guided post-exploitation objective pursuit and lateral movement analysis",
                    params={
                        "prompt": (
                            f"You have initial access to {target_str}. "
                            "Identify privilege escalation paths, lateral movement opportunities, "
                            "and sensitive data exposure. Report findings in structured format."
                        ),
                        "agent_type": "default",
                    },
                    expected_output="Privilege escalation paths, lateral movement routes, sensitive data exposure",
                ),
            ],
        ),
    ]

    # Trim to max_stages
    stages = stages[: req.max_stages]

    return OrchestratorPlan(
        plan_id=plan_id,
        title=f"Red-Team Engagement — {target_str}",
        target_profile=req.target_profile,
        enhanced_description=req.enhanced_description,
        stages=stages,
        created_at=datetime.utcnow(),
        model_used="stub",
    )


# ─── LLM-powered planner ─────────────────────────────────────────────────────

_PLAN_SYSTEM_PROMPT = textwrap.dedent("""
    You are an expert red-team engagement planner with deep knowledge of offensive security.
    Given a target profile and a list of available tools, generate a structured multi-phase
    attack plan.

    Respond ONLY with valid JSON matching this exact schema (no markdown, no extra keys):
    {
      "plan_id": "<uuid-style id>",
      "title": "<engagement title>",
      "stages": [
        {
          "stage_id": "<sN>",
          "name": "<recon|vuln_scan|exploitation|post_exploitation|custom>",
          "label": "<human label>",
          "description": "<what this stage does>",
          "depends_on": ["<stage_id>"],
          "steps": [
            {
              "step_id": "<sN-tM>",
              "tool_id": "<tool id from catalog>",
              "tool_name": "<tool name>",
              "description": "<what this step does>",
              "params": { "<param>": "<value>" },
              "expected_output": "<what analyst should see>",
              "enabled": true
            }
          ]
        }
      ]
    }

    Rules:
    - Only use tool_ids from the provided catalog.
    - Generate at most the requested number of stages.
    - Order stages logically: recon before vuln_scan before exploitation before post_exploitation.
    - Every step MUST have a tool_id that exists in the provided tool catalog.
    - Populate params with real, target-specific values.
""").strip()


async def generate_plan(
    req: OrchestratorPlanRequest,
    settings: Settings,
) -> OrchestratorPlan:
    """Generate a multi-phase engagement plan."""

    use_stub = (
        settings.orchestrator_stub
        or not settings.openai_api_key.strip()
    )
    if use_stub:
        log.info("Orchestrator planner: using STUB mode")
        return _stub_plan(req)

    try:
        from openai import AsyncOpenAI

        # Fetch tool catalog for LLM context
        registry = await get_tool_registry()
        allowed_tools = registry.tools
        if req.tool_ids:
            allowed_tools = [t for t in allowed_tools if t.id in req.tool_ids]

        catalog_summary = "\n".join(
            f"- {t.id} ({t.category}): {t.description}"
            for t in allowed_tools
        )

        user_msg = textwrap.dedent(f"""
            Enhanced Engagement Description:
            {req.enhanced_description}

            Target Profile:
            - Targets: {', '.join(req.target_profile.targets)}
            - Ports: {', '.join(req.target_profile.ports)}
            - Attack Surface: {req.target_profile.attack_surface_notes}
            - Compliance: {', '.join(req.target_profile.compliance_flags) or 'None'}
            - Out of Scope: {', '.join(req.target_profile.out_of_scope) or 'None'}

            Available Tools:
            {catalog_summary}

            Generate a plan with at most {req.max_stages} stages.
        """).strip()

        client = AsyncOpenAI(api_key=settings.openai_api_key)
        resp = await client.chat.completions.create(
            model=settings.openai_model,
            messages=[
                {"role": "system", "content": _PLAN_SYSTEM_PROMPT},
                {"role": "user", "content": user_msg},
            ],
            temperature=0.3,
            response_format={"type": "json_object"},
        )
        raw_json = resp.choices[0].message.content or "{}"
        data = json.loads(raw_json)

        stages = []
        for s in data.get("stages", []):
            steps = [
                ToolStep(
                    step_id=st.get("step_id", f"{s.get('stage_id', 's?')}-t?"),
                    tool_id=st.get("tool_id", "nmap_scan"),
                    tool_name=st.get("tool_name", "Unknown"),
                    description=st.get("description", ""),
                    params=st.get("params", {}),
                    expected_output=st.get("expected_output", ""),
                    enabled=st.get("enabled", True),
                )
                for st in s.get("steps", [])
            ]
            stages.append(
                PlanStage(
                    stage_id=s.get("stage_id", f"s{len(stages)+1}"),
                    name=s.get("name", "custom"),
                    label=s.get("label", "Stage"),
                    description=s.get("description", ""),
                    depends_on=s.get("depends_on", []),
                    steps=steps,
                )
            )

        return OrchestratorPlan(
            plan_id=data.get("plan_id", f"plan-{uuid.uuid4().hex[:8]}"),
            title=data.get("title", "Red-Team Engagement"),
            target_profile=req.target_profile,
            enhanced_description=req.enhanced_description,
            stages=stages[: req.max_stages],
            created_at=datetime.utcnow(),
            model_used=settings.openai_model,
            raw_llm_output=raw_json,
        )

    except Exception as exc:  # noqa: BLE001
        log.warning("LLM planner failed (%s), falling back to stub", exc)
        return _stub_plan(req)
