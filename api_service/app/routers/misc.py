from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status

from app.deps import Principal, PrincipalKind, deny_service_destructive, require_jwt, require_jwt_or_service, require_service
from app.schemas.models import AttackChainCreate, AttackChainStepCreate, RoleAssign, ToolRunCreate
from app.services import crud

router_chains = APIRouter(prefix="/attack-chains", tags=["attack-chains"])
router_roles = APIRouter(prefix="/roles", tags=["roles"])
router_tools = APIRouter(prefix="/tool-runs", tags=["tool-runs"])


@router_chains.get("")
def list_chains(_: Principal = Depends(require_jwt)):
    return crud.list_chains()


@router_chains.post("", status_code=201)
def create_chain(body: AttackChainCreate, _: Principal = Depends(require_jwt_or_service)):
    return crud.create_chain(body.name, body.scan_id, body.team)


@router_chains.get("/{chain_id}/steps")
def list_steps(chain_id: UUID, _: Principal = Depends(require_jwt)):
    return crud.list_chain_steps(chain_id)


@router_chains.post("/{chain_id}/steps", status_code=201)
def add_step(chain_id: UUID, body: AttackChainStepCreate, _: Principal = Depends(require_jwt_or_service)):
    return crud.add_chain_step(chain_id, body.model_dump())


@router_roles.get("")
def list_roles(_: Principal = Depends(require_jwt)):
    return crud.list_roles()


@router_roles.post("", status_code=201)
def assign_role(body: RoleAssign, principal: Principal = Depends(require_jwt)):
    deny_service_destructive(principal)
    if principal.kind != PrincipalKind.admin:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin required")
    return crud.assign_role(body.user_id, body.role)


@router_tools.post("", status_code=201)
def create_tool_run(body: ToolRunCreate, _: Principal = Depends(require_service)):
    return crud.create_tool_run(body)
