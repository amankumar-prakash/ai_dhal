"""Admin user provision via Supabase Auth Admin API."""
from __future__ import annotations

import secrets
from datetime import datetime, timedelta, timezone
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, HTTPException, status

from app.config import get_settings
from app.deps import Principal, require_admin
from app.schemas.models import AdminUserCreate, AdminUserPatch
from app.services import identity

router = APIRouter(prefix="/admin/users", tags=["admin-users"])


def _temp_password() -> str:
    return secrets.token_urlsafe(16)


def _sb():
    from app.db.supabase_client import get_supabase

    return get_supabase()


@router.get("")
def list_users(_: Principal = Depends(require_admin)):
    settings = get_settings()
    profiles = identity.list_profiles()
    roles = {str(r.get("user_id")): r.get("role") for r in identity._store().list_all("roles")}  # noqa: SLF001
    # Enrich from Auth when supabase
    out = []
    for p in profiles:
        uid = str(p.get("id"))
        out.append(
            {
                **p,
                "role": roles.get(uid),
                "store": (settings.api_store or "supabase").lower(),
            }
        )
    return out


@router.post("", status_code=201)
def create_user(body: AdminUserCreate, _: Principal = Depends(require_admin)):
    settings = get_settings()
    mode = (settings.api_store or "supabase").lower()
    password = body.temporary_password or _temp_password()
    expires = datetime.now(timezone.utc) + timedelta(hours=24)

    if mode == "memory":
        uid = uuid4()
        identity.upsert_profile(
            uid,
            {
                "email": body.email,
                "display_name": body.display_name or body.email,
                "status": "pending",
                "must_change_password": True,
                "invite_expires_at": expires,
            },
        )
        identity.set_role(uid, body.role)
        return {
            "user_id": str(uid),
            "email": body.email,
            "role": body.role,
            "temporary_password": password,
            "invite_expires_at": expires.isoformat(),
            "note": "memory store — password not stored in Auth",
        }

    sb = _sb()
    try:
        created = sb.auth.admin.create_user(
            {
                "email": body.email,
                "password": password,
                "email_confirm": True,
                "user_metadata": {"display_name": body.display_name or body.email},
            }
        )
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=400, detail=f"Auth create failed: {exc}") from exc

    user = created.user
    if not user:
        raise HTTPException(status_code=500, detail="No user returned")
    uid = UUID(user.id)
    identity.upsert_profile(
        uid,
        {
            "email": body.email,
            "display_name": body.display_name or body.email,
            "status": "pending",
            "must_change_password": True,
            "invite_expires_at": expires,
        },
    )
    identity.set_role(uid, body.role)
    return {
        "user_id": str(uid),
        "email": body.email,
        "role": body.role,
        "temporary_password": password,
        "invite_expires_at": expires.isoformat(),
    }


@router.patch("/{user_id}")
def patch_user(user_id: UUID, body: AdminUserPatch, _: Principal = Depends(require_admin)):
    profile = identity.get_profile(user_id)
    if not profile:
        raise HTTPException(status_code=404, detail="Profile not found")

    patch: dict = {"updated_at": datetime.now(timezone.utc)}
    if body.display_name is not None:
        patch["display_name"] = body.display_name
    if body.status is not None:
        patch["status"] = body.status
    result_extra: dict = {}

    if body.role is not None:
        identity.set_role(user_id, body.role)

    if body.reissue_invite:
        password = _temp_password()
        expires = datetime.now(timezone.utc) + timedelta(hours=24)
        patch["must_change_password"] = True
        patch["invite_expires_at"] = expires
        patch["invite_consumed_at"] = None
        patch["status"] = "pending"
        settings = get_settings()
        if (settings.api_store or "").lower() != "memory":
            sb = _sb()
            try:
                sb.auth.admin.update_user_by_id(str(user_id), {"password": password})
                # Best-effort session revoke
                try:
                    sb.auth.admin.sign_out(str(user_id))
                except Exception:  # noqa: BLE001
                    pass
            except Exception as exc:  # noqa: BLE001
                raise HTTPException(status_code=400, detail=f"Reissue failed: {exc}") from exc
        result_extra["temporary_password"] = password
        result_extra["invite_expires_at"] = expires.isoformat()

    if body.status == "disabled" or body.role is not None:
        settings = get_settings()
        if (settings.api_store or "").lower() != "memory":
            sb = _sb()
            try:
                sb.auth.admin.sign_out(str(user_id))
            except Exception:  # noqa: BLE001
                pass

    updated = identity.upsert_profile(user_id, {**profile, **patch})
    return {**updated, **result_extra}
