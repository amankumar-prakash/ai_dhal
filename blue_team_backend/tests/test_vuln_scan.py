import pytest

from app.pipelines import vuln_scan
from app.reporters.api_reporter import ApiReporter


@pytest.mark.asyncio
async def test_vuln_scan_calls_reporter(monkeypatch):
    calls = []

    class Fake(ApiReporter):
        async def patch_job(self, job_id, **fields):
            calls.append(("patch", job_id, fields))

        async def post_finding(self, payload):
            calls.append(("finding", payload))
            return {"id": "f1"}

        async def post_tool_run(self, payload):
            calls.append(("tool_run", payload))

        async def post_patch(self, payload):
            calls.append(("patch_row", payload))
            return {"id": "p1"}

    monkeypatch.setattr("app.pipelines.vuln_scan.ApiReporter", Fake)
    await vuln_scan.run(
        {
            "job_id": "j1",
            "assets": [{"id": "a1", "hostname": "h.local", "name": "h"}],
        }
    )
    assert any(c[0] == "finding" for c in calls)
    assert any(c[0] == "patch_row" for c in calls)
