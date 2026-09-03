"""Password login for the lab when Supabase Auth is unavailable."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

import jwt
from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, EmailStr, Field

from app.config import get_settings
from app.lab_users import find_lab_account, user_id_for_email

router = APIRouter(prefix="/auth", tags=["auth"])


class LoginBody(BaseModel):
    email: EmailStr
    password: str = Field(min_length=1)


@router.post("/login")
def login(body: LoginBody) -> dict[str, str]:
    settings = get_settings()
    secret = (settings.supabase_jwt_secret or "").strip()
    if not secret:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="SUPABASE_JWT_SECRET is not configured",
        )
    acct = find_lab_account(body.email, body.password, settings)
    if not acct:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid email or password")
    uid = user_id_for_email(acct["email"])
    now = datetime.now(timezone.utc)
    token = jwt.encode(
        {
            "sub": str(uid),
            "email": acct["email"],
            "role": acct["role"],
            "aud": "authenticated",
            "iat": int(now.timestamp()),
            "exp": int((now + timedelta(days=7)).timestamp()),
        },
        secret,
        algorithm="HS256",
    )
    return {"access_token": token, "token_type": "bearer", "role": acct["role"]}
