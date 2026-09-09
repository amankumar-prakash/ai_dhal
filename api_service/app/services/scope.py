"""Assigned-scope helpers for Analyst threat/scan visibility."""
from __future__ import annotations

from typing import Any
from uuid import UUID

from app.db.store import get_store
from app.deps import Principal


def assignee_asset_ids(user_id: str) -> set[str]:
    ids: set[str] = set()
    for t in get_store().list_all("tasks"):
        if str(t.get("assignee_id")) != user_id:
            continue
        if t.get("status") == "closed":
            continue
        aid = t.get("asset_id")
        if aid is not None:
            ids.add(str(aid))
    return ids


def filter_ops_rows(rows: list[dict[str, Any]], _principal: Principal) -> list[dict[str, Any]]:
    return rows
