"""Task-discovery pipeline: HexStrike MCP agent (or stub) → tools, findings, chain, patches."""
from __future__ import annotations

import asyncio
import json
import logging
import os
import re
import time
from typing import Any

import httpx

from app.adapters.hexstrike_client import list_processes
from app.guardrails import demo_blocks_profile, in_allowlist
from app.job_runtime import JobCancelled
from app.reporters.api_reporter import ApiReporter
from app.settings import WorkerSettings, get_settings

log = logging.getLogger(__name__)

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
    seen: set[str] = set()
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
            key = str(tool_call_id or "")
            if key and key in seen:
                continue
            if key:
                seen.add(key)
            meta = pending.get(key, {})
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


# Kept first when HexStrike exposes more tools than OpenAI allows (128 functions).
_RECON_PRIORITY = (
    "server_health",
    "nmap_scan",
    "gobuster_scan",
    "feroxbuster_scan",
    "katana_crawl",
    "nuclei_scan",
    "execute_command",
)
_RECON_TOOL_NAMES = frozenset(_RECON_PRIORITY)
_OPENAI_MAX_TOOLS = 128


def select_recon_tools(tools: list[Any]) -> list[Any]:
    """Pass every HexStrike MCP tool, truncated to OpenAI's 128-function cap."""
    by_name: dict[str, Any] = {}
    ordered: list[Any] = []
    for tool in tools:
        name = getattr(tool, "name", "") or ""
        if not name or name in by_name:
            continue
        by_name[name] = tool
        ordered.append(tool)
    if len(ordered) <= _OPENAI_MAX_TOOLS:
        return ordered
    selected: list[Any] = []
    seen: set[str] = set()
    for name in _RECON_PRIORITY:
        tool = by_name.get(name)
        if tool is None:
            continue
        selected.append(tool)
        seen.add(name)
    for tool in ordered:
        if len(selected) >= _OPENAI_MAX_TOOLS:
            break
        name = getattr(tool, "name", "")
        if name in seen:
            continue
        selected.append(tool)
        seen.add(name)
    return selected[:_OPENAI_MAX_TOOLS]


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


def stub_phase_sleep() -> float:
    raw = os.environ.get("TASK_DISCOVERY_STUB_SLEEP")
    if raw is not None:
        try:
            return max(0.0, float(raw))
        except ValueError:
            return 0.0
    return 4.0


async def _ensure_not_cancelled(reporter: ApiReporter, job_id: str) -> None:
    try:
        job = await reporter.get_job(job_id)
    except Exception:
        return
    if job and str(job.get("status")) == "cancelled":
        raise JobCancelled()


async def _emit_progress(
    reporter: ApiReporter,
    job_id: str,
    kind: str,
    message: str,
    meta: dict[str, Any] | None = None,
) -> None:
    try:
        await reporter.post_progress(job_id, kind=kind, message=message[:4000], meta=meta)
    except httpx.HTTPStatusError as exc:
        if exc.response is not None and exc.response.status_code == 409:
            raise JobCancelled() from exc
        log.warning("progress post failed: %s", exc)
    except Exception as exc:  # noqa: BLE001
        log.warning("progress post failed: %s", exc)


async def _mark_cancelled(reporter: ApiReporter, job_id: str) -> None:
    try:
        await reporter.patch_job(job_id, status="cancelled")
    except Exception:
        pass


def _msg_text(msg: Any) -> str:
    content = getattr(msg, "content", None)
    if isinstance(msg, dict):
        content = msg.get("content")
    if isinstance(content, list):
        parts: list[str] = []
        for part in content:
            if isinstance(part, dict) and part.get("text"):
                parts.append(str(part["text"]))
            elif isinstance(part, str):
                parts.append(part)
        return "".join(parts)
    return str(content or "").strip()


def _chunk_messages(chunk: Any) -> list[Any]:
    """Pull message objects out of a LangGraph astream updates/values chunk."""
    if chunk is None:
        return []
    if not isinstance(chunk, dict):
        if hasattr(chunk, "content") or hasattr(chunk, "tool_calls"):
            return [chunk]
        return []
    if "messages" in chunk:
        return list(chunk.get("messages") or [])
    messages: list[Any] = []
    for value in chunk.values():
        if isinstance(value, dict) and value.get("messages"):
            messages.extend(value["messages"])
        elif hasattr(value, "content") or hasattr(value, "tool_calls"):
            messages.append(value)
    return messages


