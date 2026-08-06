"""CAI chat worker routes — service token auth."""
from __future__ import annotations

import json
from typing import Annotated, Any
from uuid import UUID

from fastapi import APIRouter, Header, HTTPException, Query, status
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from app.adapters import cai_session as sess
from app.settings import get_settings

router = APIRouter(prefix="/cai", tags=["cai-chat"])


class CreateBody(BaseModel):
    user_id: str
    team: str = "red"
    task_id: str | None = None
    message: str | None = None


class MessageBody(BaseModel):
    content: str = Field(min_length=1)


def _require_token(x_service_token: str | None) -> None:
    settings = get_settings()
    expected = getattr(settings, "red_service_token", None) or getattr(settings, "blue_service_token", "")
    if not x_service_token or x_service_token != expected:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid service token")


@router.post("/sessions", status_code=201)
async def create_session(
    body: CreateBody,
    x_service_token: Annotated[str | None, Header(alias="X-Service-Token")] = None,
) -> dict[str, Any]:
    _require_token(x_service_token)
    settings = get_settings()
    session = await sess.get_registry().create(
        user_id=body.user_id,
        team=body.team,
        message=body.message,
        task_id=body.task_id,
        settings=settings,
        agent_type=settings.cai_agent_type,
    )
    return session.public()


@router.get("/sessions/{session_id}")
async def get_session(
    session_id: UUID,
    x_service_token: Annotated[str | None, Header(alias="X-Service-Token")] = None,
) -> dict[str, Any]:
    _require_token(x_service_token)
    session = await sess.get_registry().get(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    return session.public()


@router.post("/sessions/{session_id}/messages")
async def post_message(
    session_id: UUID,
    body: MessageBody,
    x_service_token: Annotated[str | None, Header(alias="X-Service-Token")] = None,
) -> dict[str, Any]:
    _require_token(x_service_token)
    try:
        session = await sess.get_registry().send_message(session_id, body.content)
    except KeyError:
        raise HTTPException(status_code=404, detail="Session not found") from None
    except RuntimeError as exc:
        code = 409 if "not running" in str(exc) else 400
        raise HTTPException(status_code=code, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return session.public()


@router.post("/sessions/{session_id}/stop")
async def stop_session(
    session_id: UUID,
    x_service_token: Annotated[str | None, Header(alias="X-Service-Token")] = None,
) -> dict[str, Any]:
    _require_token(x_service_token)
    try:
        session = await sess.get_registry().stop(session_id)
    except KeyError:
        raise HTTPException(status_code=404, detail="Session not found") from None
    return session.public()


@router.get("/sessions/{session_id}/events")
async def stream_events(
    session_id: UUID,
    after_seq: int = Query(0),
    x_service_token: Annotated[str | None, Header(alias="X-Service-Token")] = None,
):
    _require_token(x_service_token)
    registry = sess.get_registry()
    if not await registry.get(session_id):
        raise HTTPException(status_code=404, detail="Session not found")

    async def gen():
        try:
            async for ev in registry.events_after(session_id, after_seq):
                if ev.type == "status" and not ev.text:
                    yield ": keepalive\n\n"
                    continue
                payload = json.dumps(ev.as_dict())
                yield f"id: {ev.seq}\nevent: cai\ndata: {payload}\n\n"
                if ev.type == "ended":
                    break
        except KeyError:
            yield f"event: cai\ndata: {json.dumps({'type': 'error', 'text': 'gone'})}\n\n"

    return StreamingResponse(gen(), media_type="text/event-stream")
