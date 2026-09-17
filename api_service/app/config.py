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
    test_username: str = ""
    test_password: str = ""
    test_manager_username: str = ""
    test_manager_password: str = ""

    # CR-05: configurable callback URL so workers can reach us in any deployment
    # (Docker, Kubernetes, Vast.ai) — must be the URL workers can resolve.
    api_callback_url: str = "http://127.0.0.1:8000/api/v1"

    # CR-18: promote Vast.ai NAT-rewrite env vars into structured settings so
    # they are documented, typed, and testable without os.environ.get() sprinkled
    # across service files.
    public_ipaddr: str = ""          # PUBLIC_IPADDR
    vast_tcp_port_10200: str = ""    # Juice Shop external port for NAT rewrite
    vast_tcp_port_10100: str = ""    # UI external port for CORS origins

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
