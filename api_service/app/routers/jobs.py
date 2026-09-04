from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query

from app.config import Settings, get_settings
from app.deps import Principal, require_jwt, require_jwt_or_service, require_service
from app.schemas.models import Job, JobCreate, JobPatch, JobProgressCreate
from app.services import crud
from app.services.dispatch import dispatch_job

router = APIRouter(prefix="/jobs", tags=["jobs"])


@router.get("", response_model=list[Job])
def list_jobs(team: str | None = Query(None), _: Principal = Depends(require_jwt)):
    return crud.list_jobs(team=team)


@router.post("", response_model=Job, status_code=201)
async def create_job(
    body: JobCreate,
    principal: Principal = Depends(require_jwt),
    settings: Settings = Depends(get_settings),
):
    if not body.asset_ids:
        raise HTTPException(status_code=422, detail="asset_ids minItems 1")
    uid = UUID(principal.user_id) if principal.user_id else None
    job = crud.create_job(body, requested_by=uid)
    return await dispatch_job(job, settings)


@router.get("/{job_id}", response_model=Job)
def get_job(job_id: UUID, _: Principal = Depends(require_jwt_or_service)):
    return crud.get_job(job_id)


@router.patch("/{job_id}", response_model=Job)
def patch_job(job_id: UUID, body: JobPatch, _: Principal = Depends(require_jwt_or_service)):
    return crud.patch_job(job_id, body)


@router.post("/{job_id}/cancel", response_model=Job)
def cancel_job(job_id: UUID, _: Principal = Depends(require_jwt)):
    return crud.cancel_job(job_id)


@router.post("/{job_id}/progress", status_code=201)
def append_progress(
    job_id: UUID,
    body: JobProgressCreate,
    _: Principal = Depends(require_service),
):
    return crud.append_job_progress(job_id, body.kind, body.message, body.meta)
