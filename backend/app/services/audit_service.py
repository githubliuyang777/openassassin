from datetime import datetime, timedelta, timezone
import asyncio
import json
import logging

from sqlalchemy.orm import Session
from sqlalchemy import desc

from app.database import SessionLocal
from app.models.audit_log import AuditLog
from app.config import settings

logger = logging.getLogger(__name__)

_PRIVATE_PREFIXES = ("127.", "192.168.", "10.", "172.16.", "172.17.", "172.18.",
                     "172.19.", "172.20.", "172.21.", "172.22.", "172.23.",
                     "172.24.", "172.25.", "172.26.", "172.27.", "172.28.",
                     "172.29.", "172.30.", "172.31.", "0.", "localhost", "::1")


def create_log(
    db: Session,
    user_id: int,
    username: str,
    action: str,
    resource: str = "",
    resource_type: str = "",
    detail: str = "",
    ip_address: str = "",
    ip_location: str = "",
    user_agent: str = "",
    status_code: int = 0,
) -> AuditLog:
    entry = AuditLog(
        user_id=user_id,
        username=username,
        action=action,
        resource=resource,
        resource_type=resource_type,
        detail=detail,
        ip_address=ip_address,
        ip_location=ip_location,
        user_agent=user_agent,
        status_code=status_code,
    )
    db.add(entry)
    db.commit()
    return entry


async def create_log_async(**kwargs):
    db = SessionLocal()
    try:
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(None, lambda: _create_sync(db, **kwargs))
    except Exception:
        pass
    finally:
        db.close()


def _create_sync(db: Session, **kwargs):
    ip = kwargs.get("ip_address", "")
    if ip and not kwargs.get("ip_location"):
        kwargs["ip_location"] = _resolve_ip_location(ip)
    entry = AuditLog(**kwargs)
    db.add(entry)
    db.commit()


def _resolve_ip_location(ip: str) -> str:
    if not ip or ip == "unknown":
        return ""
    if ip in ("127.0.0.1", "localhost", "::1"):
        return "本机"
    for prefix in _PRIVATE_PREFIXES:
        if ip.startswith(prefix):
            return "内网"
    try:
        from urllib.request import Request, urlopen
        url = f"http://ip-api.com/json/{ip}?lang=zh-CN&fields=country,regionName,city"
        req = Request(url, headers={"User-Agent": "ops-platform/1.0"})
        with urlopen(req, timeout=2) as resp:
            body = json.loads(resp.read().decode())
            if isinstance(body, dict) and body.get("country"):
                parts = [body.get("country", ""), body.get("regionName", ""), body.get("city", "")]
                location = " ".join(p for p in parts if p)
                return location or "未知"
    except Exception:
        logger.debug("IP lookup failed for %s", ip)
    return "未知"


def list_logs(
    db: Session,
    page: int = 1,
    page_size: int = 50,
    username: str | None = None,
    action: str | None = None,
    resource: str | None = None,
    date_from: str | None = None,
    date_to: str | None = None,
) -> dict:
    query = db.query(AuditLog)
    if username:
        query = query.filter(AuditLog.username == username)
    if action:
        query = query.filter(AuditLog.action == action)
    if resource:
        query = query.filter(AuditLog.resource.contains(resource))
    if date_from:
        query = query.filter(AuditLog.created_at >= _parse_date(date_from))
    if date_to:
        query = query.filter(AuditLog.created_at <= _parse_date(date_to, end_of_day=True))

    total = query.count()
    items = (
        query.order_by(desc(AuditLog.created_at))
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )
    return {"items": items, "total": total, "page": page, "page_size": page_size}


def cleanup_old_logs(db: Session) -> int:
    cutoff = datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(days=settings.audit_log_retention_days)
    count = db.query(AuditLog).filter(AuditLog.created_at < cutoff).delete()
    db.commit()
    return count


def _parse_date(val: str, end_of_day: bool = False) -> datetime:
    dt = datetime.strptime(val[:10], "%Y-%m-%d")
    if end_of_day:
        dt = dt.replace(hour=23, minute=59, second=59)
    return dt
