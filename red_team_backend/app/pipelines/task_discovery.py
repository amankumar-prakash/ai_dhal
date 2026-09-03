"""Task-discovery pipeline: HexStrike MCP agent (or stub) → tools, findings, chain, patches."""
from __future__ import annotations

import asyncio
import json
import os
import re
from typing import Any

from app.guardrails import demo_blocks_profile, in_allowlist
from app.reporters.api_reporter import ApiReporter
from app.settings import WorkerSettings, get_settings

_OPEN_PORT_RE = re.compile(r"^(\d+)/(tcp|udp)\s+open\s+(\S+)", re.MULTILINE)
_GOBUSTER_RE = re.compile(r"(/\S+)\s+\(Status:\s*(\d+)", re.IGNORECASE)
_NUCLEI_RE = re.compile(
    r"\[(?P<sev>critical|high|medium|low|info)\][^\n]*",
    re.IGNORECASE,
)

STUB_PHASES = [
    ("nmap_scan", "nmap -sV {target}", "80/tcp open http\n443/tcp open https"),
    (
        "httpx-toolkit",
        "httpx-toolkit -u {target} -sc -title -tech-detect -server -cl -silent",
        "{target} [200] [OWASP Juice Shop] [Express] [nginx]",
    ),
    (
        "gobuster_scan",
        "gobuster dir -u {target} -w /usr/share/dirb/wordlists/common.txt",
        "/ftp (Status: 200)\n/rest (Status: 200)\n/api (Status: 200)",
    ),
    (
        "katana_crawl",
        "katana -u {target} -d 2",
        "{target}/rest/products/search\n{target}/api/Challenges",
    ),
    (
        "rest-api-probe",
        "httpx-toolkit -u {target}/rest {target}/api {target}/api-docs {target}/ftp",
        "{target}/rest [200]\n{target}/api [200]\n{target}/ftp [200]",
    ),
    (
        "nuclei_scan",
        "nuclei -u {target} -tags exposure,token,config,misconfig",
        "[info] [http-missing-security-headers] {target}\n[low] [exposed-panel] {target}/ftp",
    ),
]


def _use_stub(settings: WorkerSettings) -> bool:
    return settings.stub_hexstrike or settings.stub_llm


def _host_from_job(job: dict[str, Any]) -> str:
    target = job.get("target") or ""
    assets = job.get("assets") or []
    asset = assets[0] if assets else {}
    return target or asset.get("hostname") or asset.get("name") or "unknown"


def _asset_and_scan(job: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any]]:
    assets = job.get("assets") or []
    scans = job.get("scans") or []
    return (assets[0] if assets else {}), (scans[0] if scans else {})


def _stdout_from_output(output: Any) -> str:
    if isinstance(output, dict):
        return str(output.get("stdout") or output.get("content") or json.dumps(output))
    text = str(output or "")
    try:
        data = json.loads(text)
        if isinstance(data, dict):
            return str(data.get("stdout") or text)
    except (json.JSONDecodeError, TypeError):
        pass
    return text


def extract_tool_calls(result: Any) -> list[dict[str, Any]]:
    """Pull (tool_name, args, output) from a LangChain agent result."""
    messages = result.get("messages") if isinstance(result, dict) else None
    if not messages:
        return []
    pending: dict[str, dict[str, Any]] = {}
    calls: list[dict[str, Any]] = []
    for msg in messages:
        tool_calls = getattr(msg, "tool_calls", None)
        if tool_calls is None and isinstance(msg, dict):
            tool_calls = msg.get("tool_calls")
        if tool_calls:
            for tc in tool_calls:
                if isinstance(tc, dict):
                    pending[str(tc.get("id") or "")] = tc
                else:
                    pending[str(getattr(tc, "id", "") or "")] = {
                        "name": getattr(tc, "name", None),
                        "args": getattr(tc, "args", None),
                    }
        name = getattr(msg, "name", None)
        tool_call_id = getattr(msg, "tool_call_id", None)
        content = getattr(msg, "content", None)
        msg_type = getattr(msg, "type", None)
        if isinstance(msg, dict):
            name = name or msg.get("name")
            tool_call_id = tool_call_id or msg.get("tool_call_id")
            content = content if content is not None else msg.get("content")
            msg_type = msg_type or msg.get("type")
        if name and (msg_type in {"tool", "ToolMessage"} or tool_call_id):
            meta = pending.get(str(tool_call_id or ""), {})
            calls.append(
                {
                    "tool_name": name,
                    "args": meta.get("args") or {},
                    "output": content,
                }
            )
    return calls


