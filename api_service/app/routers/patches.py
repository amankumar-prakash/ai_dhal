from uuid import UUID

from fastapi import APIRouter, Depends

from app.deps import Principal, require_jwt, require_jwt_or_service
from app.schemas.models import Patch, PatchCreate, PatchPatch
from app.services import crud

router = APIRouter(prefix="/patches", tags=["patches"])


@router.get("", response_model=list[Patch])
def list_patches(_: Principal = Depends(require_jwt)):
    return crud.list_patches()


@router.post("", response_model=Patch, status_code=201)
def create_patch(body: PatchCreate, principal: Principal = Depends(require_jwt_or_service)):
    uid = UUID(principal.user_id) if principal.user_id else None
    return crud.create_patch(body, created_by=uid)


@router.patch("/{patch_id}", response_model=Patch)
def update_patch(patch_id: UUID, body: PatchPatch, _: Principal = Depends(require_jwt_or_service)):
    return crud.patch_patch(patch_id, body)
