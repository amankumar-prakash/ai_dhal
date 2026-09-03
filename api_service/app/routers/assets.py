from uuid import UUID

from fastapi import APIRouter, Depends

from app.deps import Principal, deny_service_destructive, require_ops_reader
from app.schemas.models import Asset, AssetCreate
from app.services import crud

router = APIRouter(prefix="/assets", tags=["assets"])


@router.get("", response_model=list[Asset])
def list_assets(_: Principal = Depends(require_ops_reader)):
    return crud.list_assets()


@router.post("", response_model=Asset, status_code=201)
def create_asset(body: AssetCreate, _: Principal = Depends(require_ops_reader)):
    return crud.create_asset(body)


@router.get("/{asset_id}", response_model=Asset)
def get_asset(asset_id: UUID, _: Principal = Depends(require_ops_reader)):
    return crud.get_asset(asset_id)


@router.patch("/{asset_id}", response_model=Asset)
def update_asset(asset_id: UUID, body: AssetCreate, _: Principal = Depends(require_ops_reader)):
    return crud.update_asset(asset_id, body)


@router.delete("/{asset_id}", status_code=204)
def delete_asset(asset_id: UUID, principal: Principal = Depends(require_ops_reader)):
    deny_service_destructive(principal)
    crud.delete_asset(asset_id)
