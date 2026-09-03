"""Task lifecycle service."""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from uuid import UUID, uuid4

from fastapi import HTTPException

from app.db.store import get_store
from app.deps import Principal
from app.schemas.models import TaskCreate, TaskLinkCreate, TaskNoteCreate, TaskPatch
from app.services import notifications as notif_svc


def _store():
    return get_store()


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _audit(
    task_id: UUID,
    actor_id: UUID | None,
    action: str,
    *,
    from_status: str | None = None,
    to_status: str | None = None,
    from_assignee: UUID | None = None,
    to_assignee: UUID | None = None,
    message: str | None = None,
) -> None:
    _store().create(
        "task_audit_events",
        {
            "id": uuid4(),
            "task_id": task_id,
            "actor_id": actor_id,
            "action": action,
            "from_status": from_status,
            "to_status": to_status,
            "from_assignee": from_assignee,
            "to_assignee": to_assignee,
            "message": message,
            "created_at": _now(),
        },
    )


def get_task(task_id: UUID) -> dict[str, Any]:
    row = _store().get("tasks", task_id)
    if not row:
        raise HTTPException(status_code=404, detail="Task not found")
    return row


def list_tasks(_principal: Principal, **filters: Any) -> list[dict[str, Any]]:
    rows = _store().list_all("tasks")
    for k, v in filters.items():
        if v is None:
            continue
        rows = [r for r in rows if str(r.get(k)) == str(v)]
    return rows


def create_task(body: TaskCreate, principal: Principal) -> dict[str, Any]:
    assert principal.user_id
    manager = UUID(principal.user_id)
    status_val = "assigned" if body.assignee_id else "draft"
    row = _store().create(
        "tasks",
        {
            "id": uuid4(),
            "target": body.target,
            "description": body.description,
            "patch_scope": body.patch_scope,
            "asset_id": body.asset_id,
            "task_type": body.task_type,
            "status": status_val,
            "created_by": manager,
            "assignee_id": body.assignee_id,
            "assigning_manager_id": manager,
            "linked_job_id": None,
            "created_at": _now(),
            "updated_at": _now(),
        },
    )
    tid = row["id"] if isinstance(row["id"], UUID) else UUID(str(row["id"]))
    _audit(tid, manager, "created", to_status=status_val)
    if body.assignee_id:
        _audit(tid, manager, "assigned", to_status="assigned", to_assignee=body.assignee_id)
        notif_svc.notify(
            body.assignee_id,
            "task_assigned",
            "Task assigned",
            f"You were assigned: {body.target}",
            tid,
        )
    return row


def _assert_not_closed(task: dict[str, Any]) -> None:
    if task.get("status") == "closed":
        raise HTTPException(status_code=400, detail="Closed tasks are read-only")


def _is_assignee(task: dict[str, Any], principal: Principal) -> bool:
    return str(task.get("assignee_id")) == principal.user_id


def apply_patch(task_id: UUID, body: TaskPatch, principal: Principal) -> dict[str, Any]:
    task = get_task(task_id)
    _assert_not_closed(task)
    assert principal.user_id
    actor = UUID(principal.user_id)

    if body.action:
        return _transition(task, body.action, body.assignee_id, principal)

    meta = body.model_dump(exclude_unset=True, exclude={"action", "status", "linked_job_id"})
    if meta:
        if "assignee_id" in meta and meta["assignee_id"]:
            prev = task.get("assignee_id")
            meta["status"] = "assigned"
            meta["updated_at"] = _now()
            updated = _store().update("tasks", task_id, meta)
            assert updated
            _audit(
                task_id,
                actor,
                "assigned" if not prev else "reassigned",
                from_status=task.get("status"),
                to_status="assigned",
                from_assignee=prev if isinstance(prev, UUID) else (UUID(str(prev)) if prev else None),
                to_assignee=meta["assignee_id"],
            )
            if prev and str(prev) != str(meta["assignee_id"]):
                notif_svc.notify(
                    prev if isinstance(prev, UUID) else UUID(str(prev)),
                    "task_reassigned",
                    "Task reassigned",
                    f"Task no longer yours: {task.get('target')}",
                    task_id,
                )
            notif_svc.notify(
                meta["assignee_id"],
                "task_assigned",
                "Task assigned",
                f"You were assigned: {task.get('target')}",
                task_id,
            )
            return updated
        meta["updated_at"] = _now()
        return _store().update("tasks", task_id, meta) or task

    if body.linked_job_id is not None:
        return _store().update("tasks", task_id, {"linked_job_id": body.linked_job_id, "updated_at": _now()}) or task

    raise HTTPException(status_code=400, detail="No changes")


