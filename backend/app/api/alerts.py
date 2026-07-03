from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.database import get_db
from app.middleware.auth_middleware import get_current_user
from app.schemas.alert import AlertItemResponse
from app.services.alert_service import get_all_alerts

router = APIRouter(prefix="/alerts", tags=["alerts"])


@router.get("/summary", response_model=list[AlertItemResponse])
def alert_summary(
    db: Session = Depends(get_db),
    _user: dict = Depends(get_current_user),
):
    return get_all_alerts(db)
