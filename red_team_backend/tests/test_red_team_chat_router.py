"""Red-team chat worker router: mounting + service-token auth."""
from __future__ import annotations

from fastapi.testclient import TestClient

from app.main import app
from app.settings import get_settings

client = TestClient(app)


def _token() -> str:
    return get_settings().red_service_token


def test_create_session_requires_valid_token():
    r = client.post(
        "/red-team-chat/sessions",
        headers={"X-Service-Token": "wrong"},
        json={"user_id": "u1", "team": "red"},
    )
    assert r.status_code == 401


def test_create_session_ok_with_token():
    r = client.post(
        "/red-team-chat/sessions",
        headers={"X-Service-Token": _token()},
        json={"user_id": "u1", "team": "red"},
    )
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["status"] == "running"
    assert "id" in body


def test_summary_available_after_stop():
    created = client.post(
        "/red-team-chat/sessions",
        headers={"X-Service-Token": _token()},
        json={"user_id": "u2", "team": "red", "message": "hello"},
    ).json()
    sid = created["id"]
    client.post(f"/red-team-chat/sessions/{sid}/stop", headers={"X-Service-Token": _token()})
    summary = client.get(f"/red-team-chat/sessions/{sid}/summary", headers={"X-Service-Token": _token()})
    assert summary.status_code == 200
    assert "Red Team Chat summary" in summary.text
