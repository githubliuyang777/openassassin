from datetime import timedelta

from sqlalchemy.orm import Session

from app.config import settings
from app.models.credential import Credential
from app.models.domain import Domain
from app.models.domain_whois import DomainWhois
from app.models.subscription import SubscriptionAlert, Subscription
from app.models.site_monitor import SiteMonitor
from app.database import china_now

SEVERITY_DANGER = "danger"
SEVERITY_WARNING = "warning"
SEVERITY_INFO = "info"

SOURCE_CREDENTIAL = "credential"
SOURCE_DOMAIN_CERT = "domain_cert"
SOURCE_DOMAIN_WHOIS = "domain_whois"
SOURCE_SUBSCRIPTION = "subscription"
SOURCE_SITE_MONITOR = "site_monitor"

SEVERITY_ORDER = {SEVERITY_DANGER: 0, SEVERITY_WARNING: 1, SEVERITY_INFO: 2}


def _collect_expiry_alerts(
    rows: list,
    id_prefix: str,
    source: str,
    expiry_attr: str,
    name_attr: str,
    message_template: callable,
    link: str,
    now,
    alerts: list,
) -> None:
    for row in rows:
        expiry = getattr(row, expiry_attr)
        name = getattr(row, name_attr)
        days_left = (expiry - now).days
        alerts.append({
            "id": f"{id_prefix}-{row.id}",
            "source": source,
            "message": message_template(name, days_left),
            "severity": SEVERITY_DANGER if days_left <= 0 else SEVERITY_WARNING,
            "link": link,
            "days_remaining": days_left,
        })


def _cred_message(name: str, days_left: int) -> str:
    return f"密钥 {name} 将于 {days_left} 天后过期" if days_left > 0 else f"密钥 {name} 已过期 {-days_left} 天"


def _cert_message(name: str, days_left: int) -> str:
    return f"域名 {name} SSL证书将于 {days_left} 天后过期" if days_left > 0 else f"域名 {name} SSL证书已过期 {-days_left} 天"


def _whois_message(name: str, days_left: int) -> str:
    return f"域名 {name} 将于 {days_left} 天后过期" if days_left > 0 else f"域名 {name} 已过期 {-days_left} 天"


def get_all_alerts(db: Session) -> list[dict]:
    now = china_now()
    threshold = now + timedelta(days=settings.alert_before_days)
    alerts: list[dict] = []

    # 1. Credential expiry
    creds = (
        db.query(Credential)
        .filter(
            Credential.expires_at.isnot(None),
            Credential.expires_at <= threshold,
            Credential.alert_enabled.is_(True),
        )
        .all()
    )
    _collect_expiry_alerts(creds, "cred", SOURCE_CREDENTIAL,
                           "expires_at", "name", _cred_message,
                           "/credentials", now, alerts)

    # 2. Domain SSL certificate expiry
    domains = (
        db.query(Domain)
        .filter(
            Domain.ssl_not_after.isnot(None),
            Domain.ssl_not_after <= threshold,
            Domain.alert_enabled.is_(True),
        )
        .all()
    )
    _collect_expiry_alerts(domains, "cert", SOURCE_DOMAIN_CERT,
                           "ssl_not_after", "domain", _cert_message,
                           "/monitor/domains", now, alerts)

    # 3. Domain WHOIS expiry
    whois_entries = (
        db.query(DomainWhois)
        .filter(
            DomainWhois.whois_expiry_date.isnot(None),
            DomainWhois.whois_expiry_date <= threshold,
            DomainWhois.alert_enabled.is_(True),
        )
        .all()
    )
    _collect_expiry_alerts(whois_entries, "whois", SOURCE_DOMAIN_WHOIS,
                           "whois_expiry_date", "domain", _whois_message,
                           "/monitor/domains-whois", now, alerts)

    # 4. Unread subscription alerts — grouped by subscription
    sub_alerts = (
        db.query(SubscriptionAlert, Subscription.name, Subscription.id)
        .join(Subscription, SubscriptionAlert.subscription_id == Subscription.id)
        .filter(SubscriptionAlert.is_read.is_(False))
        .all()
    )
    sub_counts: dict[tuple[int, str], int] = {}
    for _sa, sub_name, sub_id in sub_alerts:
        key = (sub_id, sub_name)
        sub_counts[key] = sub_counts.get(key, 0) + 1

    for (sub_id, sub_name), count in sub_counts.items():
        alerts.append({
            "id": f"sub-{sub_id}",
            "source": SOURCE_SUBSCRIPTION,
            "message": f"{sub_name} 有 {count} 条新动态",
            "severity": SEVERITY_INFO,
            "link": "/subscriptions",
            "days_remaining": 999,
        })

    # 5. Site monitors that are down
    down_monitors = (
        db.query(SiteMonitor)
        .filter(SiteMonitor.is_up.is_(False), SiteMonitor.alert_enabled.is_(True))
        .all()
    )
    for dm in down_monitors:
        alerts.append({
            "id": f"site-{dm.id}",
            "source": SOURCE_SITE_MONITOR,
            "message": f"站点 {dm.name} 不可达: {dm.target}",
            "severity": SEVERITY_DANGER,
            "link": "/monitor/site-monitor",
            "days_remaining": 0,
        })

    # Sort: danger first, then warning by days_remaining ASC, then info
    def _sort_key(a: dict) -> tuple[int, int]:
        return (SEVERITY_ORDER[a["severity"]], a["days_remaining"])

    alerts.sort(key=_sort_key)
    return alerts


def check_and_alert(db: Session) -> int:
    """Check for credentials nearing expiry and send alerts. Returns count of alerts sent."""
    from app.services.notification_service import send_group_notification

    now = china_now()
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
            days_left = (cred.expires_at - now).days
            subject = f"[openAssassin] 密钥即将过期: {cred.name}"
            body = f"""密钥 "{cred.name}" 即将过期。

密钥类型: {cred.type}
环境变量: {cred.key}
剩余天数: {days_left} 天
过期时间: {cred.expires_at.strftime('%Y-%m-%d %H:%M')} (北京时间)

请及时更新密钥，以免影响服务运行。
"""
            send_group_notification(
                db, getattr(cred, 'notification_group_id', None),
                settings.alert_email, subject, body,
            )
            cred.last_alerted_at = now
            db.commit()
            sent += 1
        except Exception:
            pass
    return sent
