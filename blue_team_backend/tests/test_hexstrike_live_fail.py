"""With HEXSTRIKE_STUB off and an unreachable base URL, live calls must fail closed."""
import pytest

from app.adapters import hexstrike_client
from app.pipelines import vuln_scan
from app.reporters.api_reporter import ApiReporter
from app.settings import WorkerSettings

UNREACHABLE_BASE_URL = "http://127.0.0.1:1"


@pytest.mark.asyncio
async def test_run_vuln_scan_raises_when_live_and_unreachable():
    settings = WorkerSettings(hexstrike_stub="0", hexstrike_base_url=UNREACHABLE_BASE_URL, llm_stub="1")
    with pytest.raises(RuntimeError):
        await hexstrike_client.run_vuln_scan("lab.local", settings=settings)


@pytest.mark.asyncio
async def test_vuln_scan_marks_job_failed_when_live_hexstrike_unreachable(monkeypatch):
    settings = WorkerSettings(
        hexstrike_stub="0",
        hexstrike_base_url=UNREACHABLE_BASE_URL,
        llm_stub="1",
        blue_service_token="tok",
    )
    calls = []

    class Fake(ApiReporter):
        async def patch_job(self, job_id, **fields):
            calls.append(("patch", job_id, fields))

        async def post_tool_run(self, payload):
            calls.append(("tool_run", payload))

        async def post_finding(self, payload):
            calls.append(("finding", payload))

    monkeypatch.setattr("app.pipelines.vuln_scan.ApiReporter", Fake)

    with pytest.raises(RuntimeError):
        await vuln_scan.run(
            {"job_id": "j1", "assets": [{"id": "a1", "hostname": "h.local", "name": "h"}]},
            settings,
        )

    failed_patches = [c for c in calls if c[0] == "patch" and c[2].get("status") == "failed"]
    assert failed_patches, "expected job to be patched to failed status on live hexstrike failure"
