"""task-discovery stub emits per-phase tool runs, findings, and patches; live fails closed."""
from __future__ import annotations

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


@pytest.mark.asyncio
async def test_stub_emits_tool_finding_and_patch_per_phase(monkeypatch):
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
    assert names == {
        "server_health",
        "nmap_scan",
        "execute_command",
        "nuclei_scan",
        "gobuster_scan",
        "katana_crawl",
        "feroxbuster_scan",
    }
    assert len(selected) <= 128


def test_flatten_error_unwraps_exception_group():
    inner = ValueError("Invalid 'tools': array too long. Expected 128, got 150")
    grouped = ExceptionGroup("unhandled errors in a TaskGroup (1 sub-exception)", [inner])
    msg = task_discovery.flatten_error(grouped)
    assert "array too long" in msg
    assert "TaskGroup" not in msg
