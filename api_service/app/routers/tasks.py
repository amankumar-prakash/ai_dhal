from uuid import UUID

from fastapi import APIRouter, Depends, Query

from app.deps import Principal, require_manager_or_analyst
from app.schemas.models import TaskCreate, TaskLinkCreate, TaskNoteCreate, TaskPatch
from app.services import tasks as task_svc

router = APIRouter(prefix="/tasks", tags=["tasks"])


@router.get("")
def list_tasks(
    principal: Principal = Depends(require_manager_or_analyst),
    status: str | None = Query(None),
    task_type: str | None = Query(None),
    assignee_id: UUID | None = Query(None),
):
    return task_svc.list_tasks(principal, status=status, task_type=task_type, assignee_id=assignee_id)


@router.post("", status_code=201)
def create_task(body: TaskCreate, principal: Principal = Depends(require_manager_or_analyst)):
    return task_svc.create_task(body, principal)


@router.get("/{task_id}")
def get_task(task_id: UUID, principal: Principal = Depends(require_manager_or_analyst)):
    task = task_svc.get_task(task_id)
    # analyst own-only
    from app.deps import PrincipalKind

    if principal.kind == PrincipalKind.security_analyst and str(task.get("assignee_id")) != principal.user_id:
        from fastapi import HTTPException

        raise HTTPException(status_code=403, detail="Not your task")
    return task


@router.patch("/{task_id}")
def patch_task(task_id: UUID, body: TaskPatch, principal: Principal = Depends(require_manager_or_analyst)):
    return task_svc.apply_patch(task_id, body, principal)


@router.get("/{task_id}/notes")
def list_notes(task_id: UUID, _: Principal = Depends(require_manager_or_analyst)):
    return task_svc.list_notes(task_id)


@router.post("/{task_id}/notes", status_code=201)
def add_note(task_id: UUID, body: TaskNoteCreate, principal: Principal = Depends(require_manager_or_analyst)):
    return task_svc.add_note(task_id, body, principal)


@router.get("/{task_id}/links")
def list_links(task_id: UUID, _: Principal = Depends(require_manager_or_analyst)):
    return task_svc.list_links(task_id)


@router.post("/{task_id}/links", status_code=201)
def add_link(task_id: UUID, body: TaskLinkCreate, principal: Principal = Depends(require_manager_or_analyst)):
    return task_svc.add_link(task_id, body, principal)


@router.get("/{task_id}/audit")
def list_audit(task_id: UUID, _: Principal = Depends(require_manager_or_analyst)):
    return task_svc.list_audit(task_id)
