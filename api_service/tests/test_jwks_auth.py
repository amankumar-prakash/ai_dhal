"""JWKS / HS256 auth verification tests."""
from unittest.mock import MagicMock, patch

import jwt
import pytest

from app.auth.jwks import clear_jwks_cache, decode_access_token
from app.config import Settings


def test_hs256_fallback_without_jwks():
    secret = "test-secret-at-least-32-chars-long!!"
    settings = Settings(
        supabase_url="",
        supabase_jwt_secret=secret,
        supabase_jwks_url="",
    )
    token = jwt.encode(
        {"sub": "11111111-1111-1111-1111-111111111111", "role": "analyst"},
        secret,
        algorithm="HS256",
    )
    payload = decode_access_token(token, settings)
    assert payload["sub"] == "11111111-1111-1111-1111-111111111111"


def test_jwks_path_used_when_url_set():
    clear_jwks_cache()
    settings = Settings(
        supabase_url="https://example.supabase.co",
        supabase_jwt_secret="",
    )
    token = jwt.encode(
        {"sub": "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa", "role": "authenticated"},
        "ignored",
        algorithm="HS256",
        headers={"kid": "test-kid"},
    )
    mock_key = MagicMock()
    mock_key.key = "unused"
    with patch("app.auth.jwks._jwks_client") as client_factory:
        client = MagicMock()
        client.get_signing_key_from_jwt.return_value = mock_key
        client_factory.return_value = client
        with patch("app.auth.jwks.jwt.decode") as decode:
            decode.return_value = {"sub": "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa", "role": "authenticated"}
            out = decode_access_token(token, settings)
    assert out["sub"].startswith("aaaaaaaa")
    client.get_signing_key_from_jwt.assert_called_once()
    decode.assert_called_once()


def test_assets_unauthorized(client):
    assert client.get("/api/v1/assets").status_code == 401
