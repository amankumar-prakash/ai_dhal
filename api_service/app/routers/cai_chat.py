"""CAI chat API — JWT + tool unlock, proxy to workers."""
from __future__ import annotations

from typing import Literal
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import StreamingResponse

from app.deps import Principal, PrincipalKind, require_jwt
from app.schemas.models import CaiMessageCreate, CaiSessionCreate, CaiSessionOut
from app.services import cai_proxy, identity

router = APIRouter(prefix="/cai", tags=["cai-chat"])

# In-memory map session_id -> team for get/message/stop without client sending team
_SESSION_TEAM: dict[str, str] = {}


def _require_tool_access(principal: Principal, team: Literal["red", "blue"]) -> None:
    if principal.kind in (PrincipalKind.admin, PrincipalKind.user):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Tool chat denied for this role")
    if principal.kind == PrincipalKind.security_manager:
        return
    if principal.kind != PrincipalKind.security_analyst or not principal.user_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Analyst or Manager required")
    unlock = identity.tool_unlock_for(UUID(principal.user_id), principal.role or "user")
    if not unlock.get(team):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=f"No {team} tool unlock")


@router.post("/sessions", response_model=CaiSessionOut, status_code=201)
async def create_session(body: CaiSessionCreate, principal: Principal = Depends(require_jwt)):
    assert principal.user_id
    _require_tool_access(principal, body.team)
    if body.message is not None and not body.message.strip():
        raise HTTPException(status_code=400, detail="message must be non-empty when provided")
    data = await cai_proxy.create_session(
        team=body.team,
        user_id=principal.user_id,
        message=body.message,
        task_id=str(body.task_id) if body.task_id else None,
    )
    _SESSION_TEAM[str(data["id"])] = body.team
    return data


@router.get("/sessions/{session_id}", response_model=CaiSessionOut)
async def get_session(
    session_id: UUID,
    team: Literal["red", "blue"] | None = Query(None),
    principal: Principal = Depends(require_jwt),
):
    resolved = _SESSION_TEAM.get(str(session_id)) or team
    if not resolved:
        raise HTTPException(status_code=404, detail="Session not found")
    _SESSION_TEAM[str(session_id)] = resolved
    _require_tool_access(principal, resolved)
    return await cai_proxy.get_session(resolved, session_id)


@router.post("/sessions/{session_id}/messages", response_model=CaiSessionOut)
async def post_message(
    session_id: UUID,
    body: CaiMessageCreate,
    team: Literal["red", "blue"] | None = Query(None),
    principal: Principal = Depends(require_jwt),
):
    resolved = _SESSION_TEAM.get(str(session_id)) or team
    if not resolved:
        raise HTTPException(status_code=404, detail="Session not found")
    _SESSION_TEAM[str(session_id)] = resolved
    _require_tool_access(principal, resolved)
    if not body.content.strip():
        raise HTTPException(status_code=400, detail="empty content")
    return await cai_proxy.post_message(resolved, session_id, body.content)


@router.post("/sessions/{session_id}/stop", response_model=CaiSessionOut)
async def stop_session(
    session_id: UUID,
    team: Literal["red", "blue"] | None = Query(None),
    principal: Principal = Depends(require_jwt),
):
    resolved = _SESSION_TEAM.get(str(session_id)) or team
    if not resolved:
        raise HTTPException(status_code=404, detail="Session not found")
    _SESSION_TEAM[str(session_id)] = resolved
    _require_tool_access(principal, resolved)
    return await cai_proxy.stop_session(resolved, session_id)


@router.get("/sessions/{session_id}/events")
async def stream_events(
    session_id: UUID,
    after_seq: int = Query(0),
    team: Literal["red", "blue"] | None = Query(None),
    principal: Principal = Depends(require_jwt),
):
    resolved = _SESSION_TEAM.get(str(session_id)) or team
    if not resolved:
        raise HTTPException(status_code=404, detail="Session not found")
    _SESSION_TEAM[str(session_id)] = resolved
    _require_tool_access(principal, resolved)

    async def gen():
        async for chunk in cai_proxy.stream_events(resolved, session_id, after_seq):
            yield chunk

    return StreamingResponse(gen(), media_type="text/event-stream")