def parse_findings(tool_name: str, target: str, stdout: str) -> list[dict[str, Any]]:
    text = stdout or ""
    name = (tool_name or "").lower()
    findings: list[dict[str, Any]] = []

    if "nmap" in name:
        for port, proto, service in _OPEN_PORT_RE.findall(text):
            findings.append(
                {
                    "title": f"Open port {port}/{proto} ({service}) on {target}",
                    "severity": "medium",
                    "source_tool": "nmap",
                    "evidence": f"{port}/{proto} open {service}",
                    "technique": "T1046",
                    "technique_name": "Network Service Discovery",
                }
            )
    elif "gobuster" in name or "ferox" in name:
        for path, status in _GOBUSTER_RE.findall(text):
            findings.append(
                {
                    "title": f"Discovered path {path} ({status}) on {target}",
                    "severity": "low" if status.startswith("2") else "info",
                    "source_tool": "gobuster" if "gobuster" in name else "feroxbuster",
                    "evidence": f"{path} (Status: {status})",
                    "technique": "T1595.002",
                    "technique_name": "Active Scanning: Vulnerability Scanning",
                }
            )
    elif "nuclei" in name:
        for match in _NUCLEI_RE.finditer(text):
            sev = match.group("sev").lower()
            findings.append(
                {
                    "title": match.group(0).strip()[:240],
                    "severity": sev if sev in {"critical", "high", "medium", "low", "info"} else "info",
                    "source_tool": "nuclei",
                    "evidence": match.group(0).strip()[:500],
                    "technique": "T1595.002",
                    "technique_name": "Active Scanning: Vulnerability Scanning",
                }
            )
    elif "katana" in name:
        urls = [ln.strip() for ln in text.splitlines() if ln.strip().startswith("http")]
        for url in urls[:20]:
            findings.append(
                {
                    "title": f"Crawled endpoint {url}",
                    "severity": "info",
                    "source_tool": "katana",
                    "evidence": url,
                    "technique": "T1595.003",
                    "technique_name": "Active Scanning: Wordlist Scanning",
                }
            )
    elif "httpx" in name or "rest" in name or "probe" in name or "execute_command" in name:
        lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
        for line in lines[:15]:
            findings.append(
                {
                    "title": f"HTTP probe {line[:180]}",
                    "severity": "info",
                    "source_tool": "httpx-toolkit",
                    "evidence": line[:500],
                    "technique": "T1590.002",
                    "technique_name": "Gather Victim Network Information",
                }
            )

    if not findings and text.strip():
        findings.append(
            {
                "title": f"{tool_name} completed on {target}",
                "severity": "info",
                "source_tool": tool_name,
                "evidence": text.strip()[:500],
                "technique": "T1595",
                "technique_name": "Active Scanning",
            }
        )
    return findings


def propose_patch(finding: dict[str, Any]) -> tuple[str, str]:
    tool = str(finding.get("source_tool") or "").lower()
    title = str(finding.get("title") or "").lower()
    if "nuclei" in tool or "exposure" in title or "header" in title:
        return (
            "Hide version/debug endpoints and disable verbose error pages",
            "exposure-hardening",
        )
    if "gobuster" in tool or "ferox" in tool or "path" in title or "/ftp" in title:
        return (
            "Require authentication or remove publicly listed paths",
            "content-discovery-hardening",
        )
    if "nmap" in tool or "port" in title:
        return ("Restrict bind address and close unused ports", "network-hardening")
    if "httpx" in tool or "katana" in tool or "rest" in title or "api" in title:
        return (
            "Add authentication and rate limits on API/REST surfaces",
            "api-hardening",
        )
    return ("Review and remediate discovery finding", "general-hardening")


