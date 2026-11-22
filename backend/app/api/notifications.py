from fastapi import APIRouter, Depends, HTTPException, status

from app.middleware.auth_middleware import get_current_user
from app.schemas.notifications import (
    SmtpStatusResponse,
    TestEmailRequest,
    TestEmailResponse,
)
from app.services import email_service

router = APIRouter(prefix="/notifications", tags=["notifications"])


@router.post("/test-email", response_model=TestEmailResponse)
def test_email(req: TestEmailRequest, user: dict = Depends(get_current_user)):
    result = email_service.send_alert_email(
        req.email,
        "openAssassin 告警邮件测试",
        "openAssassin SMTP 告警链路测试邮件 — 发送成功！",
        provider=req.provider,
    )
    if result.delivered:
        message = f"测试邮件已发送至 {req.email}"
        if result.failover:
            message += "（主 SMTP 不可用，已切换备用）"
        return TestEmailResponse(
            message=message,
            provider=result.provider,  # type: ignore[arg-type]
            failover=result.failover,
        )

    details = "; ".join(error.message for error in result.errors)[:500] or "未知错误"
    if any(error.kind == "config" for error in result.errors):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=details)
    raise HTTPException(
        status_code=status.HTTP_502_BAD_GATEWAY,
        detail=f"邮件发送失败: {details}",
    )


@router.get("/smtp-status", response_model=SmtpStatusResponse)
def smtp_status(user: dict = Depends(get_current_user)):
    return email_service.get_smtp_status()
