"""Identity helpers: profiles, roles, tool unlock."""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from uuid import UUID, uuid4

from app.db.store import get_store


def _store():
    return get_store()


def get_profile(user_id: UUID) -> dict[str, Any] | None:
    row = _store().get("profiles", user_id)
    if row:
        return row
    # fallback scan
    for r in _store().list_all("profiles"):
        if str(r.get("id")) == str(user_id):
            return r
    return None


def upsert_profile(user_id: UUID, data: dict[str, Any]) -> dict[str, Any]:
    existing = get_profile(user_id)
    payload = {**data, "id": user_id, "updated_at": datetime.now(timezone.utc)}
    if existing:
        return _store().update("profiles", user_id, payload) or payload
    payload.setdefault("created_at", datetime.now(timezone.utc))
    return _store().create("profiles", payload)


def get_role_for_user(user_id: UUID) -> str | None:
    rows = _store().list_all("roles", user_id=user_id)
    if not rows:
        rows = [r for r in _store().list_all("roles") if str(r.get("user_id")) == str(user_id)]
    if not rows:
        return None
    role = str(rows[0].get("role"))
    if role == "analyst":
        return "security_analyst"
    return role


def set_role(user_id: UUID, role: str) -> dict[str, Any]:
    if role == "analyst":
        role = "security_analyst"
    existing = _store().list_all("roles", user_id=user_id)
    if not existing:
        existing = [r for r in _store().list_all("roles") if str(r.get("user_id")) == str(user_id)]
    for row in existing:
        rid = row.get("id")
        if rid is not None:
            _store().delete("roles", rid if isinstance(rid, UUID) else UUID(str(rid)))
    return _store().create("roles", {"id": uuid4(), "user_id": user_id, "role": role})


def list_in_progress_tasks(assignee_id: UUID) -> list[dict[str, Any]]:
    return [
        t
        for t in _store().list_all("tasks")
        if str(t.get("assignee_id")) == str(assignee_id) and t.get("status") == "in_progress"
    ]


def tool_unlock_for(_user_id: UUID, _role: str) -> dict[str, bool]:
    return {"red": True, "blue": True}


def list_profiles() -> list[dict[str, Any]]:
    return _store().list_all("profiles")
