"""Task lifecycle service."""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from uuid import UUID, uuid4

from fastapi import HTTPException, status

from app.db.store import get_store
from app.deps import Principal, PrincipalKind
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


def list_tasks(principal: Principal, **filters: Any) -> list[dict[str, Any]]:
    rows = _store().list_all("tasks")
    if principal.kind == PrincipalKind.security_analyst:
        rows = [r for r in rows if str(r.get("assignee_id")) == principal.user_id]
    elif principal.kind != PrincipalKind.security_manager:
        raise HTTPException(status_code=403, detail="Cannot list tasks")
    for k, v in filters.items():
        if v is None:
            continue
        rows = [r for r in rows if str(r.get(k)) == str(v)]
    return rows


def create_task(body: TaskCreate, principal: Principal) -> dict[str, Any]:
    if principal.kind != PrincipalKind.security_manager:
        raise HTTPException(status_code=403, detail="Only Managers create tasks")
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
    is_mgr = principal.kind == PrincipalKind.security_manager
    is_an = principal.kind == PrincipalKind.security_analyst

    if body.action:
        return _transition(task, body.action, body.assignee_id, principal)

    # metadata edits — manager only
    meta = body.model_dump(exclude_unset=True, exclude={"action", "status", "linked_job_id"})
    if meta:
        if not is_mgr:
            raise HTTPException(status_code=403, detail="Only Managers edit task metadata")
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
        if not (is_mgr or (is_an and _is_assignee(task, principal))):
            raise HTTPException(status_code=403, detail="Cannot link job")
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
    is_mgr = principal.kind == PrincipalKind.security_manager
    is_an = principal.kind == PrincipalKind.security_analyst and _is_assignee(task, principal)

    def ok_analyst_or_mgr() -> None:
        if not (is_mgr or is_an):
            raise HTTPException(status_code=403, detail="Not allowed")

    patch: dict[str, Any] = {"updated_at": _now()}
    audit_action = action
    to_status = cur

    if action == "start":
        ok_analyst_or_mgr()
        if cur not in {"assigned", "blocked"}:
            raise HTTPException(status_code=400, detail=f"Cannot start from {cur}")
        to_status = "in_progress"
        patch["status"] = to_status
        patch["started_at"] = _now()
        if is_mgr and not _is_assignee(task, principal):
            audit_action = "started_on_behalf"
        else:
            audit_action = "started"
    elif action == "block":
        ok_analyst_or_mgr()
        if cur != "in_progress":
            raise HTTPException(status_code=400, detail="Can only block In Progress")
        to_status = "blocked"
        patch["status"] = to_status
        audit_action = "blocked"
    elif action == "unblock":
        ok_analyst_or_mgr()
        if cur != "blocked":
            raise HTTPException(status_code=400, detail="Not blocked")
        to_status = "in_progress"
        patch["status"] = to_status
        audit_action = "unblocked"
    elif action == "complete":
        ok_analyst_or_mgr()
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
        if not is_mgr:
            raise HTTPException(status_code=403, detail="Analysts cannot mark Reviewed")
        if cur != "completed":
            raise HTTPException(status_code=400, detail="Review requires Completed")
        to_status = "reviewed"
        patch["status"] = to_status
        audit_action = "reviewed"
    elif action == "close":
        if not is_mgr:
            raise HTTPException(status_code=403, detail="Analysts cannot Close")
        if cur not in {"reviewed", "completed"}:
            raise HTTPException(status_code=400, detail="Close requires Reviewed (or Completed)")
        to_status = "closed"
        patch["status"] = to_status
        patch["closed_at"] = _now()
        audit_action = "closed"
    elif action == "reassign":
        if not is_mgr:
            raise HTTPException(status_code=403, detail="Only Managers reassign")
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
        if not is_mgr:
            raise HTTPException(status_code=403, detail="Only Managers assign")
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
    is_mgr = principal.kind == PrincipalKind.security_manager
    if not (is_mgr or (principal.kind == PrincipalKind.security_analyst and _is_assignee(task, principal))):
        raise HTTPException(status_code=403, detail="Cannot note on this task")
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
    is_mgr = principal.kind == PrincipalKind.security_manager
    if not (is_mgr or (principal.kind == PrincipalKind.security_analyst and _is_assignee(task, principal))):
        raise HTTPException(status_code=403, detail="Cannot link on this task")
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
