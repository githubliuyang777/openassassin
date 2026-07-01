from datetime import datetime, timedelta, timezone

from sqlalchemy.orm import Session

from app.config import settings
from app.models.credential import Credential

CHINA_TZ = timezone(timedelta(hours=8))


def _now() -> datetime:
    return datetime.now(CHINA_TZ).replace(tzinfo=None)


def check_and_alert(db: Session) -> int:
    """Check for credentials nearing expiry and send alerts. Returns count of alerts sent."""
    if not settings.alert_email or not settings.smtp_host:
        return 0

    now = _now()
    threshold = now + timedelta(days=settings.alert_before_days)
    expiring = (
        db.query(Credential)
        .filter(
            Credential.expires_at.isnot(None),
            Credential.expires_at <= threshold,
            Credential.alert_enabled.is_(True),
        )
        .all()
    )

    sent = 0
    for cred in expiring:
        if cred.last_alerted_at and cred.last_alerted_at > now - timedelta(days=1):
            continue  # already alerted within 24h
        try:
            from app.services.email_service import send_email
            days_left = (cred.expires_at - now).days
            subject = f"[Ops Platform] 密钥即将过期: {cred.name}"
            body = f"""密钥 "{cred.name}" 即将过期。

密钥类型: {cred.type}
环境变量: {cred.key}
剩余天数: {days_left} 天
过期时间: {cred.expires_at.strftime('%Y-%m-%d %H:%M')} (北京时间)

请及时更新密钥，以免影响服务运行。
"""
            send_email(settings.alert_email, subject, body)
            cred.last_alerted_at = now
            db.commit()
            sent += 1
        except Exception:
            pass
    return sent
