"""In-app notifications."""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from uuid import UUID, uuid4

from app.db.store import get_store


def notify(
    user_id: UUID,
    ntype: str,
    title: str,
    body: str | None,
    task_id: UUID | None = None,
) -> dict[str, Any]:
    return get_store().create(
        "notifications",
        {
            "id": uuid4(),
            "user_id": user_id,
            "type": ntype,
            "task_id": task_id,
            "title": title,
            "body": body,
            "read_at": None,
            "created_at": datetime.now(timezone.utc),
        },
    )


def list_for_user(user_id: UUID) -> list[dict[str, Any]]:
    return [r for r in get_store().list_all("notifications") if str(r.get("user_id")) == str(user_id)]
