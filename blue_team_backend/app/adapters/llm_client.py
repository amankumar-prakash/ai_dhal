from __future__ import annotations

import httpx

from app.settings import WorkerSettings, get_settings


async def complete(prompt: str, settings: WorkerSettings | None = None) -> str:
    settings = settings or get_settings()
    if settings.stub_llm:
        return f"[stub-llm:{settings.llm_model}] {prompt[:200]}"
    settings.require_llm_for_live()
    base = (settings.llm_base_url or "https://api.openai.com/v1").rstrip("/")
    async with httpx.AsyncClient(timeout=60.0) as client:
        resp = await client.post(
            f"{base}/chat/completions",
            headers={"Authorization": f"Bearer {settings.openai_api_key}"},
            json={
                "model": settings.llm_model,
                "messages": [{"role": "user", "content": prompt}],
            },
        )
        resp.raise_for_status()
        return resp.json()["choices"][0]["message"]["content"]
