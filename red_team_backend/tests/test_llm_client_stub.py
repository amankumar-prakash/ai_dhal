import pytest

from app.adapters import cai_client, llm_client
from app.settings import WorkerSettings


@pytest.mark.asyncio
async def test_llm_client_stub_no_network():
    s = WorkerSettings(llm_stub="1", llm_model="stub-model")
    out = await llm_client.complete("deep plan", s)
    assert "stub-llm:stub-model" in out


@pytest.mark.asyncio
async def test_cai_plan_uses_stub():
    s = WorkerSettings(llm_stub="1", llm_model="stub-model")
    plan = await cai_client.plan_chain({"job_id": "abc", "profile": "deep-emulation"}, s)
    assert "stages" in plan
    assert plan["source"] == "cai-stub"
