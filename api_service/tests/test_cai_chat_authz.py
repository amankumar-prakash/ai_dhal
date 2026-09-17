"""CAI chat is open to any authenticated role — negative paths are also guarded.

Tests:
  - any human role can create a session (happy path, parametrised)
  - unauthenticated request → 401
  - service token → 403 (JWT required, not service token)
  - GET unknown session without team query → 404
  - GET known session using stored team (no ?team= needed) → proxied correctly
  - POST message with whitespace-only content → 400
  - POST session with empty string message body field → 400
  - STOP unknown session → 404
"""
from __future__ import annotations

from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from app.db import memory
from app.services import identity


# ── shared helpers ─────────────────────────────────────────────────────────────

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

    async def fake_get(team, session_id, **kwargs):
        return {
            "id": str(session_id),
            "team": team,
            "status": "running",
            "task_id": None,
            "created_at": None,
            "updated_at": None,
            "ended_at": None,
            "error": None,
        }

    async def fake_post_message(team, session_id, content, **kwargs):
        return {
            "id": str(session_id),
            "team": team,
            "status": "running",
            "task_id": None,
            "created_at": None,
            "updated_at": None,
            "ended_at": None,
            "error": None,
        }

    async def fake_stop(team, session_id, **kwargs):
        return {
            "id": str(session_id),
            "team": team,
            "status": "stopping",
            "task_id": None,
            "created_at": None,
            "updated_at": None,
            "ended_at": None,
            "error": None,
        }

    monkeypatch.setattr("app.services.cai_proxy.create_session", fake_create)
    monkeypatch.setattr("app.services.cai_proxy.get_session", fake_get)
    monkeypatch.setattr("app.services.cai_proxy.post_message", fake_post_message)
    monkeypatch.setattr("app.services.cai_proxy.stop_session", fake_stop)
    from app.main import app

    return TestClient(app)


def _auth(monkeypatch, uid, role):
    identity.set_role(uid, role)
    identity.upsert_profile(uid, {"email": f"{role}@t", "status": "active", "must_change_password": False})

    def fake_decode(token, settings):
        return {"sub": str(uid), "email": f"{role}@t"}

    monkeypatch.setattr("app.deps.decode_access_token", fake_decode)


# ── happy-path: all human roles ────────────────────────────────────────────────

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


# ── auth edge cases ─────────────────────────────────────────────────────────────

def test_cai_requires_auth(client):
    """CR-13: unauthenticated request must be rejected with 401."""
    r = client.post("/api/v1/cai/sessions", json={"team": "blue"})
    assert r.status_code == 401


def test_cai_rejects_service_token(client, monkeypatch):
    """CR-13: service tokens are not human JWTs — CAI must respond 403."""
    monkeypatch.setenv("RED_SERVICE_TOKEN", "change-me-red")
    from app.config import get_settings
    get_settings.cache_clear()
    r = client.post(
        "/api/v1/cai/sessions",
        headers={"X-Service-Token": "change-me-red"},
        json={"team": "red"},
    )
    assert r.status_code == 403, r.text


# ── session resolution edge cases ──────────────────────────────────────────────

def test_get_unknown_session_without_team_returns_404(client, monkeypatch):
    """CR-13: GET a session ID that isn't in _SESSION_TEAM and no ?team= → 404."""
    uid = uuid4()
    _auth(monkeypatch, uid, "user")
    fake_id = str(uuid4())
    r = client.get(
        f"/api/v1/cai/sessions/{fake_id}",
        headers={"Authorization": "Bearer x"},
        # deliberately no ?team= param
    )
    assert r.status_code == 404, r.text


def test_get_session_resolves_from_stored_team(client, monkeypatch):
    """CR-13: GET /sessions/{id} works without ?team= once session was created."""
    uid = uuid4()
    _auth(monkeypatch, uid, "user")
    # Create to populate the session-team map
    created = client.post(
        "/api/v1/cai/sessions",
        headers={"Authorization": "Bearer x"},
        json={"team": "blue"},
    )
    assert created.status_code == 201
    session_id = created.json()["id"]

    # Now GET without any ?team= — should still resolve via the stored mapping
    r = client.get(
        f"/api/v1/cai/sessions/{session_id}",
        headers={"Authorization": "Bearer x"},
    )
    assert r.status_code == 200, r.text


def test_stop_unknown_session_returns_404(client, monkeypatch):
    """CR-13: STOP an unknown session → 404."""
    uid = uuid4()
    _auth(monkeypatch, uid, "user")
    r = client.post(
        f"/api/v1/cai/sessions/{uuid4()}/stop",
        headers={"Authorization": "Bearer x"},
    )
    assert r.status_code == 404, r.text


# ── input validation edge cases ────────────────────────────────────────────────

def test_post_message_whitespace_only_content_rejected(client, monkeypatch):
    """CR-13: whitespace-only message content must return 400."""
    uid = uuid4()
    _auth(monkeypatch, uid, "user")
    created = client.post(
        "/api/v1/cai/sessions",
        headers={"Authorization": "Bearer x"},
        json={"team": "blue"},
    )
    assert created.status_code == 201
    session_id = created.json()["id"]

    r = client.post(
        f"/api/v1/cai/sessions/{session_id}/messages",
        headers={"Authorization": "Bearer x"},
        json={"content": "   "},  # whitespace only
    )
    assert r.status_code == 400, r.text
    assert "empty content" in r.json().get("detail", "")


def test_create_session_empty_message_field_rejected(client, monkeypatch):
    """CR-13: providing message="" (empty string) in session create → 400."""
    uid = uuid4()
    _auth(monkeypatch, uid, "user")
    r = client.post(
        "/api/v1/cai/sessions",
        headers={"Authorization": "Bearer x"},
        json={"team": "red", "message": ""},
    )
    assert r.status_code == 400, r.text
    assert "non-empty" in r.json().get("detail", "")
