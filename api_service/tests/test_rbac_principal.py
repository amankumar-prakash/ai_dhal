"""API RBAC principal resolves from user_roles."""
from __future__ import annotations

from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from app.db import memory
from app.services import identity


@pytest.fixture()
def client(monkeypatch):
    monkeypatch.setenv("API_STORE", "memory")
    memory.reset()
    # clear settings cache
    from app.config import get_settings

    get_settings.cache_clear()
    from app.main import app

    return TestClient(app)


def test_principal_admin_from_user_roles(client, monkeypatch):
    uid = uuid4()
    identity.set_role(uid, "admin")
    identity.upsert_profile(uid, {"email": "a@test", "status": "active", "must_change_password": False})

    # Patch decode to return our user
    from app import deps

    def fake_decode(token, settings):
        return {"sub": str(uid), "email": "a@test"}

    monkeypatch.setattr("app.deps.decode_access_token", fake_decode)
    r = client.get("/api/v1/me", headers={"Authorization": "Bearer fake"})
    assert r.status_code == 200
    body = r.json()
    assert body["role"] == "admin"
    assert body["tool_unlock"] == {"red": False, "blue": False}
