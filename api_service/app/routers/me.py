"""GET /me — role + profile + tool unlock from DB."""
from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends

from app.deps import Principal, require_jwt
from app.schemas.models import MeResponse, ProfileOut
from app.services import identity
from app.services import notifications as notif_svc

router = APIRouter(prefix="/me", tags=["me"])


@router.get("", response_model=MeResponse)
def get_me(principal: Principal = Depends(require_jwt)) -> MeResponse:
    assert principal.user_id
    uid = UUID(principal.user_id)
    profile = identity.get_profile(uid)
    unlock = identity.tool_unlock_for(uid, principal.role or "user")
    profile_out = None
    if profile:
        cleaned = {k: profile.get(k) for k in ProfileOut.model_fields}
        cleaned["id"] = profile.get("id") or uid
        profile_out = ProfileOut.model_validate(cleaned)
    return MeResponse(
        user_id=uid,
        email=principal.email or (profile.get("email") if profile else None),
        role=principal.role or "user",  # type: ignore[arg-type]
        profile=profile_out,
        tool_unlock=unlock,
    )


@router.get("/notifications")
def my_notifications(principal: Principal = Depends(require_jwt)):
    assert principal.user_id
    return notif_svc.list_for_user(UUID(principal.user_id))
