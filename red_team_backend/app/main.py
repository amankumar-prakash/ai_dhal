from fastapi import FastAPI

from app.routers.jobs import router as jobs_router
from app.routers.cai_chat import router as cai_chat_router
from app.routers.hexstrike_test import router as hexstrike_test_router
from app.settings import get_settings

app = FastAPI(title="Red Team Backend", version="0.1.0")
app.include_router(jobs_router)
app.include_router(cai_chat_router)
app.include_router(hexstrike_test_router)


@app.get("/health")
def health():
    s = get_settings()
    return {
        "status": "ok",
        "llm_model": s.llm_model,
        "llm_stub": s.stub_llm,
        "cai_stub": s.stub_cai,
        "cai_chat_stub": s.stub_cai_chat,
        "cai_workdir": s.cai_workdir or "(not set)",
    }


@app.get("/ready")
def ready():
    s = get_settings()
    if not s.stub_llm and not s.openai_api_key:
        return {"status": "not_ready", "reason": "OPENAI_API_KEY missing"}
    return {"status": "ready"}

