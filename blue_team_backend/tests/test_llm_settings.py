import pytest

from app.settings import WorkerSettings, get_settings
from app.adapters import llm_client


def test_blue_llm_settings(monkeypatch):
    monkeypatch.setenv("LLM_MODEL", "blue-model")
    monkeypatch.setenv("LLM_STUB", "1")
    get_settings.cache_clear()
    assert get_settings().llm_model == "blue-model"


@pytest.mark.asyncio
async def test_blue_stub():
    text = await llm_client.complete("x", WorkerSettings(llm_stub="1", llm_model="m"))
    assert "stub-llm" in text
