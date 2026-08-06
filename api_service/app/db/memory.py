"""In-memory store for lab/demo when API_STORE=memory."""
from __future__ import annotations

from datetime import datetime, timezone
from threading import Lock
from typing import Any
from uuid import UUID, uuid4

_lock = Lock()
_store: dict[str, dict[UUID, dict[str, Any]]] = {
    "assets": {},
    "scans": {},
    "findings": {},
    "threat_events": {},
    "jobs": {},
    "patches": {},
    "attack_chains": {},
    "attack_chain_steps": {},
    "tool_runs": {},
    "roles": {},
    "profiles": {},
    "tasks": {},
    "task_notes": {},
    "task_links": {},
    "task_audit_events": {},
    "notifications": {},
}


def _now() -> datetime:
    return datetime.now(timezone.utc)


def reset() -> None:
    with _lock:
        for k in _store:
            _store[k].clear()


def create(table: str, data: dict[str, Any]) -> dict[str, Any]:
    with _lock:
        row = dict(data)
        row.setdefault("id", uuid4())
        row.setdefault("created_at", _now())
        _store[table][row["id"]] = row
        return dict(row)


def get(table: str, item_id: UUID) -> dict[str, Any] | None:
    with _lock:
        row = _store[table].get(item_id)
        return dict(row) if row else None


def list_all(table: str, **filters: Any) -> list[dict[str, Any]]:
    with _lock:
        rows = [dict(r) for r in _store[table].values()]
    for key, val in filters.items():
        if val is None:
            continue
        rows = [r for r in rows if r.get(key) == val]
    return rows


def update(table: str, item_id: UUID, patch: dict[str, Any]) -> dict[str, Any] | None:
    with _lock:
        row = _store[table].get(item_id)
        if not row:
            return None
        row.update({k: v for k, v in patch.items() if v is not None})
        return dict(row)


def delete(table: str, item_id: UUID) -> bool:
    with _lock:
        return _store[table].pop(item_id, None) is not None
