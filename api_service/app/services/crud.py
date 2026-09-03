"""CRUD + job helpers over memory or supabase store."""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from uuid import UUID, uuid4

from fastapi import HTTPException, status

from app.db.store import get_store
from app.schemas.models import (
    AssetCreate,
    FindingCreate,
    FindingPatch,
    JobCreate,
    JobPatch,
    PatchCreate,
    PatchPatch,
    ScanCreate,
    ScanPatch,
    ThreatEventCreate,
    ToolRunCreate,
)


TERMINAL_JOB = {"completed", "failed", "cancelled"}


def _store():
    return get_store()



def create_asset(body: AssetCreate) -> dict[str, Any]:
    return _store().create(
        "assets",
        {
            "id": uuid4(),
            "name": body.name,
            "hostname": body.hostname or body.name,
            "ip_address": body.ip_address or "0.0.0.0",
            "kind": body.kind or "host",
            "criticality": body.criticality or "medium",
        },
    )


def list_assets() -> list[dict[str, Any]]:
    return _store().list_all("assets")


def get_asset(asset_id: UUID) -> dict[str, Any]:
    row = _store().get("assets", asset_id)
    if not row:
        raise HTTPException(status_code=404, detail="Asset not found")
    return row


def update_asset(asset_id: UUID, body: AssetCreate) -> dict[str, Any]:
    get_asset(asset_id)
    row = _store().update("assets", asset_id, body.model_dump(exclude_unset=True))
    assert row
    return row


def delete_asset(asset_id: UUID) -> None:
    if not _store().delete("assets", asset_id):
        raise HTTPException(status_code=404, detail="Asset not found")


def list_scans(team: str | None = None) -> list[dict[str, Any]]:
    return _store().list_all("scans", team=team) if team else _store().list_all("scans")


def create_scan(body: ScanCreate, created_by: UUID | None = None) -> dict[str, Any]:
    return _store().create(
        "scans",
        {
            "id": uuid4(),
            "target": body.target,
            "asset_id": body.asset_id,
            "profile": body.profile,
            "status": "queued",
            "team": body.team,
            "job_id": None,
            "source_service": None,
            "findings_count": 0,
            "started_at": datetime.now(timezone.utc),
            "finished_at": None,
            "created_by": created_by,
        },
    )


def patch_scan(scan_id: UUID, body: ScanPatch) -> dict[str, Any]:
    row = _store().get("scans", scan_id)
    if not row:
        raise HTTPException(status_code=404, detail="Scan not found")
    updated = _store().update("scans", scan_id, body.model_dump(exclude_unset=True))
    assert updated
    return updated


def delete_scan(scan_id: UUID) -> None:
    if not _store().delete("scans", scan_id):
        raise HTTPException(status_code=404, detail="Scan not found")


def list_findings(team: str | None = None) -> list[dict[str, Any]]:
    return _store().list_all("findings", team=team) if team else _store().list_all("findings")


def create_finding(body: FindingCreate) -> dict[str, Any]:
    data = body.model_dump()
    data.setdefault("cvss", 0.0)
    data.setdefault("detected_at", datetime.now(timezone.utc))
    data.setdefault("resolved_at", None)
    data.setdefault("evidence", [])
    return _store().create("findings", {"id": uuid4(), **data})


def patch_finding(finding_id: UUID, body: FindingPatch) -> dict[str, Any]:
    if not _store().get("findings", finding_id):
        raise HTTPException(status_code=404, detail="Finding not found")
    row = _store().update("findings", finding_id, body.model_dump(exclude_unset=True))
    assert row
    return row


def list_threat_events(team: str | None = None) -> list[dict[str, Any]]:
    return _store().list_all("threat_events", team=team) if team else _store().list_all("threat_events")


def create_threat_event(body: ThreatEventCreate) -> dict[str, Any]:
    data = body.model_dump()
    data["id"] = uuid4()
    data["occurred_at"] = datetime.now(timezone.utc)
    data.setdefault("technique", "T0000")
    data.setdefault("description", data.get("technique_name") or "event")
    data.setdefault("source_ip", "0.0.0.0")
    return _store().create("threat_events", data)