_RECON_TOOL_NAMES = frozenset(
    {
        "server_health",
        "nmap_scan",
        "gobuster_scan",
        "feroxbuster_scan",
        "katana_crawl",
        "nuclei_scan",
        "execute_command",
    }
)
_OPENAI_MAX_TOOLS = 128


def select_recon_tools(tools: list[Any]) -> list[Any]:
    """Keep discovery tools only — OpenAI rejects more than 128 function tools."""
    by_name: dict[str, Any] = {}
    for tool in tools:
        name = getattr(tool, "name", "") or ""
        if name:
            by_name[name] = tool
    selected = [by_name[name] for name in sorted(_RECON_TOOL_NAMES) if name in by_name]
    if selected:
        return selected
    return list(tools)[:_OPENAI_MAX_TOOLS]


def flatten_error(exc: BaseException) -> str:
    if isinstance(exc, BaseExceptionGroup):
        parts = [flatten_error(inner) for inner in exc.exceptions]
        return "; ".join(p for p in parts if p) or str(exc)
    msg = str(exc).strip() or type(exc).__name__
    cause = exc.__cause__
    if cause:
        inner = flatten_error(cause)
        if inner and inner not in msg:
            return f"{msg}: {inner}"
    return msg


def build_agent_prompt(job: dict[str, Any], target: str) -> str:
    description = (job.get("description") or "").strip()
    patch_scope = (job.get("patch_scope") or "").strip()
    return f"""You are a discovery-only red-team recon agent using HexStrike MCP tools.

Target: {target}
Task description: {description or "(none)"}
Patch scope: {patch_scope or "(none)"}

Rules:
- Stay on this target only. Do not exploit, brute-force, or use sqlmap/metasploit/hydra.
- Call server_health first.
- Then run these phases in order:
  1. nmap_scan with scan_type -sV and additional_args -Pn -T4 (host only, not the URL path).
  2. execute_command: httpx-toolkit -u {target} -sc -title -tech-detect -server -cl -silent
     Do NOT use httpx_probe or /api/tools/httpx — Kali's httpx is the Python client.
  3. gobuster_scan OR feroxbuster_scan with wordlist /usr/share/dirb/wordlists/common.txt
  4. katana_crawl with depth 2, js_crawl true, form_extraction true
  5. execute_command to probe {target}/rest {target}/api {target}/api-docs {target}/ftp {target}/robots.txt {target}/metrics
  6. nuclei_scan with tags exposure,token,config,misconfig,disclosure,panel,tech
- If a tool is missing, skip it and continue.
- After tools finish, summarize open ports, HTTP fingerprint, discovered paths, API surfaces, and exposure findings.
"""


async def _run_live_agent(job: dict[str, Any], target: str, settings: WorkerSettings) -> list[dict[str, Any]]:
    from langchain.agents import create_agent
    from langchain_mcp_adapters.tools import load_mcp_tools

    from app.adapters.mcp_client import create_mcp_client

    settings.require_llm_for_live()
    if settings.openai_api_key:
        os.environ.setdefault("OPENAI_API_KEY", settings.openai_api_key)

    model = f"openai:{settings.llm_model}"
    client = create_mcp_client(settings)
    async with client.session("hexstrike-ai") as session:
        tools = select_recon_tools(await load_mcp_tools(session))
        if not tools:
            raise RuntimeError("HexStrike MCP returned no recon tools")
        agent = create_agent(model, tools)
        result = await asyncio.wait_for(
            agent.ainvoke({"messages": [{"role": "user", "content": build_agent_prompt(job, target)}]}),
            timeout=900,
        )
    return extract_tool_calls(result)


def _stub_calls(target: str) -> list[dict[str, Any]]:
    calls = []
    for name, summary, stdout in STUB_PHASES:
        calls.append(
            {
                "tool_name": name,
                "args": {"target": target},
                "output": {"success": True, "stdout": stdout.format(target=target), "command_summary": summary.format(target=target)},
            }
        )
    return calls


