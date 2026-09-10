"""Phase definitions and tool allowlists for hierarchical recon."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class ToolSpec:
    """Logical tool in a phase.

    `mcp_name` is the HexStrike MCP tool to bind (exactly one).
    `prompt_path` is relative to app/agents/prompts/ without .md.
    """

    logical_name: str
    mcp_name: str
    prompt_path: str
    default_args: dict[str, Any] | None = None


@dataclass(frozen=True)
class PhaseSpec:
    name: str
    prompt_path: str
    tools: tuple[ToolSpec, ...]


RECON_PHASES: tuple[PhaseSpec, ...] = (
    PhaseSpec(
        name="surface",
        prompt_path="phases/surface/phase_agent",
        tools=(
            ToolSpec(
                logical_name="server_health",
                mcp_name="server_health",
                prompt_path="phases/surface/tools/server_health",
            ),
            ToolSpec(
                logical_name="nmap_scan",
                mcp_name="nmap_scan",
                prompt_path="phases/surface/tools/nmap_scan",
                default_args={
                    "scan_type": "-sT -sV",
                    "additional_args": "-Pn -T4",
                },
            ),
            ToolSpec(
                logical_name="httpx_toolkit",
                mcp_name="execute_command",
                prompt_path="phases/surface/tools/httpx_toolkit",
            ),
        ),
    ),
    PhaseSpec(
        name="content",
        prompt_path="phases/content/phase_agent",
        tools=(
            ToolSpec(
                logical_name="gobuster_scan",
                mcp_name="gobuster_scan",
                prompt_path="phases/content/tools/gobuster_scan",
                default_args={"wordlist": "/usr/share/dirb/wordlists/common.txt"},
            ),
            ToolSpec(
                logical_name="katana_crawl",
                mcp_name="katana_crawl",
                prompt_path="phases/content/tools/katana_crawl",
                default_args={"depth": 2, "js_crawl": True, "form_extraction": True},
            ),
            ToolSpec(
                logical_name="rest_api_probe",
                mcp_name="execute_command",
                prompt_path="phases/content/tools/rest_api_probe",
            ),
        ),
    ),
    PhaseSpec(
        name="vuln",
        prompt_path="phases/vuln/phase_agent",
        tools=(
            ToolSpec(
                logical_name="nuclei_scan",
                mcp_name="nuclei_scan",
                prompt_path="phases/vuln/tools/nuclei_scan",
                default_args={
                    "tags": "exposure,token,config,misconfig,disclosure,panel,tech",
                },
            ),
        ),
    ),
)


def phase_by_name(name: str) -> PhaseSpec | None:
    for phase in RECON_PHASES:
        if phase.name == name:
            return phase
    return None


def default_phase_order() -> list[str]:
    return [p.name for p in RECON_PHASES]
