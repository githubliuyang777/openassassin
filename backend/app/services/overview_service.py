from datetime import timedelta

from sqlalchemy.orm import Session

from app.config import settings
from app.models.site_monitor import SiteMonitor
from app.models.domain import Domain
from app.models.domain_whois import DomainWhois
from app.database import china_now


def get_monitor_summary(db: Session) -> dict:
    """获取站点监控、域名证书、域名监控的汇总统计"""
    now = china_now()
    threshold = now + timedelta(days=settings.alert_before_days)

    # 1. 站点监控
    site_monitors = db.query(SiteMonitor).all()
    sm_total = len(site_monitors)
    sm_up = sum(1 for m in site_monitors if m.is_up)
    sm_down = sm_total - sm_up
    sm_items = [
        {
            "id": m.id,
            "name": m.name,
            "target": m.target,
            "is_up": m.is_up,
            "response_ms": m.last_response_ms,
        }
        for m in site_monitors[:10]  # 最多返回10条
    ]

    # 2. 域名证书
    domains = db.query(Domain).all()
    dc_total = len(domains)
    dc_expired = 0
    dc_expiring = 0
    dc_valid = 0
    dc_items = []
    for d in domains:
        if d.ssl_expired:
            dc_expired += 1
            days_remaining = 0
        elif d.ssl_not_after and d.ssl_not_after <= threshold:
            dc_expiring += 1
            days_remaining = (d.ssl_not_after - now).days
        else:
            dc_valid += 1
            days_remaining = (d.ssl_not_after - now).days if d.ssl_not_after else None

        dc_items.append({
            "id": d.id,
            "domain": d.domain,
            "ssl_expired": d.ssl_expired,
            "days_remaining": days_remaining,
        })

    # 3. 域名 WHOIS
    whois_domains = db.query(DomainWhois).all()
    dw_total = len(whois_domains)
    dw_expired = 0
    dw_expiring = 0
    dw_valid = 0
    dw_items = []
    for w in whois_domains:
        if w.whois_expiry_date and w.whois_expiry_date <= now:
            dw_expired += 1
            days_remaining = 0
        elif w.whois_expiry_date and w.whois_expiry_date <= threshold:
            dw_expiring += 1
            days_remaining = (w.whois_expiry_date - now).days
        else:
            dw_valid += 1
            days_remaining = (w.whois_expiry_date - now).days if w.whois_expiry_date else None

        dw_items.append({
            "id": w.id,
            "domain": w.domain,
            "days_remaining": days_remaining,
        })

    return {
        "site_monitors": {
            "total": sm_total,
            "up": sm_up,
            "down": sm_down,
            "items": sm_items,
        },
        "domain_certs": {
            "total": dc_total,
            "valid": dc_valid,
            "expiring": dc_expiring,
            "expired": dc_expired,
            "items": dc_items,
        },
        "domain_whois": {
            "total": dw_total,
            "valid": dw_valid,
            "expiring": dw_expiring,
            "expired": dw_expired,
            "items": dw_items,
        },
    }
