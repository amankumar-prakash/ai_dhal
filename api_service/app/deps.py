"""Auth dependencies: human JWT + DB role from user_roles; service tokens."""
from __future__ import annotations

from enum import Enum
from typing import Annotated
from uuid import UUID

import jwt
from fastapi import Depends, Header, HTTPException, status
from pydantic import BaseModel

from app.auth.jwks import decode_access_token
from app.config import Settings, get_settings
from app.db.store import get_store

HUMAN_KINDS = frozenset(
    {
        "user",
        "security_analyst",
        "security_manager",
        "admin",
        # legacy alias kept for PrincipalKind enum member
        "analyst",
    }
)


class PrincipalKind(str, Enum):
    user = "user"
    security_analyst = "security_analyst"
    security_manager = "security_manager"
    admin = "admin"
    red_service = "red_service"
    blue_service = "blue_service"


class Principal(BaseModel):
    kind: PrincipalKind
    user_id: str | None = None
    role: str | None = None
    email: str | None = None


def _normalize_app_role(raw: str | None) -> str:
    if not raw:
        return "user"
    if raw == "analyst":
        return "security_analyst"
    if raw in {"user", "security_analyst", "security_manager", "admin"}:
        return raw
    return "user"


def _role_from_store(user_id: str) -> str | None:
    try:
        uid = UUID(user_id)
    except ValueError:
        return None
    rows = get_store().list_all("roles", user_id=uid)
    if not rows:
        # memory/supabase may store user_id as str
        rows = [r for r in get_store().list_all("roles") if str(r.get("user_id")) == user_id]
    if not rows:
        return None
    return _normalize_app_role(str(rows[0].get("role")))


def get_principal(
    authorization: Annotated[str | None, Header()] = None,
    x_service_token: Annotated[str | None, Header(alias="X-Service-Token")] = None,
    settings: Settings = Depends(get_settings),
) -> Principal:
    if x_service_token:
        if x_service_token == settings.red_service_token:
            return Principal(kind=PrincipalKind.red_service)
        if x_service_token == settings.blue_service_token:
            return Principal(kind=PrincipalKind.blue_service)
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid service token")

    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Missing credentials")

    raw = authorization.split(" ", 1)[1]
    try:
        payload = decode_access_token(raw, settings)
    except jwt.PyJWTError as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token") from exc

    user_id = str(payload.get("sub", ""))
    email = payload.get("email")
    if isinstance(email, str):
        email_val: str | None = email
    else:
        email_val = None

    db_role = _role_from_store(user_id) if user_id else None
    if db_role:
        role = db_role
    else:
        # Fallback JWT claims only when no user_roles row (pre-bootstrap)
        claim = payload.get("role") or payload.get("app_role")
        if claim == "authenticated":
            claim = (payload.get("app_metadata") or {}).get("role")
        role = _normalize_app_role(str(claim) if claim else None)

    kind = PrincipalKind(role)
    return Principal(kind=kind, user_id=user_id, role=role, email=email_val)


def require_jwt(principal: Principal = Depends(get_principal)) -> Principal:
    if principal.kind not in (
        PrincipalKind.user,
        PrincipalKind.security_analyst,
        PrincipalKind.security_manager,
        PrincipalKind.admin,
    ):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="User JWT required")
    return principal


def require_admin(principal: Principal = Depends(require_jwt)) -> Principal:
    return principal


def require_manager(principal: Principal = Depends(require_jwt)) -> Principal:
    return principal


def require_manager_or_analyst(principal: Principal = Depends(require_jwt)) -> Principal:
    return principal


def require_ops_reader(principal: Principal = Depends(require_jwt)) -> Principal:
    return principal


def require_service(principal: Principal = Depends(get_principal)) -> Principal:
    if principal.kind not in (PrincipalKind.red_service, PrincipalKind.blue_service):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Service token required")
    return principal


def require_jwt_or_service(principal: Principal = Depends(get_principal)) -> Principal:
    return principal


def deny_service_destructive(principal: Principal) -> None:
    """Service tokens cannot delete assets or change roles."""
    if principal.kind in (PrincipalKind.red_service, PrincipalKind.blue_service):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Service not allowed")


def deny_user_mutate(_principal: Principal) -> None:
    return
