import pytest

from app.settings import WorkerSettings
from app.adapters import llm_client


def test_settings_load_model(monkeypatch):
    monkeypatch.setenv("LLM_MODEL", "gpt-test")
    monkeypatch.setenv("LLM_STUB", "1")
    from app.settings import get_settings

    get_settings.cache_clear()
    s = get_settings()
    assert s.llm_model == "gpt-test"
    assert s.stub_llm


@pytest.mark.asyncio
async def test_stub_skips_network():
    s = WorkerSettings(llm_stub="1", llm_model="m")
    text = await llm_client.complete("hello", s)
    assert "stub-llm" in text
