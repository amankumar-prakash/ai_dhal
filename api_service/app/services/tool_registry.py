"""Tool Registry — discovers available red-team tools from HexStrike and a static catalog."""
from __future__ import annotations

import logging
from datetime import datetime

import httpx

from app.schemas.orchestrator import ToolDefinition, ToolParam, ToolRegistryResponse

log = logging.getLogger(__name__)

# ─── Static fallback catalog ──────────────────────────────────────────────────
# Used when HexStrike server is unreachable or returns no discovery data.

_STATIC_CATALOG: list[ToolDefinition] = [
    ToolDefinition(
        id="nmap_scan",
        name="Nmap Port Scanner",
        category="recon",
        description="Discover open ports, services, and OS fingerprints on target hosts.",
        source="hexstrike",
        params=[
            ToolParam(name="target", type="string", required=True, description="IP/hostname/CIDR range"),
            ToolParam(name="ports", type="string", required=False, default="1-1000", description="Port range"),
            ToolParam(name="flags", type="string", required=False, default="-sV -O", description="Nmap flags"),
        ],
    ),
    ToolDefinition(
        id="nikto_scan",
        name="Nikto Web Scanner",
        category="vuln_scan",
        description="Scan web servers for dangerous files, outdated software, and misconfigurations.",
        source="hexstrike",
        params=[
            ToolParam(name="target", type="string", required=True, description="HTTP/HTTPS URL"),
            ToolParam(name="port", type="integer", required=False, default=80, description="Port number"),
        ],
    ),
    ToolDefinition(
        id="sqlmap_scan",
        name="SQLMap Injection Scanner",
        category="exploitation",
        description="Detect and exploit SQL injection vulnerabilities in web applications.",
        source="hexstrike",
        params=[
            ToolParam(name="url", type="string", required=True, description="Target URL with parameter"),
            ToolParam(name="level", type="integer", required=False, default=1, description="Test level 1–5"),
            ToolParam(name="risk", type="integer", required=False, default=1, description="Risk level 1–3"),
        ],
    ),
    ToolDefinition(
        id="hydra_bruteforce",
        name="Hydra Brute-Force",
        category="exploitation",
        description="Online brute-force password attacks against network services.",
        source="hexstrike",
        params=[
            ToolParam(name="target", type="string", required=True, description="Target host"),
            ToolParam(name="service", type="string", required=True, description="Service type (ssh/ftp/http-form)"),
            ToolParam(name="wordlist", type="string", required=False, default="/usr/share/wordlists/rockyou.txt"),
        ],
    ),
    ToolDefinition(
        id="nuclei_scan",
        name="Nuclei Template Scanner",
        category="vuln_scan",
        description="Fast template-based vulnerability scanner covering CVEs, misconfigs, exposures.",
        source="hexstrike",
        params=[
            ToolParam(name="target", type="string", required=True, description="Target URL or host"),
            ToolParam(name="templates", type="string", required=False, default="cves,misconfig", description="Comma-separated template tags"),
        ],
    ),
    ToolDefinition(
        id="gobuster_dirbusting",
        name="Gobuster Directory Brute-Force",
        category="recon",
        description="Enumerate hidden directories and files on web servers.",
        source="hexstrike",
        params=[
            ToolParam(name="url", type="string", required=True, description="Base URL"),
            ToolParam(name="wordlist", type="string", required=False, default="/usr/share/wordlists/dirb/common.txt"),
            ToolParam(name="extensions", type="string", required=False, default="php,html,js,txt"),
        ],
    ),
    ToolDefinition(
        id="metasploit_exploit",
        name="Metasploit Framework",
        category="exploitation",
        description="Run Metasploit modules for exploit development and verification.",
        source="hexstrike",
        params=[
            ToolParam(name="module", type="string", required=True, description="Metasploit module path"),
            ToolParam(name="rhosts", type="string", required=True, description="Target host(s)"),
            ToolParam(name="payload", type="string", required=False, description="Payload module path"),
        ],
    ),
    ToolDefinition(
        id="cai_emulation",
        name="CAI Red-Team Emulation",
        category="post_exploitation",
        description="AI-guided red-team session via CAI framework for post-exploitation and LLM-driven attack chains.",
        source="cai",
        params=[
            ToolParam(name="prompt", type="string", required=True, description="Initial prompt or objective"),
            ToolParam(name="agent_type", type="string", required=False, default="default", description="CAI agent type"),
        ],
    ),
    ToolDefinition(
        id="shodan_lookup",
        name="Shodan Intelligence Lookup",
        category="recon",
        description="Query Shodan for host intelligence: open ports, services, banners, and known vulnerabilities.",
        source="builtin",
        params=[
            ToolParam(name="query", type="string", required=True, description="IP, domain, or Shodan dork"),
        ],
    ),
    ToolDefinition(
        id="ssl_audit",
        name="SSL/TLS Audit",
        category="recon",
        description="Enumerate TLS versions, cipher suites, certificate validity, and BEAST/POODLE/HEARTBLEED vulnerabilities.",
        source="hexstrike",
        params=[
            ToolParam(name="host", type="string", required=True, description="Hostname or IP"),
            ToolParam(name="port", type="integer", required=False, default=443),
        ],
    ),
]

# Normalise by id for quick lookup
_CATALOG_BY_ID: dict[str, ToolDefinition] = {t.id: t for t in _STATIC_CATALOG}


async def _try_discover_from_hexstrike(hexstrike_url: str) -> list[ToolDefinition]:
    """Attempt to fetch /api/tools/list from HexStrike.  Returns [] on any error."""
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            resp = await client.get(f"{hexstrike_url.rstrip('/')}/api/tools/list")
            if resp.status_code == 200:
                raw = resp.json()
                tools = []
                for item in raw.get("tools", []):
                    tools.append(
                        ToolDefinition(
                            id=item.get("id", item.get("name", "unknown").lower().replace(" ", "_")),
                            name=item.get("name", "Unknown Tool"),
                            category=item.get("category", "recon"),
                            description=item.get("description", ""),
                            source="hexstrike",
                            params=[
                                ToolParam(
                                    name=p.get("name", ""),
                                    type=p.get("type", "string"),
                                    required=p.get("required", False),
                                    description=p.get("description", ""),
                                    default=p.get("default"),
                                )
                                for p in item.get("params", [])
                            ],
                        )
                    )
                log.info("Discovered %d tools from HexStrike at %s", len(tools), hexstrike_url)
                return tools
    except Exception as exc:  # noqa: BLE001
        log.debug("HexStrike discovery failed (%s), using static catalog", exc)
    return []


async def get_tool_registry(hexstrike_url: str | None = None) -> ToolRegistryResponse:
    """Return available tools, merging live HexStrike discovery with the static catalog."""
    discovered: list[ToolDefinition] = []
    if hexstrike_url:
        discovered = await _try_discover_from_hexstrike(hexstrike_url)

    # Merge: live discovery overrides static by id; static fills any gaps
    merged: dict[str, ToolDefinition] = dict(_CATALOG_BY_ID)
    for t in discovered:
        merged[t.id] = t

    return ToolRegistryResponse(
        tools=list(merged.values()),
        discovered_at=datetime.utcnow(),
    )


def get_tool_by_id(tool_id: str) -> ToolDefinition | None:
    return _CATALOG_BY_ID.get(tool_id)
