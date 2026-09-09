"""Password login for the lab when Supabase Auth is unavailable."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from uuid import UUID

import httpx
import jwt
from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, EmailStr, Field

from app.config import Settings, get_settings
from app.lab_users import find_lab_account, seed_lab_identities, user_id_for_email
from app.services import identity

router = APIRouter(prefix="/auth", tags=["auth"])


class LoginBody(BaseModel):
    email: EmailStr
    password: str = Field(min_length=1)


def _mint_lab_token(email: str, role: str, secret: str) -> str:
    uid = user_id_for_email(email)
    now = datetime.now(timezone.utc)
    return jwt.encode(
        {
            "sub": str(uid),
            "email": email,
            "role": role,
            "aud": "authenticated",
            "iat": int(now.timestamp()),
            "exp": int((now + timedelta(days=7)).timestamp()),
        },
        secret,
        algorithm="HS256",
    )


def _ensure_memory_identity(user_id: UUID, email: str, role: str, display_name: str) -> None:
    settings = get_settings()
    if (settings.api_store or "").lower() != "memory":
        return
    now = datetime.now(timezone.utc)
    identity.upsert_profile(
        user_id,
        {
            "email": email,
            "display_name": display_name,
            "status": "active",
            "must_change_password": False,
            "invite_expires_at": None,
            "invite_consumed_at": now,
        },
    )
    from app.db.store import get_store
    from uuid import uuid4

    store = get_store()
    existing = [r for r in store.list_all("roles") if str(r.get("user_id")) == str(user_id)]
    if existing:
        store.update("roles", existing[0]["id"], {"role": role})
    else:
        store.create("roles", {"id": uuid4(), "user_id": user_id, "role": role})


def _role_from_supabase(user_id: str, settings: Settings) -> str | None:
    key = settings.elevated_key()
    base = settings.supabase_url.rstrip("/")
    if not key or not base:
        return None
    try:
        with httpx.Client(timeout=10.0) as client:
            resp = client.get(
                f"{base}/rest/v1/user_roles",
                params={"user_id": f"eq.{user_id}", "select": "role"},
                headers={"apikey": key, "Authorization": f"Bearer {key}"},
            )
        if resp.status_code >= 400:
            return None
        rows = resp.json()
        if isinstance(rows, list) and rows:
            return str(rows[0].get("role") or "") or None
    except Exception:
        return None
    return None


def _login_via_supabase(email: str, password: str, settings: Settings) -> dict[str, str] | None:
    key = settings.elevated_key()
    base = settings.supabase_url.rstrip("/")
    if not key or not base:
        return None
    try:
        with httpx.Client(timeout=15.0) as client:
            resp = client.post(
                f"{base}/auth/v1/token?grant_type=password",
                headers={"apikey": key, "Authorization": f"Bearer {key}"},
                json={"email": email, "password": password},
            )
        if resp.status_code >= 400:
            return None
        data = resp.json()
        token = data.get("access_token")
        user = data.get("user") or {}
        uid = str(user.get("id") or "")
        if not token or not uid:
            return None
        role = _role_from_supabase(uid, settings) or "user"
        _ensure_memory_identity(
            UUID(uid),
            email.strip().lower(),
            role,
            str((user.get("user_metadata") or {}).get("display_name") or email.split("@")[0]),
        )
        return {"access_token": token, "token_type": "bearer", "role": role}
    except Exception:
        return None


@router.post("/login")
def login(body: LoginBody) -> dict[str, str]:
    settings = get_settings()
    secret = (settings.supabase_jwt_secret or "").strip()
    acct = find_lab_account(body.email, body.password, settings)
    if acct:
        if not secret:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="SUPABASE_JWT_SECRET is not configured",
            )
        seed_lab_identities()
        token = _mint_lab_token(acct["email"], acct["role"], secret)
        return {"access_token": token, "token_type": "bearer", "role": acct["role"]}

    via_supabase = _login_via_supabase(body.email, body.password, settings)
    if via_supabase:
        return via_supabase

    raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid email or password")
