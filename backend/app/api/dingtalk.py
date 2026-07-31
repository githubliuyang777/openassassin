from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.middleware.auth_middleware import get_current_user
from app.schemas.dingtalk import DingTalkConfigUpdate, DingTalkConfigResponse, DingTalkStatusResponse
from app.services import dingtalk_service

router = APIRouter(prefix="/dingtalk", tags=["dingtalk"])


@router.get("/config", response_model=DingTalkConfigResponse)
def get_config(
    db: Session = Depends(get_db),
    _user: dict = Depends(get_current_user),
):
    """Get DingTalk configuration (secret is masked)."""
    config = dingtalk_service.get_config(db)
    return DingTalkConfigResponse(
        id=config.id,
        webhook_url=config.webhook_url,
        is_enabled=config.is_enabled,
        secret_configured=bool(config.secret),
        created_at=config.created_at,
        updated_at=config.updated_at,
    )


@router.put("/config", response_model=DingTalkConfigResponse)
def update_config(
    data: DingTalkConfigUpdate,
    db: Session = Depends(get_db),
    _user: dict = Depends(get_current_user),
):
    """Update DingTalk configuration."""
    config = dingtalk_service.update_config(
        db,
        webhook_url=data.webhook_url,
        secret=data.secret,
        is_enabled=data.is_enabled,
    )
    return DingTalkConfigResponse(
        id=config.id,
        webhook_url=config.webhook_url,
        is_enabled=config.is_enabled,
        secret_configured=bool(config.secret),
        created_at=config.created_at,
        updated_at=config.updated_at,
    )


@router.get("/status", response_model=DingTalkStatusResponse)
def get_status(
    db: Session = Depends(get_db),
    _user: dict = Depends(get_current_user),
):
    """View DingTalk connection status."""
    status_data = dingtalk_service.get_status(db)
    return DingTalkStatusResponse(**status_data)


@router.post("/test")
def test_connection(
    db: Session = Depends(get_db),
    _user: dict = Depends(get_current_user),
):
    """Send a test message via the configured DingTalk bot."""
    try:
        result = dingtalk_service.send_test_message(db)
        return {"message": "测试消息已发送至钉钉群", "data": result}
    except dingtalk_service.DingTalkNotConfiguredError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=f"钉钉消息发送失败: {str(e)}")