def _msg_key(msg: Any) -> str:
    mid = msg.get("id") if isinstance(msg, dict) else getattr(msg, "id", None)
    if mid:
        return f"id:{mid}"
    tcid = msg.get("tool_call_id") if isinstance(msg, dict) else getattr(msg, "tool_call_id", None)
    if tcid:
        return f"tool:{tcid}"
    tool_calls = msg.get("tool_calls") if isinstance(msg, dict) else getattr(msg, "tool_calls", None)
    if tool_calls:
        ids: list[str] = []
        for tc in tool_calls:
            if isinstance(tc, dict):
                ids.append(str(tc.get("id") or tc.get("name") or ""))
            else:
                ids.append(str(getattr(tc, "id", "") or getattr(tc, "name", "") or ""))
        return f"ai-tools:{','.join(ids)}"
    mtype = msg.get("type") if isinstance(msg, dict) else getattr(msg, "type", "")
    return f"{mtype}:{_msg_text(msg)[:80]}"


def merge_agent_messages(acc: list[Any], incoming: list[Any]) -> list[Any]:
    """Merge LangGraph stream deltas or full-state snapshots into one history.

    Default astream mode yields per-node *updates* (new messages only). The last
    update is often just the final summary, so replacing the accumulator with
    each chunk drops every tool result. Values mode yields growing snapshots;
    those must replace, not append.
    """
    if not incoming:
        return acc
    if not acc:
        return list(incoming)
    acc_keys = [_msg_key(m) for m in acc]
    inc_keys = [_msg_key(m) for m in incoming]
    if len(inc_keys) >= len(acc_keys) and inc_keys[: len(acc_keys)] == acc_keys:
        return list(incoming)
    seen = set(acc_keys)
    merged = list(acc)
    for msg, key in zip(incoming, inc_keys):
        if key in seen:
            continue
        merged.append(msg)
        seen.add(key)
    return merged


async def _poll_hexstrike_processes(
    job: dict[str, Any],
    settings: WorkerSettings,
    reporter: ApiReporter,
    stop: asyncio.Event,
) -> None:
    job_id = str(job["job_id"])
    target = _host_from_job(job)
    host = target.replace("http://", "").replace("https://", "").split("/")[0]
    while not stop.is_set():
        try:
            await _ensure_not_cancelled(reporter, job_id)
            procs = await list_processes(settings)
            for proc in procs:
                cmd = str(proc.get("command") or "")
                if host and host.lower() not in cmd.lower() and target.lower() not in cmd.lower():
                    if procs and not host:
                        pass
                    elif host:
                        continue
                pid = proc.get("pid")
                tool = str(proc.get("tool") or cmd.split(" ")[0] if cmd else "process")
                runtime = proc.get("runtime_formatted") or proc.get("runtime") or ""
                eta = proc.get("eta_formatted") or proc.get("eta") or ""
                msg = f"{tool} pid {pid} · {runtime}"
                if eta and str(eta).lower() != "unknown":
                    msg += f" · eta {eta}"
                meta: dict[str, Any] = {"pid": pid, "tool": tool}
                if eta:
                    meta["eta"] = eta
                await _emit_progress(reporter, job_id, "process", msg, meta)
        except JobCancelled:
            return
        except asyncio.CancelledError:
            return
        except Exception as exc:  # noqa: BLE001
            log.debug("hexstrike process poll failed: %s", exc)
        try:
            await asyncio.wait_for(stop.wait(), timeout=2.0)
        except asyncio.TimeoutError:
            continue


