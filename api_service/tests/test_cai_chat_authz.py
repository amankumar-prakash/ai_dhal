"""CAI chat is open to any authenticated role."""
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

    async def fake_create(**kwargs):
        return {
            "id": str(uuid4()),
            "team": kwargs["team"],
            "status": "running",
            "task_id": kwargs.get("task_id"),
            "created_at": None,
            "updated_at": None,
            "ended_at": None,
            "error": None,
        }

    monkeypatch.setattr("app.services.cai_proxy.create_session", fake_create)
    from app.main import app

    return TestClient(app)


def _auth(monkeypatch, uid, role):
    identity.set_role(uid, role)
    identity.upsert_profile(uid, {"email": f"{role}@t", "status": "active", "must_change_password": False})

    def fake_decode(token, settings):
        return {"sub": str(uid), "email": f"{role}@t"}

    monkeypatch.setattr("app.deps.decode_access_token", fake_decode)


@pytest.mark.parametrize("role", ["security_manager", "security_analyst", "user", "admin"])
def test_any_role_can_create_cai_session(client, monkeypatch, role):
    uid = uuid4()
    _auth(monkeypatch, uid, role)
    r = client.post(
        "/api/v1/cai/sessions",
        headers={"Authorization": "Bearer x"},
        json={"team": "blue", "message": "hi"},
    )
    assert r.status_code == 201, r.text
