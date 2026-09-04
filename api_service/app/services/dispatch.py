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
from app.services.targets import lab_reachable_url, merge_allowlists, parse_target

log = logging.getLogger(__name__)


async def dispatch_job(
    job: dict[str, Any],
    settings: Settings,
    *,
    task: dict[str, Any] | None = None,
) -> dict[str, Any]:
    team = job["team"]
    base = settings.red_worker_url if team == "red" else settings.blue_worker_url
    store = get_store()
    assets = []
    for aid in job["asset_ids"]:
        uid = aid if isinstance(aid, UUID) else UUID(str(aid))
        a = store.get("assets", uid)
        if a:
            assets.append(a)

    parsed = parse_target((task or {}).get("target") or "")
    allowlist = list(parsed["allowlist"]) if task else []
    scan_url = ""
    if task:
        scan_url = lab_reachable_url(str(parsed["url"] or task.get("target") or ""))
        if scan_url and scan_url != parsed["url"]:
            allowlist = merge_allowlists(allowlist, parse_target(scan_url)["allowlist"])
    scans = [
        {
            "id": str(s["id"]),
            "asset_id": str(s["asset_id"]) if s.get("asset_id") else None,
            "target": s.get("target"),
        }
        for s in store.list_all("scans")
        if str(s.get("job_id")) == str(job["id"])
    ]

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
        "callback_base_url": "http://127.0.0.1:8000/api/v1",
        "demo_safe_mode": True,
        "allowlist": allowlist,
        "task_id": str(task["id"]) if task and task.get("id") else None,
        "target": (scan_url or parsed["url"] or (task or {}).get("target") or None) if task else None,
        "description": (task or {}).get("description") or None,
        "patch_scope": (task or {}).get("patch_scope") or None,
        "scans": scans,
    }

    job = crud.patch_job(job["id"], JobPatch(status="dispatched"))

    for scan in store.list_all("scans"):
        if str(scan.get("job_id")) == str(job["id"]):
            store.update(
                "scans",
                scan["id"],
                {"status": "running", "source_service": f"{team}_team_backend"},
            )

    try:
        async with httpx.AsyncClient(timeout=httpx.Timeout(5.0, connect=2.0)) as client:
            resp = await client.post(f"{base.rstrip('/')}/internal/jobs", json=payload)
            resp.raise_for_status()
    except Exception as exc:  # noqa: BLE001
        log.warning("dispatch failed: %s", exc)
    return job


async def cancel_worker_job(task: dict[str, Any], settings: Settings) -> None:
    """Best-effort notify the worker to kill the running asyncio job and HexStrike PIDs."""
    linked = task.get("linked_job_id")
    if not linked:
        return
    job_id = linked if isinstance(linked, UUID) else UUID(str(linked))
    try:
        job = crud.get_job(job_id)
    except Exception:  # noqa: BLE001
        return
    team = job.get("team") or "red"
    base = settings.red_worker_url if team == "red" else settings.blue_worker_url
    try:
        async with httpx.AsyncClient(timeout=httpx.Timeout(5.0, connect=2.0)) as client:
            resp = await client.post(f"{base.rstrip('/')}/internal/jobs/{job_id}/cancel")
            resp.raise_for_status()
    except Exception as exc:  # noqa: BLE001
        log.warning("worker cancel failed: %s", exc)