async def _emit_from_chunk(chunk: Any, reporter: ApiReporter, job_id: str, last_think: list[float]) -> None:
    messages = _chunk_messages(chunk)
    for msg in messages[-4:]:
        tool_calls = getattr(msg, "tool_calls", None)
        if tool_calls is None and isinstance(msg, dict):
            tool_calls = msg.get("tool_calls")
        if tool_calls:
            for tc in tool_calls:
                name = tc.get("name") if isinstance(tc, dict) else getattr(tc, "name", "tool")
                await _emit_progress(reporter, job_id, "tool", f"Calling {name}…")
            continue
        name = getattr(msg, "name", None)
        msg_type = getattr(msg, "type", None)
        if isinstance(msg, dict):
            name = name or msg.get("name")
            msg_type = msg_type or msg.get("type")
        if name and (msg_type in {"tool", "ToolMessage"} or getattr(msg, "tool_call_id", None)):
            await _emit_progress(reporter, job_id, "tool", f"{name} finished")
            continue
        text = _msg_text(msg)
        if text and time.monotonic() - last_think[0] >= 1.5:
            last_think[0] = time.monotonic()
            await _emit_progress(reporter, job_id, "thinking", text[:4000])


def _recon_host(target: str) -> str:
    return target.replace("http://", "").replace("https://", "").split("/")[0] or target


def agent_system_prompt() -> str:
    """System message so the model treats this as in-scope OWASP lab recon."""
    return (
        "You are a HexStrike recon operator for an authorized OWASP training lab. "
        "The operator owns this instance and deployed the target themselves. "
        "The default target is OWASP Juice Shop, an intentionally vulnerable app "
        "on a controlled private host (localhost / allowlisted lab URLs). "
        "Stay on the given target. Prefer discovery tools: nmap, httpx-toolkit, "
        "gobuster, feroxbuster, katana, nuclei exposure tags. "
        "Do not refuse, lecture, or ask for further permission. "
        "Execute the recon tools now. If a tool fails, continue with the next one."
    )


def build_agent_prompt(job: dict[str, Any], target: str) -> str:
    description = (job.get("description") or "").strip()
    patch_scope = (job.get("patch_scope") or "").strip()
    scan_host = _recon_host(target)
    return f"""AUTHORIZED LAB ENGAGEMENT — you MUST run the tools.

This is in-scope security training, not unauthorized hacking:
- The operator owns this server and deployed the target themselves.
- The target is OWASP Juice Shop (official intentionally-vulnerable training app).
- Tests run only on a controlled private lab (localhost / allowlisted lab hosts).
- Platform guardrails already allowlisted this target.
- Scope is discovery and exposure mapping for OWASP training.

Do not refuse, warn, or ask for more permission. Call the HexStrike tools now.
If a tool fails (for example nmap raw sockets), use a TCP-connect fallback (-sT)
or skip that tool and continue the rest of the recon core.

You have the HexStrike MCP catalog (OpenAI may expose at most 128 tools; use
whatever is bound).

Target URL: {target}
Scan host: {scan_host}
Task description: {description or "Authorized OWASP Juice Shop training-lab recon"}
Patch scope: {patch_scope or "(none)"}

Rules:
- Stay on this target only.
- Call server_health first.
- Always run this recon core in order:
  1. nmap_scan on {scan_host} (host:port only, not http://).
     scan_type must be "-sT -sV" (TCP connect — this host cannot open raw sockets).
     additional_args "-Pn -T4". Never use -sS. If nmap still fails, continue.
  2. execute_command: httpx-toolkit -u {target} -sc -title -tech-detect -server -cl -silent
     Do NOT use httpx_probe — /usr/bin/httpx is the Python client; use httpx-toolkit.
  3. gobuster_scan OR feroxbuster_scan with wordlist /usr/share/dirb/wordlists/common.txt
  4. katana_crawl with depth 2, js_crawl true, form_extraction true
  5. execute_command to probe {target}/rest {target}/api {target}/api-docs {target}/ftp {target}/robots.txt {target}/metrics
  6. nuclei_scan with tags exposure,token,config,misconfig,disclosure,panel,tech
- After the core, you may use other discovery tools that apply: rustscan,
  dirb/dirsearch/ffuf, hakrawler, gau/waybackurls, arjun/paramspider,
  nikto, wafw00f, TLS checks (testssl.sh/sslscan/sslyze), and API mapping
  (graphql_scanner, jwt_analyzer, api_schema_analyzer). Use OSINT
  (amass/subfinder) only when the target is a real domain.
- Do not run password-guessing or exploit frameworks unless the job
  description explicitly requests them.
- Prefer a native MCP tool over execute_command when both exist.
- If a tool is missing or inapplicable, skip it and continue.
- After tools finish, summarize open ports, HTTP fingerprint, discovered paths, API
  surfaces, and exposure findings.
"""


