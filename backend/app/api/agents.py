from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.database import get_db
from app.middleware.auth_middleware import get_current_user
from app.middleware.agent_auth import get_current_agent
from app.schemas.agent import AgentReportRequest, AgentReportResponse, AgentEventsRequest, HostStatusSummary
from app.services import agent_service

router = APIRouter(prefix="/agents", tags=["agents"])


@router.post("/report", response_model=AgentReportResponse)
def report(
    data: AgentReportRequest,
    host_id: int = Depends(get_current_agent),
    db: Session = Depends(get_db),
):
    agent_service.process_report(db, host_id, data)
    return AgentReportResponse(ok=True)


@router.post("/events", response_model=AgentReportResponse)
def report_events(
    data: AgentEventsRequest,
    host_id: int = Depends(get_current_agent),
    db: Session = Depends(get_db),
):
    agent_service.process_events(db, host_id, data.events)
    return AgentReportResponse(ok=True)


@router.get("/status", response_model=list[HostStatusSummary])
def agent_status(
    db: Session = Depends(get_db),
    _user: dict = Depends(get_current_user),
):
    return agent_service.get_all_host_status(db)
