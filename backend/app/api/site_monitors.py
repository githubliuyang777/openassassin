from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from app.database import get_db
from app.middleware.auth_middleware import get_current_user
from app.schemas.site_monitor import SiteMonitorCreate, SiteMonitorUpdate, SiteMonitorResponse, SiteCheckResultResponse
from app.services import site_monitor_service
from app.services.site_monitor_stats import get_all_monitors_sla, export_sla_csv, get_heatmap_data

router = APIRouter(prefix="/site-monitors", tags=["site-monitors"])


# Static routes must be defined BEFORE parameterized routes to avoid path conflicts
@router.get("/sla-summary")
def sla_summary(
    period: str = Query("monthly", pattern="^(monthly|annual)$"),
    db: Session = Depends(get_db),
    _user: dict = Depends(get_current_user),
):
    return get_all_monitors_sla(db, period)


@router.get("/export-sla")
def export_sla(
    period: str = Query("monthly", pattern="^(monthly|annual)$"),
    db: Session = Depends(get_db),
    _user: dict = Depends(get_current_user),
):
    csv_content = export_sla_csv(db, period)
    filename = f"sla-{period}-report.csv"
    return StreamingResponse(
        iter([csv_content]),
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename={filename}"},
    )


@router.get("", response_model=list[SiteMonitorResponse])
def list_monitors(
    db: Session = Depends(get_db),
    _user: dict = Depends(get_current_user),
):
    return site_monitor_service.list_monitors(db)


@router.post("", response_model=SiteMonitorResponse, status_code=status.HTTP_201_CREATED)
def create_monitor(
    data: SiteMonitorCreate,
    db: Session = Depends(get_db),
    _user: dict = Depends(get_current_user),
):
    return site_monitor_service.create_monitor(db, data)


@router.get("/{monitor_id}", response_model=SiteMonitorResponse)
def get_monitor(
    monitor_id: int,
    db: Session = Depends(get_db),
    _user: dict = Depends(get_current_user),
):
    m = site_monitor_service.get_monitor(db, monitor_id)
    if not m:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="监控不存在")
    return m


@router.put("/{monitor_id}", response_model=SiteMonitorResponse)
def update_monitor(
    monitor_id: int,
    data: SiteMonitorUpdate,
    db: Session = Depends(get_db),
    _user: dict = Depends(get_current_user),
):
    m = site_monitor_service.get_monitor(db, monitor_id)
    if not m:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="监控不存在")
    return site_monitor_service.update_monitor(db, m, data)


@router.delete("/{monitor_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_monitor(
    monitor_id: int,
    db: Session = Depends(get_db),
    _user: dict = Depends(get_current_user),
):
    m = site_monitor_service.get_monitor(db, monitor_id)
    if not m:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="监控不存在")
    site_monitor_service.delete_monitor(db, m)


@router.get("/{monitor_id}/history", response_model=dict)
def get_history(
    monitor_id: int,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
    _user: dict = Depends(get_current_user),
):
    m = site_monitor_service.get_monitor(db, monitor_id)
    if not m:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="监控不存在")
    return site_monitor_service.get_check_history(db, monitor_id, page, page_size)


@router.post("/{monitor_id}/check-now", response_model=SiteCheckResultResponse)
def check_now(
    monitor_id: int,
    db: Session = Depends(get_db),
    _user: dict = Depends(get_current_user),
):
    m = site_monitor_service.get_monitor(db, monitor_id)
    if not m:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="监控不存在")
    return site_monitor_service.run_single_check(m)


@router.get("/{monitor_id}/heatmap")
def heatmap(
    monitor_id: int,
    days: int = Query(7, ge=1, le=90),
    db: Session = Depends(get_db),
    _user: dict = Depends(get_current_user),
):
    m = site_monitor_service.get_monitor(db, monitor_id)
    if not m:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="监控不存在")
    return get_heatmap_data(db, monitor_id, days)
