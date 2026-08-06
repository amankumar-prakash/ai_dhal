"""Supabase client for api_service — elevated secret key only (never expose to UI)."""
from __future__ import annotations

from functools import lru_cache

from supabase import Client, create_client

from app.config import Settings, get_settings


@lru_cache
def get_supabase(settings: Settings | None = None) -> Client:
    settings = settings or get_settings()
    key = settings.elevated_key()
    if not settings.supabase_url or not key:
        raise RuntimeError(
            "SUPABASE_URL and SUPABASE_SECRET_KEY (or SUPABASE_SERVICE_ROLE_KEY) "
            "required when API_STORE=supabase"
        )
    return create_client(settings.supabase_url, key)


def clear_supabase_cache() -> None:
    get_supabase.cache_clear()
