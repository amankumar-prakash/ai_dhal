"""Select memory or supabase store based on API_STORE."""
from __future__ import annotations

from types import ModuleType

from app.config import get_settings


def get_store() -> ModuleType:
    settings = get_settings()
    mode = (settings.api_store or "supabase").strip().lower()
    if mode == "memory":
        from app.db import memory

        return memory
    from app.db import supabase_store

    return supabase_store
