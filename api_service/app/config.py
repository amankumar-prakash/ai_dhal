"""API service configuration — DB credentials live only here."""
from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    api_store: str = "supabase"  # supabase (primary) | memory (offline/tests)
    database_url: str = ""
    supabase_url: str = ""
    supabase_secret_key: str = ""
    supabase_service_role_key: str = ""  # legacy alias
    supabase_jwks_url: str = ""  # optional override
    supabase_jwt_secret: str = ""  # deprecated HS256 fallback only
    red_service_token: str = "change-me-red"
    blue_service_token: str = "change-me-blue"
    red_worker_url: str = "http://localhost:8001"
    blue_worker_url: str = "http://localhost:8002"

    def elevated_key(self) -> str:
        return (self.supabase_secret_key or self.supabase_service_role_key or "").strip()

    def jwks_url(self) -> str:
        if self.supabase_jwks_url.strip():
            return self.supabase_jwks_url.strip()
        base = self.supabase_url.rstrip("/")
        if not base:
            return ""
        return f"{base}/auth/v1/.well-known/jwks.json"


@lru_cache
def get_settings() -> Settings:
    return Settings()
