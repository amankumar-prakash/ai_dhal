"""Supabase PostgREST-backed store (same surface as memory.py)."""
from __future__ import annotations

from datetime import date, datetime
from typing import Any
from uuid import UUID

from app.db.supabase_client import get_supabase

# memory uses "roles"; Postgres table is user_roles
_TABLE_MAP = {"roles": "user_roles"}


def _pg_table(name: str) -> str:
    return _TABLE_MAP.get(name, name)


def _serialize(value: Any) -> Any:
    if isinstance(value, UUID):
        return str(value)
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    if isinstance(value, dict):
        return {k: _serialize(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_serialize(v) for v in value]
    return value


def _normalize(row: dict[str, Any] | None) -> dict[str, Any] | None:
    if not row:
        return None
    out: dict[str, Any] = {}
    for k, v in row.items():
        if k in {
            "id",
            "asset_id",
            "scan_id",
            "job_id",
            "finding_id",
            "chain_id",
            "user_id",
            "requested_by",
            "created_by",
            "threat_event_id",
            "assignee_id",
            "assigning_manager_id",
            "linked_job_id",
            "author_id",
            "actor_id",
            "from_assignee",
            "to_assignee",
            "task_id",
            "ref_id",
        } and isinstance(v, str):
            try:
                out[k] = UUID(v)
            except ValueError:
                out[k] = v
        elif k == "asset_ids" and isinstance(v, list):
            out[k] = [UUID(x) if isinstance(x, str) else x for x in v]
        else:
            out[k] = v
    return out


def reset() -> None:
    """No-op for cloud store (tests use memory)."""
    return


def create(table: str, data: dict[str, Any]) -> dict[str, Any]:
    payload = _serialize({k: v for k, v in data.items() if v is not None or k == "id"})
    sb = get_supabase()
    resp = sb.table(_pg_table(table)).insert(payload).execute()
    rows = resp.data or []
    if not rows:
        raise RuntimeError(f"insert into {table} returned no rows")
    return _normalize(rows[0])  # type: ignore[return-value]


def get(table: str, item_id: UUID) -> dict[str, Any] | None:
    sb = get_supabase()
    resp = sb.table(_pg_table(table)).select("*").eq("id", str(item_id)).limit(1).execute()
    rows = resp.data or []
    return _normalize(rows[0]) if rows else None


def list_all(table: str, **filters: Any) -> list[dict[str, Any]]:
    sb = get_supabase()
    q = sb.table(_pg_table(table)).select("*")
    for key, val in filters.items():
        if val is None:
            continue
        q = q.eq(key, val)
    resp = q.execute()
    return [_normalize(r) for r in (resp.data or [])]  # type: ignore[misc]


def update(table: str, item_id: UUID, patch: dict[str, Any]) -> dict[str, Any] | None:
    payload = _serialize({k: v for k, v in patch.items() if v is not None})
    if not payload:
        return get(table, item_id)
    sb = get_supabase()
    resp = sb.table(_pg_table(table)).update(payload).eq("id", str(item_id)).execute()
    rows = resp.data or []
    if rows:
        return _normalize(rows[0])
    return get(table, item_id)


def delete(table: str, item_id: UUID) -> bool:
    existing = get(table, item_id)
    if not existing:
        return False
    sb = get_supabase()
    sb.table(_pg_table(table)).delete().eq("id", str(item_id)).execute()
    return True
