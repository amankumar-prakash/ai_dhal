"""Tests for agent prompt loader and phase/tool prompt tree."""
from __future__ import annotations

import pytest

from app.agents.prompt_loader import (
    build_system_prompt,
    load_prompt,
    parse_prompt_sections,
    prompts_root,
    render_user_prompt,
)

REQUIRED_PROMPTS = [
    "_shared/lab_authorization",
    "_shared/output_contracts",
    "orchestrator/system",
    "orchestrator/decide",
    "phases/surface/phase_agent",
    "phases/surface/tools/server_health",
    "phases/surface/tools/nmap_scan",
    "phases/surface/tools/httpx_toolkit",
    "phases/content/phase_agent",
    "phases/content/tools/gobuster_scan",
    "phases/content/tools/feroxbuster_scan",
    "phases/content/tools/katana_crawl",
    "phases/content/tools/rest_api_probe",
    "phases/vuln/phase_agent",
    "phases/vuln/tools/nuclei_scan",
]


@pytest.mark.parametrize("rel", REQUIRED_PROMPTS)
def test_required_prompts_exist(rel: str) -> None:
    text = load_prompt(rel)
    assert text.strip()
    path = prompts_root() / f"{rel}.md"
    assert path.is_file()


def test_parse_sections_and_render_user() -> None:
    sections = parse_prompt_sections(load_prompt("phases/surface/tools/nmap_scan"))
    assert "system" in sections
    assert "user" in sections
    user = render_user_prompt(
        "phases/surface/tools/nmap_scan",
        scan_host="localhost",
        target="http://localhost:3000",
        prior_facts="{}",
        args_hint="{}",
    )
    assert "localhost" in user
    assert "{scan_host}" not in user


def test_build_system_prompt_includes_shared() -> None:
    system = build_system_prompt("phases/vuln/tools/nuclei_scan")
    assert "authorized" in system.lower() or "OWASP" in system
    assert "nuclei" in system.lower()
