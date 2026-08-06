import os

# Tests use in-memory store + HS256 fallback secret
os.environ.setdefault("API_STORE", "memory")
os.environ.setdefault("SUPABASE_JWT_SECRET", "test-secret-at-least-32-chars-long!!")

import jwt
import pytest
from fastapi.testclient import TestClient

from app.db import memory as store
from app.main import app


@pytest.fixture(autouse=True)
def _reset_store(monkeypatch):
    monkeypatch.setenv("API_STORE", "memory")
    monkeypatch.setenv("SUPABASE_JWT_SECRET", "test-secret-at-least-32-chars-long!!")
    from app.config import get_settings

    get_settings.cache_clear()
    store.reset()
    yield
    store.reset()
    get_settings.cache_clear()


@pytest.fixture
def client():
    return TestClient(app)


@pytest.fixture
def jwt_secret():
    return "test-secret-at-least-32-chars-long!!"


@pytest.fixture
def analyst_headers(jwt_secret, monkeypatch):
    monkeypatch.setenv("SUPABASE_JWT_SECRET", jwt_secret)
    monkeypatch.setenv("API_STORE", "memory")
    from app.config import get_settings

    get_settings.cache_clear()
    token = jwt.encode(
        {"sub": "11111111-1111-1111-1111-111111111111", "role": "analyst"},
        jwt_secret,
        algorithm="HS256",
    )
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def admin_headers(jwt_secret, monkeypatch):
    monkeypatch.setenv("SUPABASE_JWT_SECRET", jwt_secret)
    monkeypatch.setenv("API_STORE", "memory")
    from app.config import get_settings

    get_settings.cache_clear()
    token = jwt.encode(
        {"sub": "22222222-2222-2222-2222-222222222222", "role": "admin"},
        jwt_secret,
        algorithm="HS256",
    )
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def red_headers(monkeypatch):
    monkeypatch.setenv("RED_SERVICE_TOKEN", "change-me-red")
    from app.config import get_settings

    get_settings.cache_clear()
    return {"X-Service-Token": "change-me-red"}


@pytest.fixture
def blue_headers(monkeypatch):
    monkeypatch.setenv("BLUE_SERVICE_TOKEN", "change-me-blue")
    from app.config import get_settings

    get_settings.cache_clear()
    return {"X-Service-Token": "change-me-blue"}
