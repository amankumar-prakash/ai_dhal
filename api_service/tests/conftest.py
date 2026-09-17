"""
Pytest configuration for api_service tests.

All environment overrides are consolidated in the _reset_store autouse fixture
(CR-12: removed module-level os.environ.setdefault calls that mutated global
process state before any test ran, interfering with IDE runners and
parallel execution).
"""
import jwt
import pytest
from fastapi.testclient import TestClient

from app.db import memory as store


@pytest.fixture(autouse=True)
def _reset_store(monkeypatch):
    # CR-12 FIX: all env patching is done exclusively in the fixture so each
    # test starts from a clean slate rather than inheriting module-level state.
    monkeypatch.setenv("API_STORE", "memory")
    monkeypatch.setenv("SUPABASE_JWT_SECRET", "test-secret-at-least-32-chars-long!!")
    from app.config import get_settings

    get_settings.cache_clear()
    store.reset()

    # CR-03 FIX: clear the bounded session-team map so CAI chat tests don't
    # bleed session state from one test into another.
    from app.routers.cai_chat import _clear_session_team
    _clear_session_team()

    yield

    store.reset()
    get_settings.cache_clear()

    # Ensure the session map is clean after each test as well.
    from app.routers.cai_chat import _clear_session_team as _cst
    _cst()


@pytest.fixture
def client():
    from app.main import app
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
