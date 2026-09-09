"""Manager task create + start-on-behalf audit."""
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


def _auth(monkeypatch, uid, role):
    identity.set_role(uid, role)
    identity.upsert_profile(uid, {"email": f"{role}@t", "status": "active", "must_change_password": False})

    def fake_decode(token, settings):
        return {"sub": str(uid), "email": f"{role}@t"}

    monkeypatch.setattr("app.deps.decode_access_token", fake_decode)


def test_manager_create_and_start_on_behalf(client, monkeypatch):
    mgr = uuid4()
    analyst = uuid4()
    identity.set_role(analyst, "security_analyst")
    identity.upsert_profile(analyst, {"email": "an@t", "status": "active", "must_change_password": False})
    _auth(monkeypatch, mgr, "security_manager")

    created = client.post(
        "/api/v1/tasks",
        headers={"Authorization": "Bearer x"},
        json={
            "target": "edge-gw",
            "description": "recon",
            "patch_scope": "none",
            "task_type": "red",
            "assignee_id": str(analyst),
        },
    )
    assert created.status_code == 201, created.text
    task_id = created.json()["id"]

    started = client.patch(
        f"/api/v1/tasks/{task_id}",
        headers={"Authorization": "Bearer x"},
        json={"action": "start"},
    )
    assert started.status_code == 200
    assert started.json()["status"] == "in_progress"

    audit = client.get(f"/api/v1/tasks/{task_id}/audit", headers={"Authorization": "Bearer x"})
    assert audit.status_code == 200
    actions = [a["action"] for a in audit.json()]
    assert "started_on_behalf" in actions


def test_user_can_create_and_list(client, monkeypatch):
    user = uuid4()
    _auth(monkeypatch, user, "user")

    created = client.post(
        "/api/v1/tasks",
        headers={"Authorization": "Bearer x"},
        json={
            "target": "user-task",
            "description": "open",
            "patch_scope": "none",
            "task_type": "blue",
        },
    )
    assert created.status_code == 201, created.text
    assert created.json()["status"] == "draft"

    listed = client.get("/api/v1/tasks", headers={"Authorization": "Bearer x"})
    assert listed.status_code == 200
    assert any(t["id"] == created.json()["id"] for t in listed.json())
