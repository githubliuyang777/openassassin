from fastapi import APIRouter, Depends, HTTPException, status

from app.config import settings
from app.middleware.auth_middleware import get_current_user
from app.schemas.notifications import TestEmailRequest
from app.services import email_service

router = APIRouter(prefix="/notifications", tags=["notifications"])


@router.post("/test-email")
def test_email(req: TestEmailRequest, user: dict = Depends(get_current_user)):
    try:
        email_service.send_email(req.email, "openAssassin 邮件测试", "openAssassin SMTP 配置测试邮件 — 发送成功！")
    except email_service.EmailNotConfiguredError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=f"邮件发送失败: {str(e)}")
    return {"message": f"测试邮件已发送至 {req.email}"}


@router.get("/smtp-status")
def smtp_status(user: dict = Depends(get_current_user)):
    configured = bool(settings.smtp_host)
    return {
        "configured": configured,
        "host": settings.smtp_host if configured else None,
        "port": settings.smtp_port if configured else None,
        "from": settings.smtp_from if configured else None,
        "use_tls": settings.smtp_use_tls,
    }