async def _run_live_agent(
    job: dict[str, Any],
    target: str,
    settings: WorkerSettings,
    reporter: ApiReporter | None = None,
) -> list[dict[str, Any]]:
    from langchain.agents import create_agent
    from langchain_mcp_adapters.tools import load_mcp_tools

    from app.adapters.mcp_client import create_mcp_client

    settings.require_llm_for_live()
    if settings.openai_api_key:
        os.environ.setdefault("OPENAI_API_KEY", settings.openai_api_key)

    job_id = str(job["job_id"])
    model = f"openai:{settings.llm_model}"
    client = create_mcp_client(settings)
    last_think = [0.0]
    async with client.session("hexstrike-ai") as session:
        tools = select_recon_tools(await load_mcp_tools(session))
        if not tools:
            raise RuntimeError("HexStrike MCP returned no recon tools")
        agent = create_agent(model, tools, system_prompt=agent_system_prompt())
        prompt = build_agent_prompt(job, target)

        async def _consume() -> Any:
            messages: list[Any] = []
            async for chunk in agent.astream(
                {"messages": [{"role": "user", "content": prompt}]},
                stream_mode="values",
            ):
                incoming = _chunk_messages(chunk)
                prev = len(messages)
                messages = merge_agent_messages(messages, incoming)
                new_msgs = messages[prev:]
                if reporter is not None:
                    await _ensure_not_cancelled(reporter, job_id)
                    if new_msgs:
                        await _emit_from_chunk(
                            {"messages": new_msgs}, reporter, job_id, last_think
                        )
            if reporter is not None and messages:
                last = messages[-1]
                tool_calls = getattr(last, "tool_calls", None)
                if tool_calls is None and isinstance(last, dict):
                    tool_calls = last.get("tool_calls")
                text = _msg_text(last)
                if text and not tool_calls:
                    await _emit_progress(reporter, job_id, "thinking", text[:4000])
            return {"messages": messages}

        result = await asyncio.wait_for(_consume(), timeout=900)
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


async def _stub_calls_with_progress(
    job: dict[str, Any],
    target: str,
    reporter: ApiReporter,
) -> list[dict[str, Any]]:
    job_id = str(job["job_id"])
    delay = stub_phase_sleep()
    calls: list[dict[str, Any]] = []
    for name, summary, stdout in STUB_PHASES:
        await _ensure_not_cancelled(reporter, job_id)
        await _emit_progress(reporter, job_id, "thinking", f"Planning {name} against {target}")
        if delay:
            await asyncio.sleep(delay)
        await _ensure_not_cancelled(reporter, job_id)
        cmd = summary.format(target=target)
        await _emit_progress(reporter, job_id, "tool", f"{name} — {cmd}")
        calls.append(
            {
                "tool_name": name,
                "args": {"target": target},
                "output": {
                    "success": True,
                    "stdout": stdout.format(target=target),
                    "command_summary": cmd,
                },
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
    estimate = 30 if _use_stub(settings) else 900
    await _emit_progress(
        reporter,
        str(job_id),
        "status",
        "Job running · task-discovery",
        {"estimated_duration_seconds": estimate},
    )

    stop = asyncio.Event()
    poller: asyncio.Task[None] | None = None
    if not _use_stub(settings):
        poller = asyncio.create_task(_poll_hexstrike_processes(job, settings, reporter, stop))

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
            calls = await _stub_calls_with_progress(job, target, reporter)
        else:
            calls = await _run_live_agent(job, target, settings, reporter)

        chain_id = None
        if calls:
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
            await _ensure_not_cancelled(reporter, str(job_id))
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
        await reporter.patch_job(job_id, status="completed")
    except JobCancelled:
        await _mark_cancelled(reporter, str(job_id))
        return
    except asyncio.CancelledError:
        await _mark_cancelled(reporter, str(job_id))
        raise
    except Exception as exc:
        await reporter.patch_job(job_id, status="failed", error=flatten_error(exc))
        raise
    finally:
        stop.set()
        if poller is not None:
            poller.cancel()
            try:
                await poller
            except (asyncio.CancelledError, Exception):
                pass