async def run(job: dict[str, Any], settings: WorkerSettings | None = None) -> None:
    settings = settings or get_settings()
    reporter = ApiReporter(settings)
    job_id = job["job_id"]
    await reporter.patch_job(job_id, status="running")

    target = _host_from_job(job)
    asset, scan = _asset_and_scan(job)
    host = asset.get("hostname") or target
    scan_id = scan.get("id")
    asset_id = asset.get("id")

    try:
        if not in_allowlist(str(host), settings.target_allowlist) and not in_allowlist(
            str(target), settings.target_allowlist
        ):
            await reporter.post_threat_event(
                {
                    "technique": "blocked_by_guardrail",
                    "technique_name": "Out of scope target",
                    "description": f"Target {target} outside allowlist",
                    "severity": "info",
                    "status": "blocked_by_guardrail",
                    "team": "red",
                    "source_tag": "blocked_by_guardrail",
                    "asset_id": asset_id,
                    "source_ip": "0.0.0.0",
                }
            )
            await reporter.patch_job(job_id, status="completed")
            return

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
                    "asset_id": asset_id,
                    "source_ip": "0.0.0.0",
                }
            )
            await reporter.patch_job(job_id, status="completed")
            return

        if _use_stub(settings):
            calls = _stub_calls(target)
        else:
            calls = await _run_live_agent(job, target, settings)

        chain = await reporter.post_attack_chain(
            {
                "name": f"Task discovery {str(job_id)[:8]}",
                "team": "red",
                "scan_id": scan_id,
            }
        )
        chain_id = str(chain["id"]) if chain and chain.get("id") else None
        sequence = 0

        for call in calls:
            tool_name = str(call.get("tool_name") or "tool")
            stdout = _stdout_from_output(call.get("output"))
            args = call.get("args") or {}
            summary = str(args) if args else tool_name
            if isinstance(call.get("output"), dict) and call["output"].get("command_summary"):
                summary = str(call["output"]["command_summary"])

            await reporter.post_tool_run(
                {
                    "job_id": job_id,
                    "team": "red",
                    "tool_name": tool_name,
                    "command_summary": summary[:500],
                    "exit_code": 0,
                    "raw_output": {
                        "args": args,
                        "stdout": stdout[:8000],
                    },
                }
            )
            sequence += 1
            if chain_id:
                await reporter.post_chain_step(
                    chain_id,
                    {
                        "stage": "recon",
                        "sequence": sequence,
                        "title": f"{tool_name} on {target}",
                        "severity": "info",
                        "category": "tools",
                        "source_tool": tool_name,
                        "evidence": stdout[:500] or None,
                    },
                )

            for finding in parse_findings(tool_name, target, stdout):
                posted = await reporter.post_finding(
                    {
                        "title": finding["title"],
                        "severity": finding["severity"],
                        "team": "red",
                        "source_tool": finding["source_tool"],
                        "evidence": finding.get("evidence"),
                        "asset_id": asset_id,
                        "scan_id": scan_id,
                        "status": "open",
                        "remediation": propose_patch(finding)[0],
                    }
                )
                sequence += 1
                finding_id = posted.get("id") if posted else None
                if chain_id:
                    await reporter.post_chain_step(
                        chain_id,
                        {
                            "stage": "recon",
                            "sequence": sequence,
                            "title": finding["title"],
                            "severity": finding["severity"],
                            "category": "findings",
                            "source_tool": finding["source_tool"],
                            "finding_id": finding_id,
                            "evidence": finding.get("evidence"),
                        },
                    )
                if finding_id:
                    title, playbook = propose_patch(finding)
                    await reporter.post_patch(
                        {
                            "finding_id": finding_id,
                            "title": title,
                            "playbook": playbook,
                            "asset_id": asset_id,
                        }
                    )
                await reporter.post_threat_event(
                    {
                        "technique": finding.get("technique", "T1595"),
                        "technique_name": finding.get("technique_name"),
                        "description": finding["title"],
                        "severity": finding["severity"],
                        "team": "red",
                        "source_tag": "hexstrike",
                        "asset_id": asset_id,
                        "finding_id": finding_id,
                        "source_ip": asset.get("ip_address") or "0.0.0.0",
                    }
                )
    except Exception as exc:
        await reporter.patch_job(job_id, status="failed", error=flatten_error(exc))
        raise

    await reporter.patch_job(job_id, status="completed")
