"""CAI chat API — JWT + tool unlock, proxy to workers."""
from __future__ import annotations

import threading
from collections import OrderedDict
from typing import Literal
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse

from app.deps import Principal, require_jwt
from app.schemas.models import CaiMessageCreate, CaiSessionCreate, CaiSessionOut
from app.services import cai_proxy

router = APIRouter(prefix="/cai", tags=["cai-chat"])

# CR-03 FIX: Bounded, thread-safe LRU mapping of session_id → team.
# Replaces the previous unbounded dict that grew forever and was never evicted.
# Capacity: 5 000 sessions (~= worst-case concurrent lab users).  When the cap
# is hit the oldest session mapping is evicted (LRU via OrderedDict).
_SESSION_TEAM_MAX = 5_000
_SESSION_TEAM: OrderedDict[str, str] = OrderedDict()
_SESSION_TEAM_LOCK = threading.Lock()


def _team_set(session_id: str, team: str) -> None:
    """Store session→team mapping with LRU eviction at capacity."""
    with _SESSION_TEAM_LOCK:
        if session_id in _SESSION_TEAM:
            _SESSION_TEAM.move_to_end(session_id)
        else:
            _SESSION_TEAM[session_id] = team
            if len(_SESSION_TEAM) > _SESSION_TEAM_MAX:
                _SESSION_TEAM.popitem(last=False)  # evict oldest
        _SESSION_TEAM[session_id] = team


def _team_get(session_id: str) -> str | None:
    """Retrieve team for a session_id (None if unknown)."""
    return _SESSION_TEAM.get(session_id)


def _clear_session_team() -> None:
    """Reset the session map — called by tests to ensure isolation."""
    with _SESSION_TEAM_LOCK:
        _SESSION_TEAM.clear()


@router.post("/sessions", response_model=CaiSessionOut, status_code=201)
async def create_session(body: CaiSessionCreate, principal: Principal = Depends(require_jwt)):
    # CR-02 FIX: replaced bare assert with explicit HTTPException.
    if not principal.user_id:
        raise HTTPException(status_code=400, detail="Principal must carry a user_id")
    if body.message is not None and not body.message.strip():
        raise HTTPException(status_code=400, detail="message must be non-empty when provided")
    data = await cai_proxy.create_session(
        team=body.team,
        user_id=principal.user_id,
        message=body.message,
        task_id=str(body.task_id) if body.task_id else None,
    )
    _team_set(str(data["id"]), body.team)
    return data


@router.get("/sessions/{session_id}", response_model=CaiSessionOut)
async def get_session(
    session_id: UUID,
    team: Literal["red", "blue"] | None = Query(None),
    principal: Principal = Depends(require_jwt),
):
    resolved = _team_get(str(session_id)) or team
    if not resolved:
        raise HTTPException(status_code=404, detail="Session not found")
    _team_set(str(session_id), resolved)
    return await cai_proxy.get_session(resolved, session_id)


@router.post("/sessions/{session_id}/messages", response_model=CaiSessionOut)
async def post_message(
    session_id: UUID,
    body: CaiMessageCreate,
    team: Literal["red", "blue"] | None = Query(None),
    principal: Principal = Depends(require_jwt),
):
    resolved = _team_get(str(session_id)) or team
    if not resolved:
        raise HTTPException(status_code=404, detail="Session not found")
    _team_set(str(session_id), resolved)
    if not body.content.strip():
        raise HTTPException(status_code=400, detail="empty content")
    return await cai_proxy.post_message(resolved, session_id, body.content)


@router.post("/sessions/{session_id}/stop", response_model=CaiSessionOut)
async def stop_session(
    session_id: UUID,
    team: Literal["red", "blue"] | None = Query(None),
    principal: Principal = Depends(require_jwt),
):
    resolved = _team_get(str(session_id)) or team
    if not resolved:
        raise HTTPException(status_code=404, detail="Session not found")
    _team_set(str(session_id), resolved)
    return await cai_proxy.stop_session(resolved, session_id)


@router.get("/sessions/{session_id}/events")
async def stream_events(
    session_id: UUID,
    after_seq: int = Query(0),
    team: Literal["red", "blue"] | None = Query(None),
    principal: Principal = Depends(require_jwt),
):
    resolved = _team_get(str(session_id)) or team
    if not resolved:
        raise HTTPException(status_code=404, detail="Session not found")
    _team_set(str(session_id), resolved)

    async def gen():
        async for chunk in cai_proxy.stream_events(resolved, session_id, after_seq):
            yield chunk

    return StreamingResponse(gen(), media_type="text/event-stream")
