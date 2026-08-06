from fastapi import APIRouter, Depends, Query

from app.deps import Principal, require_ops_reader, require_jwt_or_service
from app.schemas.models import ThreatEvent, ThreatEventCreate
from app.services import crud
from app.services.scope import filter_ops_rows

router = APIRouter(prefix="/threat-events", tags=["threat-events"])


@router.get("", response_model=list[ThreatEvent])
def list_events(team: str | None = Query(None), principal: Principal = Depends(require_ops_reader)):
    return filter_ops_rows(crud.list_threat_events(team=team), principal)


@router.post("", response_model=ThreatEvent, status_code=201)
def create_event(body: ThreatEventCreate, _: Principal = Depends(require_jwt_or_service)):
    return crud.create_threat_event(body)
