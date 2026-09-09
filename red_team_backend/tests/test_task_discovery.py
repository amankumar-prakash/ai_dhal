"""task-discovery stub emits per-phase tool runs, findings, and patches; live fails closed."""
from __future__ import annotations

import asyncio

import pytest

from app.pipelines import task_discovery
from app.reporters.api_reporter import ApiReporter
from app.settings import WorkerSettings

UNREACHABLE_BASE_URL = "http://127.0.0.1:1"


class FakeReporter(ApiReporter):
    def __init__(self) -> None:
        self.calls: list[tuple[str, object]] = []
        self._finding_n = 0
        self._chain_id = "chain-1"

    async def patch_job(self, job_id, **fields):
        self.calls.append(("patch", job_id, fields))

    async def post_threat_event(self, payload):
        self.calls.append(("threat_event", payload))

    async def post_tool_run(self, payload):
        self.calls.append(("tool_run", payload))
        return {"id": "tr-1"}

    async def post_finding(self, payload):
        self._finding_n += 1
        row = {"id": f"f-{self._finding_n}", **payload}
        self.calls.append(("finding", row))
        return row

    async def post_attack_chain(self, payload):
        self.calls.append(("chain", payload))
        return {"id": self._chain_id}

    async def post_chain_step(self, chain_id, payload):
        self.calls.append(("step", chain_id, payload))
        return {"id": "s-1"}

    async def post_patch(self, payload):
        self.calls.append(("patch_record", payload))
        return {"id": "p-1"}

    async def get_job(self, job_id):
        self.calls.append(("get_job", job_id))
        return {"id": job_id, "status": getattr(self, "job_status", "running")}

    async def post_progress(self, job_id, *, kind, message, meta=None):
        self.calls.append(("progress", job_id, {"kind": kind, "message": message, "meta": meta or {}}))
        return {"id": "ev-1"}


@pytest.mark.asyncio
async def test_stub_emits_tool_finding_and_patch_per_phase(monkeypatch):
    monkeypatch.setenv("TASK_DISCOVERY_STUB_SLEEP", "0")
    settings = WorkerSettings(hexstrike_stub="1", llm_stub="1", target_allowlist="")
    fake = FakeReporter()
    monkeypatch.setattr("app.pipelines.task_discovery.ApiReporter", lambda settings=None: fake)

    await task_discovery.run(
        {
            "job_id": "j1",
            "profile": "task-discovery",
            "target": "http://juice.lab:3000",
            "description": "Phases: nmap, httpx-toolkit, gobuster, katana, nuclei",
            "assets": [{"id": "a1", "hostname": "juice.lab", "ip_address": "10.0.0.1"}],
            "scans": [{"id": "s1", "asset_id": "a1"}],
            "allowlist": ["juice.lab"],
        },
        settings,
    )

    tools = [c[1]["tool_name"] for c in fake.calls if c[0] == "tool_run"]
    assert tools == [
        "nmap_scan",
        "httpx-toolkit",
        "gobuster_scan",
        "katana_crawl",
        "rest-api-probe",
        "nuclei_scan",
    ]
    findings = [c for c in fake.calls if c[0] == "finding"]
    patches = [c for c in fake.calls if c[0] == "patch_record"]
    steps = [c for c in fake.calls if c[0] == "step"]
    assert findings
    assert patches
    assert any(c[2].get("category") == "tools" for c in steps)
    assert any(c[2].get("category") == "findings" for c in steps)
    assert any(c[0] == "patch" and c[2].get("status") == "completed" for c in fake.calls)
    progress_kinds = [c[2]["kind"] for c in fake.calls if c[0] == "progress"]
    assert "status" in progress_kinds
    assert "thinking" in progress_kinds
    assert "tool" in progress_kinds


