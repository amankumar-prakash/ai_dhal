from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class WorkerSettings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    openai_api_key: str = ""
    llm_model: str = "gpt-4o-mini"
    llm_base_url: str = ""
    llm_stub: str = "1"
    api_base_url: str = "http://localhost:8000/api/v1"
    blue_service_token: str = "change-me-blue"
    demo_safe_mode: str = "1"
    target_allowlist: str = ""
    hexstrike_base_url: str = "http://host.docker.internal:8888"
    hexstrike_stub: str = "0"
    cai_workdir: str = ""
    cai_stub: str = "0"
    cai_chat_stub: str = "1"
    cai_agent_type: str = "bug_bounter_agent"

    @property
    def stub_llm(self) -> bool:
        return self.llm_stub.strip() in {"1", "true", "True", "yes"}

    @property
    def stub_hexstrike(self) -> bool:
        return self.hexstrike_stub.strip() in {"1", "true", "True", "yes"}

    @property
    def stub_cai(self) -> bool:
        return self.cai_stub.strip() in {"1", "true", "True", "yes"}

    @property
    def stub_cai_chat(self) -> bool:
        return self.cai_chat_stub.strip() in {"1", "true", "True", "yes"}

    def require_llm_for_live(self) -> None:
        if not self.stub_llm and not self.openai_api_key:
            raise RuntimeError("OPENAI_API_KEY required when LLM_STUB is not enabled")


@lru_cache
def get_settings() -> WorkerSettings:
    return WorkerSettings()
