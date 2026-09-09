from uuid import UUID

from fastapi import APIRouter, BackgroundTasks, Depends, Query

from app.config import get_settings
from app.deps import Principal, require_ops_reader
from app.schemas.models import TaskCreate, TaskLinkCreate, TaskNoteCreate, TaskPatch
from app.services import tasks as task_svc

router = APIRouter(prefix="/tasks", tags=["tasks"])


async def _dispatch_started(job: dict, task: dict) -> None:
    from app.services.dispatch import dispatch_job

    await dispatch_job(job, get_settings(), task=task)


async def _cancel_worker(task: dict) -> None:
    from app.services.dispatch import cancel_worker_job

    await cancel_worker_job(task, get_settings())


@router.get("")
def list_tasks(
    principal: Principal = Depends(require_ops_reader),
    status: str | None = Query(None),
    task_type: str | None = Query(None),
    assignee_id: UUID | None = Query(None),
):
    return task_svc.list_tasks(principal, status=status, task_type=task_type, assignee_id=assignee_id)


@router.post("", status_code=201)
def create_task(body: TaskCreate, principal: Principal = Depends(require_ops_reader)):
    return task_svc.create_task(body, principal)


@router.get("/{task_id}/results")
def get_task_results(task_id: UUID, _: Principal = Depends(require_ops_reader)):
    return task_svc.get_task_results(task_id)


@router.get("/{task_id}")
def get_task(task_id: UUID, _: Principal = Depends(require_ops_reader)):
    return task_svc.get_task(task_id)


@router.patch("/{task_id}")
async def patch_task(
    task_id: UUID,
    body: TaskPatch,
    background: BackgroundTasks,
    principal: Principal = Depends(require_ops_reader),
):
    updated = task_svc.apply_patch(task_id, body, principal)
    if body.action == "start":
        updated, job = await task_svc.start_discovery_run(updated, principal)
        if job:
            background.add_task(_dispatch_started, job, updated)
    elif body.action == "stop":
        background.add_task(_cancel_worker, updated)
    return updated


@router.get("/{task_id}/notes")
def list_notes(task_id: UUID, _: Principal = Depends(require_ops_reader)):
    return task_svc.list_notes(task_id)


@router.post("/{task_id}/notes", status_code=201)
def add_note(task_id: UUID, body: TaskNoteCreate, principal: Principal = Depends(require_ops_reader)):
    return task_svc.add_note(task_id, body, principal)


@router.get("/{task_id}/links")
def list_links(task_id: UUID, _: Principal = Depends(require_ops_reader)):
    return task_svc.list_links(task_id)


@router.post("/{task_id}/links", status_code=201)
def add_link(task_id: UUID, body: TaskLinkCreate, principal: Principal = Depends(require_ops_reader)):
    return task_svc.add_link(task_id, body, principal)


@router.get("/{task_id}/audit")
def list_audit(task_id: UUID, _: Principal = Depends(require_ops_reader)):
    return task_svc.list_audit(task_id)