def _transition(
    task: dict[str, Any],
    action: str,
    new_assignee: UUID | None,
    principal: Principal,
) -> dict[str, Any]:
    assert principal.user_id
    actor = UUID(principal.user_id)
    task_id = task["id"] if isinstance(task["id"], UUID) else UUID(str(task["id"]))
    cur = str(task.get("status"))

    patch: dict[str, Any] = {"updated_at": _now()}
    audit_action = action
    to_status = cur

    if action == "start":
        if cur == "in_progress":
            from app.services import crud

            linked = task.get("linked_job_id")
            existing = None
            if linked:
                try:
                    existing = crud.get_job(
                        linked if isinstance(linked, UUID) else UUID(str(linked))
                    )
                except HTTPException:
                    existing = None
            if existing and str(existing.get("status")) not in {"failed", "cancelled"}:
                raise HTTPException(status_code=400, detail="Task already started")
        elif cur not in {"assigned", "blocked", "draft"}:
            raise HTTPException(status_code=400, detail=f"Cannot start from {cur}")
        to_status = "in_progress"
        patch["status"] = to_status
        patch["started_at"] = _now()
        if not _is_assignee(task, principal):
            audit_action = "started_on_behalf"
        else:
            audit_action = "started"
    elif action == "block":
        if cur != "in_progress":
            raise HTTPException(status_code=400, detail="Can only block In Progress")
        to_status = "blocked"
        patch["status"] = to_status
        audit_action = "blocked"
    elif action == "unblock":
        if cur != "blocked":
            raise HTTPException(status_code=400, detail="Not blocked")
        to_status = "in_progress"
        patch["status"] = to_status
        audit_action = "unblocked"
    elif action == "complete":
        if cur not in {"in_progress", "blocked"}:
            raise HTTPException(status_code=400, detail=f"Cannot complete from {cur}")
        to_status = "completed"
        patch["status"] = to_status
        patch["completed_at"] = _now()
        audit_action = "completed"
        mgr = task.get("assigning_manager_id")
        if mgr:
            mid = mgr if isinstance(mgr, UUID) else UUID(str(mgr))
            notif_svc.notify(
                mid,
                "task_completed_for_review",
                "Task ready for review",
                f"Completed: {task.get('target')}",
                task_id,
            )
    elif action == "review":
        if cur != "completed":
            raise HTTPException(status_code=400, detail="Review requires Completed")
        to_status = "reviewed"
        patch["status"] = to_status
        audit_action = "reviewed"
    elif action == "close":
        if cur not in {"reviewed", "completed"}:
            raise HTTPException(status_code=400, detail="Close requires Reviewed (or Completed)")
        to_status = "closed"
        patch["status"] = to_status
        patch["closed_at"] = _now()
        audit_action = "closed"
    elif action == "reassign":
        if not new_assignee:
            raise HTTPException(status_code=400, detail="assignee_id required")
        prev = task.get("assignee_id")
        to_status = "assigned"
        patch["status"] = to_status
        patch["assignee_id"] = new_assignee
        audit_action = "reassigned"
        if prev:
            pid = prev if isinstance(prev, UUID) else UUID(str(prev))
            notif_svc.notify(
                pid,
                "task_reassigned",
                "Task reassigned",
                f"Task no longer yours: {task.get('target')}",
                task_id,
            )
        notif_svc.notify(
            new_assignee,
            "task_assigned",
            "Task assigned",
            f"You were assigned: {task.get('target')}",
            task_id,
        )
        _audit(
            task_id,
            actor,
            audit_action,
            from_status=cur,
            to_status=to_status,
            from_assignee=prev if isinstance(prev, UUID) else (UUID(str(prev)) if prev else None),
            to_assignee=new_assignee,
        )
        updated = _store().update("tasks", task_id, patch)
        assert updated
        return updated
    elif action == "assign":
        if not new_assignee:
            raise HTTPException(status_code=400, detail="assignee_id required")
        to_status = "assigned"
        patch["status"] = to_status
        patch["assignee_id"] = new_assignee
        audit_action = "assigned"
        notif_svc.notify(
            new_assignee,
            "task_assigned",
            "Task assigned",
            f"You were assigned: {task.get('target')}",
            task_id,
        )
    else:
        raise HTTPException(status_code=400, detail=f"Unknown action {action}")

    _audit(task_id, actor, audit_action, from_status=cur, to_status=to_status)
    updated = _store().update("tasks", task_id, patch)
    assert updated
    return updated


