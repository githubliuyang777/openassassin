from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.database import get_db
from app.middleware.auth_middleware import get_current_user
from app.schemas.audit_log import AuditLogListResponse
from app.services import audit_service

router = APIRouter(prefix="/audit-logs", tags=["audit-logs"])


@router.get("", response_model=AuditLogListResponse)
def list_logs(
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    username: str | None = None,
    action: str | None = None,
    resource: str | None = None,
    date_from: str | None = None,
    date_to: str | None = None,
    db: Session = Depends(get_db),
    _user: dict = Depends(get_current_user),
):
    return audit_service.list_logs(
        db,
        page=page,
        page_size=page_size,
        username=username,
        action=action,
        resource=resource,
        date_from=date_from,
        date_to=date_to,
    )
