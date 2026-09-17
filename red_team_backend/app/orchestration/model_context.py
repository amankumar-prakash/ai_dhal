"""Resolve chat-model context windows and the 80% LLMLingua-2 trigger."""
from __future__ import annotations

import logging
from functools import lru_cache
from typing import Any

from app.settings import WorkerSettings

log = logging.getLogger(__name__)

DEFAULT_CONTEXT_WINDOW = 128_000

# Longest prefix wins. Values are published context windows (tokens).
_CONTEXT_WINDOWS: tuple[tuple[str, int], ...] = (
    ("gpt-4.1", 1_047_576),
    ("gpt-4o-mini", 128_000),
    ("gpt-4-turbo", 128_000),
    ("gpt-4o", 128_000),
    ("gpt-3.5-turbo", 16_385),
    ("gpt-5", 256_000),
    ("o1", 200_000),
    ("o3", 200_000),
    ("o4", 200_000),
)


def _normalized_model(name: str) -> str:
    return (name or "").strip().lower()


def lookup_context_window(model_name: str) -> int | None:
    """Return a known context window for `model_name`, or None if unknown."""
    name = _normalized_model(model_name)
    if not name:
        return None
    matches = [(prefix, window) for prefix, window in _CONTEXT_WINDOWS if name.startswith(prefix)]
    if not matches:
        return None
    matches.sort(key=lambda item: len(item[0]), reverse=True)
    return matches[0][1]


def context_window_for(settings: WorkerSettings) -> int:
    """Resolved window: explicit override, then lookup, then 128k fallback."""
    override = int(settings.llm_context_window or 0)
    if override > 0:
        return override
    found = lookup_context_window(settings.llm_model)
    if found is not None:
        return found
    log.warning(
        "Unknown LLM_MODEL %r; falling back to %s-token context window "
        "(set LLM_CONTEXT_WINDOW to override)",
        settings.llm_model,
        DEFAULT_CONTEXT_WINDOW,
    )
    return DEFAULT_CONTEXT_WINDOW


def compress_trigger_tokens(settings: WorkerSettings, window: int | None = None) -> int:
    window = window if window is not None else context_window_for(settings)
    ratio = float(settings.llm_compress_trigger_ratio or 0.8)
    if ratio <= 0 or ratio > 1:
        ratio = 0.8
    return max(1, int(window * ratio))


def llm_budget(settings: WorkerSettings, reserved_tokens: int = 0) -> dict[str, Any]:
    window = context_window_for(settings)
    trigger = compress_trigger_tokens(settings, window)
    reserved = max(0, int(reserved_tokens or 0))
    remaining = max(1, trigger - reserved)
    return {
        "model": settings.llm_model,
        "window": window,
        "trigger": trigger,
        "reserved": reserved,
        "remaining": remaining,
        "ratio": float(settings.llm_compress_trigger_ratio or 0.8),
    }


@lru_cache(maxsize=8)
def _encoding(model: str = ""):
    try:
        import tiktoken
    except ImportError:
        return None
    name = (model or "").strip()
    if name:
        try:
            return tiktoken.encoding_for_model(name)
        except KeyError:
            pass
    for enc_name in ("o200k_base", "cl100k_base"):
        try:
            return tiktoken.get_encoding(enc_name)
        except Exception:  # noqa: BLE001
            continue
    return None


def count_tokens(text: str, model: str = "") -> int:
    if not text:
        return 0
    enc = _encoding(model)
    if enc is not None:
        return len(enc.encode(text))
    return max(1, len(text) // 4)


def cut_to_tokens(text: str, cap: int, model: str = "") -> str:
    original = text or ""
    if cap <= 0:
        return ""
    if count_tokens(original, model) <= cap:
        return original
    enc = _encoding(model)
    if enc is not None:
        ids = enc.encode(original)
        return enc.decode(ids[:cap])
    return original[: max(0, cap * 4)]


def split_token_chunks(text: str, chunk_tokens: int, model: str = "") -> list[str]:
    if not text:
        return []
    size = max(1, int(chunk_tokens or 1))
    enc = _encoding(model)
    if enc is not None:
        ids = enc.encode(text)
        return [enc.decode(ids[i : i + size]) for i in range(0, len(ids), size)]
    char_size = size * 4
    return [text[i : i + char_size] for i in range(0, len(text), char_size)]


def tool_schema_text(tool: Any) -> str:
    """Approximate token source for a bound tool schema (name + description + args)."""
    parts = [str(getattr(tool, "name", "") or ""), str(getattr(tool, "description", "") or "")]
    schema = getattr(tool, "args_schema", None)
    if schema is not None:
        for attr in ("model_json_schema", "schema"):
            fn = getattr(schema, attr, None)
            if not callable(fn):
                continue
            try:
                import json

                parts.append(json.dumps(fn(), default=str))
                break
            except Exception:  # noqa: BLE001
                continue
    return "\n".join(p for p in parts if p)
