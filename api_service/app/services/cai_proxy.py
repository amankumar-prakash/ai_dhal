"""Proxy CAI chat calls to red/blue workers."""
from __future__ import annotations

from typing import Any, AsyncIterator
from uuid import UUID

import httpx
from fastapi import HTTPException, status

from app.config import Settings, get_settings


def _worker(team: str, settings: Settings) -> tuple[str, str]:
    if team == "red":
        return settings.red_worker_url.rstrip("/"), settings.red_service_token
    if team == "blue":
        return settings.blue_worker_url.rstrip("/"), settings.blue_service_token
    raise HTTPException(status_code=400, detail="Invalid team")


async def create_session(
    *,
    team: str,
    user_id: str,
    message: str | None,
    task_id: str | None,
    settings: Settings | None = None,
) -> dict[str, Any]:
    settings = settings or get_settings()
    base, token = _worker(team, settings)
    async with httpx.AsyncClient(timeout=60.0) as client:
        r = await client.post(
            f"{base}/cai/sessions",
            headers={"X-Service-Token": token},
            json={"user_id": user_id, "team": team, "message": message, "task_id": task_id},
        )
    if r.status_code >= 400:
        raise HTTPException(status_code=r.status_code, detail=r.text)
    return r.json()


async def get_session(team: str, session_id: UUID, settings: Settings | None = None) -> dict[str, Any]:
    settings = settings or get_settings()
    base, token = _worker(team, settings)
    async with httpx.AsyncClient(timeout=30.0) as client:
        r = await client.get(f"{base}/cai/sessions/{session_id}", headers={"X-Service-Token": token})
    if r.status_code >= 400:
        raise HTTPException(status_code=r.status_code, detail=r.text)
    return r.json()


async def post_message(
    team: str, session_id: UUID, content: str, settings: Settings | None = None
) -> dict[str, Any]:
    settings = settings or get_settings()
    base, token = _worker(team, settings)
    async with httpx.AsyncClient(timeout=60.0) as client:
        r = await client.post(
            f"{base}/cai/sessions/{session_id}/messages",
            headers={"X-Service-Token": token},
            json={"content": content},
        )
    if r.status_code >= 400:
        raise HTTPException(status_code=r.status_code, detail=r.text)
    return r.json()


async def stop_session(team: str, session_id: UUID, settings: Settings | None = None) -> dict[str, Any]:
    settings = settings or get_settings()
    base, token = _worker(team, settings)
    async with httpx.AsyncClient(timeout=60.0) as client:
        r = await client.post(
            f"{base}/cai/sessions/{session_id}/stop",
            headers={"X-Service-Token": token},
        )
    if r.status_code >= 400:
        raise HTTPException(status_code=r.status_code, detail=r.text)
    return r.json()


async def stream_events(
    team: str, session_id: UUID, after_seq: int = 0, settings: Settings | None = None
) -> AsyncIterator[bytes]:
    settings = settings or get_settings()
    base, token = _worker(team, settings)
    async with httpx.AsyncClient(timeout=None) as client:
        async with client.stream(
            "GET",
            f"{base}/cai/sessions/{session_id}/events",
            params={"after_seq": after_seq},
            headers={"X-Service-Token": token},
        ) as resp:
            if resp.status_code >= 400:
                body = await resp.aread()
                raise HTTPException(status_code=resp.status_code, detail=body.decode(errors="replace"))
            async for chunk in resp.aiter_bytes():
                yield chunk
