"""Model context-window lookup and 80% LLMLingua trigger."""
from __future__ import annotations

from app.main import health
from app.orchestration.model_context import (
    compress_trigger_tokens,
    context_window_for,
    llm_budget,
    lookup_context_window,
)
from app.settings import WorkerSettings, get_settings


def test_gpt4o_mini_window_and_trigger() -> None:
    settings = WorkerSettings(llm_model="gpt-4o-mini", llm_context_window=0)
    assert lookup_context_window("gpt-4o-mini") == 128_000
    assert lookup_context_window("gpt-4o-mini-2024-07-18") == 128_000
    assert context_window_for(settings) == 128_000
    assert compress_trigger_tokens(settings) == 102_400
    budget = llm_budget(settings, reserved_tokens=400)
    assert budget["window"] == 128_000
    assert budget["trigger"] == 102_400
    assert budget["remaining"] == 102_000


def test_llm_context_window_override_wins() -> None:
    settings = WorkerSettings(llm_model="gpt-4o-mini", llm_context_window=8_000)
    assert context_window_for(settings) == 8_000
    assert compress_trigger_tokens(settings) == 6_400


def test_unknown_model_falls_back_without_crash() -> None:
    settings = WorkerSettings(llm_model="not-a-real-model-xyz", llm_context_window=0)
    assert lookup_context_window("not-a-real-model-xyz") is None
    assert context_window_for(settings) == 128_000
    budget = llm_budget(settings)
    assert budget["trigger"] == 102_400
    assert budget["remaining"] >= 1


def test_prefix_windows() -> None:
    assert lookup_context_window("gpt-4.1-mini") == 1_047_576
    assert lookup_context_window("gpt-4o") == 128_000
    assert lookup_context_window("gpt-3.5-turbo") == 16_385
    assert lookup_context_window("o3-mini") == 200_000
    assert lookup_context_window("gpt-5.6-luna") == 256_000


def test_health_exposes_window_and_trigger(monkeypatch) -> None:
    monkeypatch.setenv("LLM_MODEL", "gpt-4o-mini")
    monkeypatch.setenv("LLM_CONTEXT_WINDOW", "0")
    get_settings.cache_clear()
    payload = health()
    assert payload["llm_model"] == "gpt-4o-mini"
    assert payload["llm_context_window"] == 128_000
    assert payload["compress_trigger_tokens"] == 102_400
    get_settings.cache_clear()
