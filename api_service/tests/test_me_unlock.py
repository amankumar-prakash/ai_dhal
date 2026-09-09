""" /me tool_unlock is always both teams. """
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
    from app.config import get_settings

    get_settings.cache_clear()
    from app.main import app

    return TestClient(app)


def test_me_unlock_always_both(client, monkeypatch):
    user = uuid4()
    identity.set_role(user, "user")
    identity.upsert_profile(user, {"email": "u@t", "status": "active", "must_change_password": False})

    def fake_decode(token, settings):
        return {"sub": str(user), "email": "u@t"}

    monkeypatch.setattr("app.deps.decode_access_token", fake_decode)
    r = client.get("/api/v1/me", headers={"Authorization": "Bearer x"})
    assert r.status_code == 200
    assert r.json()["tool_unlock"] == {"red": True, "blue": True}
