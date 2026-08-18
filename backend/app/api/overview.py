from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.database import get_db
from app.middleware.auth_middleware import get_current_user
from app.schemas.overview import MonitorSummaryResponse
from app.services.overview_service import get_monitor_summary

router = APIRouter(prefix="/overview", tags=["overview"])


@router.get("/monitor-summary", response_model=MonitorSummaryResponse)
def monitor_summary(
    db: Session = Depends(get_db),
    _user: dict = Depends(get_current_user),
):
    """获取站点监控、域名证书、域名监控的汇总统计"""
    return get_monitor_summary(db)
