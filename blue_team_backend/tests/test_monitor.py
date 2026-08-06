import pytest

from app.pipelines import monitor
from app.reporters.api_reporter import ApiReporter


@pytest.mark.asyncio
async def test_monitor_emits_event(monkeypatch):
    calls = []

    class Fake(ApiReporter):
        async def post_threat_event(self, payload):
            calls.append(payload)
            return {"id": "e1"}

        async def patch_job(self, job_id, **fields):
            calls.append({"job": job_id, **fields})

    monkeypatch.setattr("app.pipelines.monitor.ApiReporter", Fake)
    monkeypatch.setattr(
        "app.pipelines.monitor.llm_client.complete",
        lambda prompt: __import__("asyncio").coroutine(lambda: "note")(),
    )

    async def fake_complete(prompt):
        return "monitor note"

    monkeypatch.setattr("app.pipelines.monitor.llm_client.complete", fake_complete)
    await monitor.run({"job_id": "jm"})
    assert any(isinstance(c, dict) and c.get("technique") == "T1078" for c in calls)
