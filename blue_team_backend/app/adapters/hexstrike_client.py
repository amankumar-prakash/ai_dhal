"""HexStrike client for the blue vuln-scan path — live nuclei call, stub fallback for CI/offline.

Live mode POSTs to HexStrike's `/api/tools/nuclei` route (see hexstrike-ai `hexstrike_server.py`),
which returns `{"success": bool, "stdout": str, "stderr": str, "return_code": int, ...}`.
When `HEXSTRIKE_STUB` is not truthy, any HTTP/parse failure raises `RuntimeError` — callers must
not silently fall back to stub findings when live mode was requested.
"""
from __future__ import annotations

import re
from typing import Any

import httpx

from app.settings import WorkerSettings, get_settings

_SEVERITY_RE = re.compile(r"\[(critical|high|medium|low|info)\]", re.IGNORECASE)
_KNOWN_SEVERITIES = {"critical", "high", "medium", "low", "info"}


def _stub_result(target: str) -> dict[str, Any]:
    return {
        "tool": "trivy-stub",
        "target": target,
        "findings": [
            {
                "title": f"Vulnerable package on {target}",
                "severity": "high",
                "source_tool": "trivy",
                "evidence": f"stub vuln scan of {target}",
                "remediation": "Upgrade package",
            }
        ],
    }


def _parse_nuclei_findings(target: str, stdout: str) -> list[dict[str, Any]]:
    findings: list[dict[str, Any]] = []
    for line in (stdout or "").splitlines():
        line = line.strip()
        if not line:
            continue
        match = _SEVERITY_RE.search(line)
        severity = match.group(1).lower() if match else None
        if severity not in _KNOWN_SEVERITIES:
            continue
        findings.append(
            {
                "title": line[:200],
                "severity": severity,
                "source_tool": "nuclei",
                "evidence": line,
                "remediation": "Review and patch the reported vulnerability/template match",
            }
        )
    if not findings:
        findings.append(
            {
                "title": f"Nuclei scan completed on {target}",
                "severity": "info",
                "source_tool": "nuclei",
                "evidence": (stdout or "").strip()[:500] or "no output",
                "remediation": None,
            }
        )
    return findings


async def run_vuln_scan(target: str, settings: WorkerSettings | None = None) -> dict[str, Any]:
    """Return normalized vuln findings, calling live HexStrike (nuclei) unless stubbed.

    Raises `RuntimeError` when live mode is enabled and the HexStrike call fails
    (unreachable server, non-2xx, or tool-level error) — never falls back to stub data.
    """
    settings = settings or get_settings()

    if settings.stub_hexstrike:
        return _stub_result(target)

    base = settings.hexstrike_base_url.rstrip("/")
    url = f"{base}/api/tools/nuclei"
    try:
        async with httpx.AsyncClient(timeout=90.0) as client:
            resp = await client.post(url, json={"target": target})
            resp.raise_for_status()
            data = resp.json()
    except httpx.HTTPError as exc:
        raise RuntimeError(f"HexStrike live nuclei call to {url} failed for {target}: {exc}") from exc
    except ValueError as exc:  # non-JSON response
        raise RuntimeError(f"HexStrike returned a non-JSON response from {url} for {target}: {exc}") from exc

    if not isinstance(data, dict):
        raise RuntimeError(f"HexStrike returned an unexpected payload from {url} for {target}: {data!r}")
    if data.get("error"):
        raise RuntimeError(f"HexStrike nuclei error for {target}: {data['error']}")
    if data.get("success") is False:
        raise RuntimeError(
            f"HexStrike nuclei reported failure for {target}: {data.get('stderr') or data.get('return_code')}"
        )

    return {
        "tool": "nuclei",
        "target": target,
        "findings": _parse_nuclei_findings(target, data.get("stdout", "")),
        "raw": data,
    }
