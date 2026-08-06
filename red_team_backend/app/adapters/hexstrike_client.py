"""HexStrike client — live HTTP calls to the HexStrike Flask API, stub fallback for CI/offline.

Live mode POSTs to HexStrike's `/api/tools/nmap` route (see hexstrike-ai `hexstrike_server.py`),
which returns `{"success": bool, "stdout": str, "stderr": str, "return_code": int, ...}`.
When `HEXSTRIKE_STUB` is not truthy, any HTTP/parse failure raises `RuntimeError` — callers must
not silently fall back to stub findings when live mode was requested.
"""
from __future__ import annotations

import re
from typing import Any

import httpx

from app.settings import WorkerSettings, get_settings

_OPEN_PORT_RE = re.compile(r"^(\d+)/(tcp|udp)\s+open\s+(\S+)", re.MULTILINE)


def _stub_result(target: str) -> dict[str, Any]:
    return {
        "tool": "nmap-stub",
        "target": target,
        "findings": [
            {
                "title": f"Open port discovery on {target}",
                "severity": "medium",
                "source_tool": "nmap",
                "evidence": f"stub scan of {target}",
                "technique": "T1046",
                "technique_name": "Network Service Discovery",
            }
        ],
    }


def _parse_nmap_findings(target: str, stdout: str) -> list[dict[str, Any]]:
    findings = [
        {
            "title": f"Open port {port}/{proto} ({service}) on {target}",
            "severity": "medium",
            "source_tool": "nmap",
            "evidence": f"{port}/{proto} open {service}",
            "technique": "T1046",
            "technique_name": "Network Service Discovery",
        }
        for port, proto, service in _OPEN_PORT_RE.findall(stdout or "")
    ]
    if not findings:
        findings.append(
            {
                "title": f"Nmap scan completed on {target}",
                "severity": "info",
                "source_tool": "nmap",
                "evidence": (stdout or "").strip()[:500] or "no output",
                "technique": "T1046",
                "technique_name": "Network Service Discovery",
            }
        )
    return findings


async def run_recon(
    hostname: str, ip: str | None = None, settings: WorkerSettings | None = None
) -> dict[str, Any]:
    """Return normalized recon findings, calling live HexStrike unless stubbed.

    Raises `RuntimeError` when live mode is enabled and the HexStrike call fails
    (unreachable server, non-2xx, or tool-level error) — never falls back to stub data.
    """
    settings = settings or get_settings()
    target = hostname or ip or "unknown"

    if settings.stub_hexstrike:
        return _stub_result(target)

    base = settings.hexstrike_base_url.rstrip("/")
    url = f"{base}/api/tools/nmap"
    try:
        async with httpx.AsyncClient(timeout=90.0) as client:
            resp = await client.post(url, json={"target": target})
            resp.raise_for_status()
            data = resp.json()
    except httpx.HTTPError as exc:
        raise RuntimeError(f"HexStrike live nmap call to {url} failed for {target}: {exc}") from exc
    except ValueError as exc:  # non-JSON response
        raise RuntimeError(f"HexStrike returned a non-JSON response from {url} for {target}: {exc}") from exc

    if not isinstance(data, dict):
        raise RuntimeError(f"HexStrike returned an unexpected payload from {url} for {target}: {data!r}")
    if data.get("error"):
        raise RuntimeError(f"HexStrike nmap error for {target}: {data['error']}")
    if data.get("success") is False:
        raise RuntimeError(
            f"HexStrike nmap reported failure for {target}: {data.get('stderr') or data.get('return_code')}"
        )

    return {
        "tool": "nmap",
        "target": target,
        "findings": _parse_nmap_findings(target, data.get("stdout", "")),
        "raw": data,
    }