def add_note(task_id: UUID, body: TaskNoteCreate, principal: Principal) -> dict[str, Any]:
    task = get_task(task_id)
    _assert_not_closed(task)
    assert principal.user_id
    note = _store().create(
        "task_notes",
        {
            "id": uuid4(),
            "task_id": task_id,
            "author_id": UUID(principal.user_id),
            "body": body.body,
            "created_at": _now(),
        },
    )
    _audit(task_id, UUID(principal.user_id), "note_added", message=body.body[:200])
    return note


def add_link(task_id: UUID, body: TaskLinkCreate, principal: Principal) -> dict[str, Any]:
    task = get_task(task_id)
    _assert_not_closed(task)
    assert principal.user_id
    table = "findings" if body.kind == "finding" else "scans"
    if not _store().get(table, body.ref_id):
        raise HTTPException(status_code=404, detail=f"{body.kind} not found")
    link = _store().create(
        "task_links",
        {
            "id": uuid4(),
            "task_id": task_id,
            "author_id": UUID(principal.user_id),
            "kind": body.kind,
            "ref_id": body.ref_id,
            "created_at": _now(),
        },
    )
    _audit(task_id, UUID(principal.user_id), "link_added", message=f"{body.kind}:{body.ref_id}")
    return link


def list_notes(task_id: UUID) -> list[dict[str, Any]]:
    get_task(task_id)
    return [r for r in _store().list_all("task_notes") if str(r.get("task_id")) == str(task_id)]


def list_links(task_id: UUID) -> list[dict[str, Any]]:
    get_task(task_id)
    return [r for r in _store().list_all("task_links") if str(r.get("task_id")) == str(task_id)]


def list_audit(task_id: UUID) -> list[dict[str, Any]]:
    get_task(task_id)
    return [r for r in _store().list_all("task_audit_events") if str(r.get("task_id")) == str(task_id)]


def complete_linked_task_for_job(job_id: UUID) -> None:
    """Mark the task that owns this job as completed so Attack Chain / Patches unlock."""
    now = _now()
    for task in _store().list_all("tasks"):
        if str(task.get("linked_job_id")) != str(job_id):
            continue
        if str(task.get("status")) in {"completed", "reviewed", "closed"}:
            continue
        tid = task["id"] if isinstance(task["id"], UUID) else UUID(str(task["id"]))
        _store().update(
            "tasks",
            tid,
            {"status": "completed", "completed_at": now, "updated_at": now},
        )
        mgr = task.get("assigning_manager_id")
        if mgr:
            mid = mgr if isinstance(mgr, UUID) else UUID(str(mgr))
            notif_svc.notify(
                mid,
                "task_completed_for_review",
                "Task ready for review",
                f"Completed: {task.get('target')}",
                tid,
            )


def _task_uuid(task: dict[str, Any]) -> UUID:
    return task["id"] if isinstance(task["id"], UUID) else UUID(str(task["id"]))


