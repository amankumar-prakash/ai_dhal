"""API AuthZ for CAI chat."""
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
    # avoid real worker calls — patch proxy
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


def test_manager_can_create(client, monkeypatch):
    uid = uuid4()
    _auth(monkeypatch, uid, "security_manager")
    r = client.post(
        "/api/v1/cai/sessions",
        headers={"Authorization": "Bearer x"},
        json={"team": "red", "message": "hi"},
    )
    assert r.status_code == 201, r.text


def test_admin_denied(client, monkeypatch):
    uid = uuid4()
    _auth(monkeypatch, uid, "admin")
    r = client.post(
        "/api/v1/cai/sessions",
        headers={"Authorization": "Bearer x"},
        json={"team": "red", "message": "hi"},
    )
    assert r.status_code == 403


def test_user_denied(client, monkeypatch):
    uid = uuid4()
    _auth(monkeypatch, uid, "user")
    r = client.post(
        "/api/v1/cai/sessions",
        headers={"Authorization": "Bearer x"},
        json={"team": "red", "message": "hi"},
    )
    assert r.status_code == 403


def test_analyst_without_unlock_denied_blue(client, monkeypatch):
    uid = uuid4()
    _auth(monkeypatch, uid, "security_analyst")
    r = client.post(
        "/api/v1/cai/sessions",
        headers={"Authorization": "Bearer x"},
        json={"team": "blue", "message": "hi"},
    )
    assert r.status_code == 403