@pytest.mark.asyncio
async def test_live_unreachable_fails_closed(monkeypatch):
    settings = WorkerSettings(
        hexstrike_stub="0",
        llm_stub="0",
        openai_api_key="sk-test",
        hexstrike_base_url=UNREACHABLE_BASE_URL,
        target_allowlist="",
    )
    fake = FakeReporter()
    monkeypatch.setattr("app.pipelines.task_discovery.ApiReporter", lambda settings=None: fake)

    async def boom(*_a, **_k):
        raise RuntimeError("HexStrike MCP unreachable")

    monkeypatch.setattr("app.pipelines.task_discovery._run_live_agent", boom)

    with pytest.raises(RuntimeError):
        await task_discovery.run(
            {
                "job_id": "j2",
                "profile": "task-discovery",
                "target": "http://juice.lab:3000",
                "assets": [{"id": "a1", "hostname": "juice.lab"}],
            },
            settings,
        )

    assert any(c[0] == "patch" and c[2].get("status") == "failed" for c in fake.calls)


def test_build_agent_prompt_states_owasp_lab_authorization():
    prompt = task_discovery.build_agent_prompt(
        {
            "description": "Authorized HexStrike recon of OWASP Juice Shop",
            "patch_scope": "none — lab Juice Shop",
        },
        "http://127.0.0.1:10200",
    )
    low = prompt.lower()
    assert "authorized lab engagement" in low
    assert "owasp juice shop" in low
    assert "do not refuse" in low
    assert "training" in low
    assert "127.0.0.1:10200" in prompt
    assert '-sT -sV' in prompt or "-st -sv" in low
    assert "metasploit" not in low
    assert "msfvenom" not in low
    system = task_discovery.agent_system_prompt().lower()
    assert "authorized" in system
    assert "do not refuse" in system


def test_select_recon_tools_keeps_under_openai_limit():
    class Tool:
        def __init__(self, name: str) -> None:
            self.name = name

    tools = [Tool(f"extra_{i}") for i in range(150)]
    tools.extend(
        [
            Tool("server_health"),
            Tool("nmap_scan"),
            Tool("execute_command"),
            Tool("nuclei_scan"),
            Tool("gobuster_scan"),
            Tool("katana_crawl"),
            Tool("feroxbuster_scan"),
        ]
    )
    selected = task_discovery.select_recon_tools(tools)
    names = {t.name for t in selected}
    assert len(selected) == 128
    assert names.issuperset(task_discovery._RECON_TOOL_NAMES)
    assert "extra_0" in names


def test_select_recon_tools_passes_all_when_under_cap():
    class Tool:
        def __init__(self, name: str) -> None:
            self.name = name

    tools = [Tool("nmap_scan"), Tool("sqlmap_scan"), Tool("hydra_attack"), Tool("prowler_scan")]
    selected = task_discovery.select_recon_tools(tools)
    assert [t.name for t in selected] == ["nmap_scan", "sqlmap_scan", "hydra_attack", "prowler_scan"]


def _ai_tool(call_id: str, name: str, args: dict | None = None) -> dict:
    return {
        "id": f"ai-{call_id}",
        "type": "ai",
        "content": "",
        "tool_calls": [{"id": call_id, "name": name, "args": args or {}}],
    }


def _tool_result(call_id: str, name: str, output: str) -> dict:
    return {
        "id": f"tool-{call_id}",
        "type": "tool",
        "name": name,
        "tool_call_id": call_id,
        "content": output,
    }


def test_merge_agent_messages_keeps_tools_from_update_chunks():
    nmap_ai = _ai_tool("c1", "nmap_scan", {"target": "127.0.0.1"})
    nmap_out = _tool_result("c1", "nmap_scan", "80/tcp open http")
    nuclei_ai = _ai_tool("c2", "nuclei_scan", {"url": "http://127.0.0.1:10200"})
    nuclei_out = _tool_result("c2", "nuclei_scan", "[info] exposed-panel")
    summary = {"id": "ai-end", "type": "ai", "content": "### Reconnaissance Summary"}

    acc: list = []
    for incoming in ([nmap_ai], [nmap_out], [nuclei_ai], [nuclei_out], [summary]):
        acc = task_discovery.merge_agent_messages(acc, incoming)

    calls = task_discovery.extract_tool_calls({"messages": acc})
    assert [c["tool_name"] for c in calls] == ["nmap_scan", "nuclei_scan"]
    assert "80/tcp open http" in str(calls[0]["output"])

    last_chunk_only = task_discovery.extract_tool_calls({"messages": [summary]})
    assert last_chunk_only == []


