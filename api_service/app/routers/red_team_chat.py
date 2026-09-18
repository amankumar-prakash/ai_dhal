"""Red-team supervised chat API — JWT auth, proxy to workers."""
from __future__ import annotations

from typing import Literal
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import PlainTextResponse, StreamingResponse

from app.deps import Principal, require_jwt
from app.schemas.models import (
    RedTeamChatDecision,
    RedTeamChatMessageCreate,
    RedTeamChatSessionCreate,
    RedTeamChatSessionOut,
)
from app.services import red_team_chat_proxy as proxy

router = APIRouter(prefix="/red-team-chat", tags=["red-team-chat"])

# In-memory map session_id -> team so message/stop/decision don't need the client to resend team.
_SESSION_TEAM: dict[str, str] = {}


def _resolve_team(session_id: UUID, team: str | None) -> str:
    resolved = _SESSION_TEAM.get(str(session_id)) or team
    if not resolved:
        raise HTTPException(status_code=404, detail="Session not found")
    _SESSION_TEAM[str(session_id)] = resolved
    return resolved


@router.post("/sessions", response_model=RedTeamChatSessionOut, status_code=201)
async def create_session(body: RedTeamChatSessionCreate, principal: Principal = Depends(require_jwt)):
    assert principal.user_id
    if body.message is not None and not body.message.strip():
        raise HTTPException(status_code=400, detail="message must be non-empty when provided")
    data = await proxy.create_session(
        team=body.team,
        user_id=principal.user_id,
        message=body.message,
        task_id=str(body.task_id) if body.task_id else None,
        target=body.target.strip() if body.target else None,
    )
    _SESSION_TEAM[str(data["id"])] = body.team
    return data


@router.get("/sessions/{session_id}", response_model=RedTeamChatSessionOut)
async def get_session(
    session_id: UUID,
    team: Literal["red", "blue"] | None = Query(None),
    principal: Principal = Depends(require_jwt),
):
    resolved = _resolve_team(session_id, team)
    return await proxy.get_session(resolved, session_id)


@router.post("/sessions/{session_id}/messages", response_model=RedTeamChatSessionOut)
async def post_message(
    session_id: UUID,
    body: RedTeamChatMessageCreate,
    team: Literal["red", "blue"] | None = Query(None),
    principal: Principal = Depends(require_jwt),
):
    resolved = _resolve_team(session_id, team)
    if not body.content.strip():
        raise HTTPException(status_code=400, detail="empty content")
    return await proxy.post_message(resolved, session_id, body.content)


@router.post("/sessions/{session_id}/tool-calls/{call_id}/decision", response_model=RedTeamChatSessionOut)
async def decide_tool_call(
    session_id: UUID,
    call_id: str,
    body: RedTeamChatDecision,
    team: Literal["red", "blue"] | None = Query(None),
    principal: Principal = Depends(require_jwt),
):
    resolved = _resolve_team(session_id, team)
    return await proxy.decide_tool_call(resolved, session_id, call_id, body.decision, body.reason)


@router.post("/sessions/{session_id}/stop", response_model=RedTeamChatSessionOut)
async def stop_session(
    session_id: UUID,
    team: Literal["red", "blue"] | None = Query(None),
    principal: Principal = Depends(require_jwt),
):
    resolved = _resolve_team(session_id, team)
    return await proxy.stop_session(resolved, session_id)


@router.get("/sessions/{session_id}/summary")
async def session_summary(
    session_id: UUID,
    team: Literal["red", "blue"] | None = Query(None),
    principal: Principal = Depends(require_jwt),
):
    resolved = _resolve_team(session_id, team)
    markdown = await proxy.get_summary(resolved, session_id)
    return PlainTextResponse(markdown, media_type="text/markdown")


@router.get("/sessions/{session_id}/events")
async def stream_events(
    session_id: UUID,
    after_seq: int = Query(0),
    team: Literal["red", "blue"] | None = Query(None),
    principal: Principal = Depends(require_jwt),
):
    resolved = _resolve_team(session_id, team)

    async def gen():
        async for chunk in proxy.stream_events(resolved, session_id, after_seq):
            yield chunk

    return StreamingResponse(gen(), media_type="text/event-stream")
