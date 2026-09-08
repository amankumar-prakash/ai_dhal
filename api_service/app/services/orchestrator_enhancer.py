"""Orchestrator Enhancer — refines raw target input into a structured target profile."""
from __future__ import annotations

import json
import logging
import textwrap
from datetime import datetime

from app.config import Settings
from app.schemas.orchestrator import (
    EnhanceDescriptionRequest,
    EnhanceDescriptionResponse,
    TargetProfile,
)

log = logging.getLogger(__name__)

# ─── Stub response ───────────────────────────────────────────────────────────

def _stub_enhance(req: EnhanceDescriptionRequest) -> EnhanceDescriptionResponse:
    """Deterministic stub used when ORCHESTRATOR_STUB=1 or no API key available."""
    targets = []
    raw = req.raw_input.lower()
    # Crude extraction of IPs / hostnames from raw input for stub
    import re
    ips = re.findall(r"\b(?:\d{1,3}\.){3}\d{1,3}(?:/\d+)?\b", req.raw_input)
    hosts = re.findall(r"\b(?:[a-zA-Z0-9-]+\.)+[a-zA-Z]{2,}\b", req.raw_input)
    targets = list(dict.fromkeys(ips + hosts)) or ["192.168.1.1"]

    compliance = []
    if any(k in raw for k in ["owasp", "web"]):
        compliance.append("OWASP Top 10")
    if any(k in raw for k in ["pci", "card"]):
        compliance.append("PCI-DSS")

    return EnhanceDescriptionResponse(
        enhanced_description=(
            f"Authorized red-team engagement against {', '.join(targets)}. "
            f"Scope: {req.scope_notes or 'full application stack'}. "
            f"Objectives: enumerate open services, identify vulnerabilities, "
            f"verify exploitability, and recommend remediations."
        ),
        target_profile=TargetProfile(
            targets=targets,
            ports=["80", "443", "22", "8080", "8443"],
            attack_surface_notes="Web application and network services",
            compliance_flags=compliance,
            out_of_scope=[],
        ),
        suggested_phase_count=4,
        model_used="stub",
    )


# ─── LLM-powered enhancement ─────────────────────────────────────────────────

_SYSTEM_PROMPT = textwrap.dedent("""
    You are an expert red-team engagement planner.
    Given raw target information and optional scope notes, produce a structured JSON
    object describing the engagement target profile and an enhanced engagement description.

    Respond ONLY with valid JSON matching this exact schema (no markdown, no explanation):
    {
      "enhanced_description": "<concise professional engagement description>",
      "targets": ["<ip or hostname>", ...],
      "ports": ["<port/range>", ...],
      "attack_surface_notes": "<brief notes on attack surface>",
      "compliance_flags": ["<flag>", ...],
      "out_of_scope": ["<items>", ...],
      "suggested_phase_count": <integer 1-8>
    }
""").strip()


async def enhance_description(
    req: EnhanceDescriptionRequest,
    settings: Settings,
) -> EnhanceDescriptionResponse:
    """Enhance target description using LLM or stub."""

    use_stub = (
        settings.orchestrator_stub
        or not settings.openai_api_key.strip()
    )
    if use_stub:
        log.info("Orchestrator enhancer: using STUB mode")
        return _stub_enhance(req)

    try:
        from openai import AsyncOpenAI  # lazy import

        client = AsyncOpenAI(api_key=settings.openai_api_key)
        user_msg = f"Raw Input: {req.raw_input}"
        if req.scope_notes:
            user_msg += f"\nScope Notes: {req.scope_notes}"

        resp = await client.chat.completions.create(
            model=settings.openai_model,
            messages=[
                {"role": "system", "content": _SYSTEM_PROMPT},
                {"role": "user", "content": user_msg},
            ],
            temperature=0.2,
            response_format={"type": "json_object"},
        )
        raw_json = resp.choices[0].message.content or "{}"
        data = json.loads(raw_json)

        return EnhanceDescriptionResponse(
            enhanced_description=data.get("enhanced_description", req.raw_input),
            target_profile=TargetProfile(
                targets=data.get("targets", []),
                ports=data.get("ports", []),
                attack_surface_notes=data.get("attack_surface_notes", ""),
                compliance_flags=data.get("compliance_flags", []),
                out_of_scope=data.get("out_of_scope", []),
            ),
            suggested_phase_count=int(data.get("suggested_phase_count", 4)),
            model_used=settings.openai_model,
        )

    except Exception as exc:  # noqa: BLE001
        log.warning("LLM enhancement failed (%s), falling back to stub", exc)
        return _stub_enhance(req)
