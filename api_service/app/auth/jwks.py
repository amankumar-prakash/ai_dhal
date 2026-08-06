"""Verify Supabase Auth JWTs via JWKS (signing keys) with optional HS256 fallback."""
from __future__ import annotations

import logging
from functools import lru_cache

import jwt
from jwt import PyJWKClient

from app.config import Settings, get_settings

log = logging.getLogger(__name__)


@lru_cache
def _jwks_client(url: str) -> PyJWKClient:
    return PyJWKClient(url, cache_keys=True, lifespan=600)


def decode_access_token(token: str, settings: Settings | None = None) -> dict:
    """Decode and verify a user access token.

    Primary path: JWKS (ES256/RS256 signing keys).
    Fallback: HS256 with SUPABASE_JWT_SECRET if set (legacy / tests).
    """
    settings = settings or get_settings()
    jwks = settings.jwks_url()
    secret = (settings.supabase_jwt_secret or "").strip()

    if jwks:
        try:
            client = _jwks_client(jwks)
            signing_key = client.get_signing_key_from_jwt(token)
            return jwt.decode(
                token,
                signing_key.key,
                algorithms=["ES256", "RS256", "EdDSA", "HS256"],
                options={"verify_aud": False},
            )
        except Exception as exc:  # noqa: BLE001
            if not secret:
                log.warning("JWKS verify failed and no JWT secret fallback: %s", exc)
                raise
            log.info("JWKS verify failed (%s); trying HS256 fallback", exc)

    if secret:
        return jwt.decode(
            token,
            secret,
            algorithms=["HS256"],
            options={"verify_aud": False},
        )

    raise jwt.InvalidTokenError("No JWKS URL or SUPABASE_JWT_SECRET configured")


def clear_jwks_cache() -> None:
    _jwks_client.cache_clear()
