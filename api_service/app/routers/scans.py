from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.deps import Principal, PrincipalKind, deny_user_mutate, require_ops_reader, require_jwt_or_service
from app.schemas.models import Scan, ScanCreate, ScanPatch
from app.services import crud
from app.services.scope import filter_ops_rows

router = APIRouter(prefix="/scans", tags=["scans"])


@router.get("", response_model=list[Scan])
def list_scans(team: str | None = Query(None), principal: Principal = Depends(require_ops_reader)):
    return filter_ops_rows(crud.list_scans(team=team), principal)


@router.post("", response_model=Scan, status_code=201)
def create_scan(body: ScanCreate, principal: Principal = Depends(require_ops_reader)):
    deny_user_mutate(principal)
    uid = UUID(principal.user_id) if principal.user_id else None
    return crud.create_scan(body, created_by=uid)


@router.patch("/{scan_id}", response_model=Scan)
def patch_scan(scan_id: UUID, body: ScanPatch, _: Principal = Depends(require_jwt_or_service)):
    return crud.patch_scan(scan_id, body)


@router.delete("/{scan_id}", status_code=204)
def delete_scan(scan_id: UUID, principal: Principal = Depends(require_ops_reader)):
    if principal.kind != PrincipalKind.security_manager:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Manager required")
    crud.delete_scan(scan_id)
