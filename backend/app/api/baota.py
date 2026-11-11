from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.middleware.auth_middleware import get_current_admin_user
from app.models.baota_panel import BaotaPanel
from app.schemas.baota import (
    BaotaPanelCreate,
    BaotaPanelResponse,
    BaotaPanelUpdate,
    BaotaTestResponse,
)
from app.services import baota_service

router = APIRouter(prefix="/baota", tags=["baota"])


def _panel_response(panel: BaotaPanel) -> dict:
    return {
        "id": panel.id,
        "name": panel.name,
        "panel_url": panel.panel_url,
        "verify_tls": bool(panel.verify_tls),
        "enabled": bool(panel.enabled),
        "api_key_configured": bool(panel.encrypted_api_key),
        "created_at": panel.created_at,
        "updated_at": panel.updated_at,
    }


@router.get("/panels", response_model=list[BaotaPanelResponse])
def list_panels(
    db: Session = Depends(get_db),
    _user: dict = Depends(get_current_admin_user),
):
    panels = db.query(BaotaPanel).order_by(BaotaPanel.id.asc()).all()
    return [_panel_response(panel) for panel in panels]


@router.post("/panels", response_model=BaotaPanelResponse, status_code=status.HTTP_201_CREATED)
def create_panel(
    data: BaotaPanelCreate,
    db: Session = Depends(get_db),
    _user: dict = Depends(get_current_admin_user),
):
    return _panel_response(baota_service.create_panel(db, data))


@router.put("/panels/{panel_id}", response_model=BaotaPanelResponse)
def update_panel(
    panel_id: int,
    data: BaotaPanelUpdate,
    db: Session = Depends(get_db),
    _user: dict = Depends(get_current_admin_user),
):
    panel = db.get(BaotaPanel, panel_id)
    if not panel:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="宝塔面板不存在")
    return _panel_response(baota_service.update_panel(db, panel, data))


@router.delete("/panels/{panel_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_panel(
    panel_id: int,
    db: Session = Depends(get_db),
    _user: dict = Depends(get_current_admin_user),
):
    panel = db.get(BaotaPanel, panel_id)
    if not panel:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="宝塔面板不存在")
    if baota_service.panel_in_use(db, panel_id):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="该面板仍被域名引用，请先解除域名绑定",
        )
    db.delete(panel)
    db.commit()


@router.post("/panels/{panel_id}/test", response_model=BaotaTestResponse)
def test_panel(
    panel_id: int,
    db: Session = Depends(get_db),
    _user: dict = Depends(get_current_admin_user),
):
    try:
        sites = baota_service.test_panel(db, panel_id)
    except baota_service.BaotaError as exc:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(exc))
    return {"ok": True, "message": f"连接成功，共 {len(sites)} 个站点", "sites": sites}
