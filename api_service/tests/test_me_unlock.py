"""Analyst unlock via /me."""
from __future__ import annotations

from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from app.db import memory
from app.services import identity, tasks as task_svc
from app.deps import Principal, PrincipalKind
from app.schemas.models import TaskCreate


@pytest.fixture()
def client(monkeypatch):
    monkeypatch.setenv("API_STORE", "memory")
    memory.reset()
    from app.config import get_settings

    get_settings.cache_clear()
    from app.main import app

    return TestClient(app)


def test_me_unlock_red_only(client, monkeypatch):
    analyst = uuid4()
    mgr = uuid4()
    identity.set_role(analyst, "security_analyst")
    identity.upsert_profile(analyst, {"email": "a@t", "status": "active", "must_change_password": False})
    identity.set_role(mgr, "security_manager")

    mgr_p = Principal(kind=PrincipalKind.security_manager, user_id=str(mgr), role="security_manager")
    task = task_svc.create_task(
        TaskCreate(target="h", description="d", patch_scope="p", task_type="red", assignee_id=analyst),
        mgr_p,
    )
    tid = task["id"]
    an_p = Principal(kind=PrincipalKind.security_analyst, user_id=str(analyst), role="security_analyst")
    from app.schemas.models import TaskPatch

    task_svc.apply_patch(tid, TaskPatch(action="start"), an_p)

    def fake_decode(token, settings):
        return {"sub": str(analyst), "email": "a@t"}

    monkeypatch.setattr("app.deps.decode_access_token", fake_decode)
    r = client.get("/api/v1/me", headers={"Authorization": "Bearer x"})
    assert r.status_code == 200
    assert r.json()["tool_unlock"] == {"red": True, "blue": False}