def create_job(body: JobCreate, requested_by: UUID | None) -> dict[str, Any]:
    if not body.asset_ids:
        raise HTTPException(status_code=422, detail="asset_ids required")
    job = _store().create(
        "jobs",
        {
            "id": uuid4(),
            "team": body.team,
            "profile": body.profile,
            "status": "queued",
            "asset_ids": list(body.asset_ids),
            "requested_by": requested_by,
            "error": None,
            "started_at": None,
            "finished_at": None,
        },
    )
    for asset_id in body.asset_ids:
        asset = _store().get("assets", asset_id)
        target = (asset or {}).get("hostname") or (asset or {}).get("name") or str(asset_id)
        _store().create(
            "scans",
            {
                "id": uuid4(),
                "target": target,
                "asset_id": asset_id,
                "profile": body.profile,
                "status": "queued",
                "team": body.team,
                "job_id": job["id"],
                "source_service": None,
                "findings_count": 0,
                "started_at": datetime.now(timezone.utc),
                "finished_at": None,
                "created_by": requested_by,
            },
        )
    return job


def list_jobs(team: str | None = None) -> list[dict[str, Any]]:
    return _store().list_all("jobs", team=team) if team else _store().list_all("jobs")


def get_job(job_id: UUID) -> dict[str, Any]:
    row = _store().get("jobs", job_id)
    if not row:
        raise HTTPException(status_code=404, detail="Job not found")
    return row


def patch_job(job_id: UUID, body: JobPatch) -> dict[str, Any]:
    job = get_job(job_id)
    if job["status"] in TERMINAL_JOB:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Job is terminal")
    data = body.model_dump(exclude_unset=True)
    if data.get("status") in {"completed", "failed", "cancelled"}:
        data.setdefault("finished_at", datetime.now(timezone.utc))
    row = _store().update("jobs", job_id, data)
    assert row
    if data.get("status") == "completed":
        from app.services.tasks import complete_linked_task_for_job

        complete_linked_task_for_job(job_id)
    return row


def cancel_job(job_id: UUID) -> dict[str, Any]:
    job = get_job(job_id)
    if job["status"] in TERMINAL_JOB:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Job is terminal")
    row = _store().update(
        "jobs",
        job_id,
        {"status": "cancelled", "finished_at": datetime.now(timezone.utc)},
    )
    assert row
    return row


def create_patch(body: PatchCreate, created_by: UUID | None) -> dict[str, Any]:
    if not _store().get("findings", body.finding_id):
        raise HTTPException(status_code=404, detail="Finding not found")
    return _store().create(
        "patches",
        {
            "id": uuid4(),
            "finding_id": body.finding_id,
            "asset_id": body.asset_id,
            "title": body.title,
            "playbook": body.playbook,
            "status": "proposed",
            "evidence": [],
            "created_by": created_by,
            "applied_at": None,
        },
    )


def list_patches() -> list[dict[str, Any]]:
    return _store().list_all("patches")


def patch_patch(patch_id: UUID, body: PatchPatch) -> dict[str, Any]:
    row = _store().get("patches", patch_id)
    if not row:
        raise HTTPException(status_code=404, detail="Patch not found")
    data = body.model_dump(exclude_unset=True)
    if data.get("status") == "applied":
        data["applied_at"] = datetime.now(timezone.utc)
        _store().update("findings", row["finding_id"], {"status": "remediated"})
    elif data.get("status") == "failed":
        # finding stays open
        pass
    updated = _store().update("patches", patch_id, data)
    assert updated
    return updated


def create_tool_run(body: ToolRunCreate) -> dict[str, Any]:
    get_job(body.job_id)
    return _store().create("tool_runs", {"id": uuid4(), **body.model_dump()})


def list_tool_runs(job_id: UUID | None = None) -> list[dict[str, Any]]:
    rows = _store().list_all("tool_runs")
    if job_id is None:
        return rows
    return [r for r in rows if str(r.get("job_id")) == str(job_id)]


def scans_for_job(job_id: UUID) -> list[dict[str, Any]]:
    return [r for r in _store().list_all("scans") if str(r.get("job_id")) == str(job_id)]


def create_chain(name: str, scan_id: UUID | None, team: str) -> dict[str, Any]:
    return _store().create(
        "attack_chains",
        {"id": uuid4(), "name": name, "scan_id": scan_id, "team": team},
    )


def add_chain_step(chain_id: UUID, step: dict[str, Any]) -> dict[str, Any]:
    if not _store().get("attack_chains", chain_id):
        raise HTTPException(status_code=404, detail="Chain not found")
    return _store().create("attack_chain_steps", {"id": uuid4(), "chain_id": chain_id, **step})


def list_chains() -> list[dict[str, Any]]:
    return _store().list_all("attack_chains")


def list_chain_steps(chain_id: UUID) -> list[dict[str, Any]]:
    return [r for r in _store().list_all("attack_chain_steps") if str(r.get("chain_id")) == str(chain_id)]


def list_roles() -> list[dict[str, Any]]:
    return _store().list_all("roles")


def assign_role(user_id: UUID, role: str) -> dict[str, Any]:
    from app.services import identity

    return identity.set_role(user_id, role)
