from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class WorkerSettings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    openai_api_key: str = ""
    llm_model: str = "gpt-4o-mini"
    llm_base_url: str = ""
    llm_stub: str = "1"
    api_base_url: str = "http://localhost:8000/api/v1"
    red_service_token: str = "change-me-red"
    demo_safe_mode: str = "1"
    target_allowlist: str = ""
    hexstrike_base_url: str = "http://localhost:8005"
    hexstrike_mcp_script: str = ""
    hexstrike_stub: str = "0"

    # Orchestration / token budget
    artifact_root: str = "/tmp/ai_dhal/jobs"
    llmlingua_model: str = "microsoft/llmlingua-2-bert-base-multilingual-cased-meetingbank"
    llmlingua_device: str = "cpu"
    llmlingua_enabled: str = "1"
    tool_summary_tokens: int = 800
    phase_rollup_tokens: int = 1500
    job_context_tokens: int = 3000
    max_tools_per_job: int = 24
    max_tools_per_phase: int = 8
    max_phase_loops: int = 2
    # 0 = no job wall timeout (run until phases finish or the job is cancelled)
    orchestration_timeout_seconds: int = 0

    @property
    def stub_llm(self) -> bool:
        return self.llm_stub.strip() in {"1", "true", "True", "yes"}

    @property
    def stub_hexstrike(self) -> bool:
        return self.hexstrike_stub.strip() in {"1", "true", "True", "yes"}

    @property
    def use_llmlingua(self) -> bool:
        return self.llmlingua_enabled.strip() in {"1", "true", "True", "yes"}

    def require_llm_for_live(self) -> None:
        if not self.stub_llm and not self.openai_api_key:
            raise RuntimeError("OPENAI_API_KEY required when LLM_STUB is not enabled")


@lru_cache
def get_settings() -> WorkerSettings:
    return WorkerSettings()