def ensure_task_asset(task: dict[str, Any]) -> UUID:
    from app.schemas.models import AssetCreate
    from app.services import crud

    if task.get("asset_id"):
        return task["asset_id"] if isinstance(task["asset_id"], UUID) else UUID(str(task["asset_id"]))

    from app.services.targets import parse_target

    parsed = parse_target(str(task.get("target") or ""))
    hostname = str(parsed["hostname"] or task.get("target") or "unknown")
    ip = hostname if hostname.replace(".", "").isdigit() or ":" in hostname else "0.0.0.0"
    asset = crud.create_asset(
        AssetCreate(name=str(task.get("target") or hostname), hostname=hostname, ip_address=ip)
    )
    aid = asset["id"] if isinstance(asset["id"], UUID) else UUID(str(asset["id"]))
    tid = _task_uuid(task)
    _store().update("tasks", tid, {"asset_id": aid, "updated_at": _now()})
    task["asset_id"] = aid
    return aid


async def start_discovery_run(task: dict[str, Any], principal: Principal) -> tuple[dict[str, Any], dict[str, Any] | None]:
    """Create a red task-discovery job. Returns (task, job_to_dispatch_or_None)."""
    if str(task.get("task_type") or "red") == "blue":
        return task, None
    linked = task.get("linked_job_id")
    if linked:
        from app.services import crud

        try:
            existing = crud.get_job(linked if isinstance(linked, UUID) else UUID(str(linked)))
        except HTTPException:
            existing = None
        if existing and str(existing.get("status")) not in {"failed", "cancelled"}:
            return task, None

    from app.schemas.models import JobCreate
    from app.services import crud

    asset_id = ensure_task_asset(task)
    uid = UUID(principal.user_id) if principal.user_id else None
    job = crud.create_job(
        JobCreate(team="red", profile="task-discovery", asset_ids=[asset_id]),
        requested_by=uid,
    )
    tid = _task_uuid(task)
    jid = job["id"] if isinstance(job["id"], UUID) else UUID(str(job["id"]))
    updated = _store().update("tasks", tid, {"linked_job_id": jid, "updated_at": _now()})
    assert updated
    return get_task(tid), job


def get_task_results(task_id: UUID) -> dict[str, Any]:
    """Assemble job, tool runs, findings, chain, and patches for a task."""
    from app.services import crud

    task = get_task(task_id)
    job = None
    tools: list[dict[str, Any]] = []
    findings: list[dict[str, Any]] = []
    patches: list[dict[str, Any]] = []
    chain: dict[str, Any] | None = None

    linked = task.get("linked_job_id")
    if not linked:
        return {"task": task, "job": None, "tools": [], "findings": [], "chain": None, "patches": []}

    job_id = linked if isinstance(linked, UUID) else UUID(str(linked))
    try:
        job = crud.get_job(job_id)
    except HTTPException:
        job = None

    tools = crud.list_tool_runs(job_id)
    scans = crud.scans_for_job(job_id)
    scan_ids = {str(s["id"]) for s in scans}
    asset_ids = {str(s.get("asset_id")) for s in scans if s.get("asset_id")}
    if task.get("asset_id"):
        asset_ids.add(str(task["asset_id"]))

    for finding in crud.list_findings():
        if str(finding.get("scan_id") or "") in scan_ids or str(finding.get("asset_id") or "") in asset_ids:
            findings.append(finding)

    finding_ids = {str(f["id"]) for f in findings}
    patches = [
        p for p in crud.list_patches() if str(p.get("finding_id") or "") in finding_ids
    ]

    chosen = None
    for c in crud.list_chains():
        if str(c.get("scan_id") or "") in scan_ids:
            chosen = c
            break
    if chosen is None and scan_ids:
        # Chains created without scan_id still belong to this run if named with the job.
        job_short = str(job_id)[:8]
        for c in crud.list_chains():
            if job_short in str(c.get("name") or ""):
                chosen = c
                break
    if chosen is not None:
        cid = chosen["id"] if isinstance(chosen["id"], UUID) else UUID(str(chosen["id"]))
        steps = crud.list_chain_steps(cid)
        steps = sorted(steps, key=lambda s: int(s.get("sequence") or 0))
        chain = {**chosen, "steps": steps}

    return {
        "task": task,
        "job": job,
        "tools": tools,
        "findings": findings,
        "chain": chain,
        "patches": patches,
    }

