"""Dispatch jobs to red/blue workers."""
from __future__ import annotations

import logging
from typing import Any
from uuid import UUID

import httpx

from app.config import Settings
from app.db.store import get_store
from app.schemas.models import JobPatch
from app.services import crud

log = logging.getLogger(__name__)


async def dispatch_job(job: dict[str, Any], settings: Settings) -> dict[str, Any]:
    team = job["team"]
    base = settings.red_worker_url if team == "red" else settings.blue_worker_url
    store = get_store()
    assets = []
    for aid in job["asset_ids"]:
        uid = aid if isinstance(aid, UUID) else UUID(str(aid))
        a = store.get("assets", uid)
        if a:
            assets.append(a)

    payload = {
        "job_id": str(job["id"]),
        "team": team,
        "profile": job["profile"],
        "asset_ids": [str(x) for x in job["asset_ids"]],
        "assets": [
            {
                "id": str(a["id"]),
                "name": a.get("name"),
                "hostname": a.get("hostname"),
                "ip_address": a.get("ip_address"),
            }
            for a in assets
        ],
        "tools": None,
        "callback_base_url": "http://api_service:8000/api/v1",
        "demo_safe_mode": True,
        "allowlist": [],
    }

    job = crud.patch_job(job["id"], JobPatch(status="dispatched"))

    for scan in store.list_all("scans"):
        if scan.get("job_id") == job["id"]:
            store.update(
                "scans",
                scan["id"],
                {"status": "running", "source_service": f"{team}_team_backend"},
            )

    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.post(f"{base.rstrip('/')}/internal/jobs", json=payload)
            resp.raise_for_status()
    except Exception as exc:  # noqa: BLE001
        log.warning("dispatch failed: %s", exc)
    return job
