from uuid import UUID

from fastapi import APIRouter, Depends, Query

from app.deps import Principal, require_ops_reader, require_jwt_or_service
from app.schemas.models import Finding, FindingCreate, FindingPatch
from app.services import crud
from app.services.scope import filter_ops_rows

router = APIRouter(prefix="/findings", tags=["findings"])


@router.get("", response_model=list[Finding])
def list_findings(team: str | None = Query(None), principal: Principal = Depends(require_ops_reader)):
    return filter_ops_rows(crud.list_findings(team=team), principal)


@router.post("", response_model=Finding, status_code=201)
def create_finding(body: FindingCreate, _: Principal = Depends(require_jwt_or_service)):
    return crud.create_finding(body)


@router.patch("/{finding_id}", response_model=Finding)
def patch_finding(
    finding_id: UUID,
    body: FindingPatch,
    _: Principal = Depends(require_jwt_or_service),
):
    return crud.patch_finding(finding_id, body)