def test_merge_agent_messages_replaces_growing_snapshots():
    nmap_ai = _ai_tool("c1", "nmap_scan")
    nmap_out = _tool_result("c1", "nmap_scan", "22/tcp open ssh")
    summary = {"id": "ai-end", "type": "ai", "content": "done"}
    snap1 = [nmap_ai, nmap_out]
    snap2 = [nmap_ai, nmap_out, summary]
    acc = task_discovery.merge_agent_messages([], snap1)
    acc = task_discovery.merge_agent_messages(acc, snap2)
    assert acc == snap2
    calls = task_discovery.extract_tool_calls({"messages": acc})
    assert [c["tool_name"] for c in calls] == ["nmap_scan"]


def test_chunk_messages_reads_langgraph_update_and_values():
    tool = _tool_result("c1", "gobuster_scan", "/ftp (Status: 200)")
    assert task_discovery._chunk_messages({"model": {"messages": [_ai_tool("c1", "gobuster_scan")]}})
    assert task_discovery._chunk_messages({"tools": {"messages": [tool]}})[0]["name"] == "gobuster_scan"
    assert task_discovery._chunk_messages({"messages": [tool]})[0]["tool_call_id"] == "c1"


def test_flatten_error_unwraps_exception_group():
    inner = ValueError("Invalid 'tools': array too long. Expected 128, got 150")
    grouped = ExceptionGroup("unhandled errors in a TaskGroup (1 sub-exception)", [inner])
    msg = task_discovery.flatten_error(grouped)
    assert "array too long" in msg
    assert "TaskGroup" not in msg


@pytest.mark.asyncio
async def test_stub_stops_between_phases_when_cancelled(monkeypatch):
    monkeypatch.setenv("TASK_DISCOVERY_STUB_SLEEP", "0")
    settings = WorkerSettings(hexstrike_stub="1", llm_stub="1", target_allowlist="")
    fake = FakeReporter()
    fake.job_status = "running"
    gets = {"n": 0}

    async def get_job(job_id):
        gets["n"] += 1
        if gets["n"] > 2:
            return {"id": job_id, "status": "cancelled"}
        return {"id": job_id, "status": "running"}

    fake.get_job = get_job  # type: ignore[method-assign]
    monkeypatch.setattr("app.pipelines.task_discovery.ApiReporter", lambda settings=None: fake)

    await task_discovery.run(
        {
            "job_id": "j-cancel",
            "profile": "task-discovery",
            "target": "http://juice.lab:3000",
            "assets": [{"id": "a1", "hostname": "juice.lab", "ip_address": "10.0.0.1"}],
            "scans": [{"id": "s1", "asset_id": "a1"}],
            "allowlist": ["juice.lab"],
        },
        settings,
    )

    tools = [c[1]["tool_name"] for c in fake.calls if c[0] == "tool_run"]
    assert len(tools) < 6
    assert any(c[0] == "patch" and c[2].get("status") == "cancelled" for c in fake.calls)
    assert not any(c[0] == "patch" and c[2].get("status") == "completed" for c in fake.calls)


@pytest.mark.asyncio
async def test_cancel_running_unregisters_task():
    from app.job_runtime import RUNNING_JOBS, cancel_running, spawn

    started = asyncio.Event()

    async def slow() -> None:
        started.set()
        await asyncio.sleep(30)

    spawn("j-reg", slow(), target="juice.lab")
    await started.wait()
    assert cancel_running("j-reg") is True
    await asyncio.sleep(0.05)
    assert "j-reg" not in RUNNING_JOBS
