import asyncio
import logging
import socket
import time

import httpx
from typing import List, Optional

from sqlalchemy.orm import Session

from app.database import SessionLocal, china_now
from app.models.site_monitor import SiteMonitor, SiteCheckResult
from app.schemas.site_monitor import SiteMonitorCreate, SiteMonitorUpdate

logger = logging.getLogger(__name__)


# ── CRUD ──────────────────────────────────────────────────────────────────────

def list_monitors(db: Session, group: str = "") -> List[SiteMonitor]:
    query = db.query(SiteMonitor)
    if group:
        query = query.filter(SiteMonitor.group_name == group)
    return query.order_by(SiteMonitor.updated_at.desc()).all()


def list_groups(db: Session) -> List[str]:
    rows = db.query(SiteMonitor.group_name).distinct().order_by(SiteMonitor.group_name).all()
    return [r[0] for r in rows if r[0]]


def get_monitor(db: Session, monitor_id: int) -> Optional[SiteMonitor]:
    return db.query(SiteMonitor).filter(SiteMonitor.id == monitor_id).first()


def create_monitor(db: Session, data: SiteMonitorCreate) -> SiteMonitor:
    m = SiteMonitor(**data.model_dump())
    db.add(m)
    db.commit()
    db.refresh(m)
    return m


def update_monitor(db: Session, monitor: SiteMonitor, data: SiteMonitorUpdate) -> SiteMonitor:
    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(monitor, field, value)
    db.commit()
    db.refresh(monitor)
    return monitor


def delete_monitor(db: Session, monitor: SiteMonitor) -> None:
    db.delete(monitor)
    db.commit()


def get_check_history(db: Session, monitor_id: int, page: int = 1, page_size: int = 20) -> dict:
    rows = (
        db.query(SiteCheckResult)
        .filter(SiteCheckResult.monitor_id == monitor_id)
        .order_by(SiteCheckResult.checked_at.asc())
        .all()
    )
    # Keep only state transitions: first record + each state change
    transitions: list[SiteCheckResult] = []
    prev_up: bool | None = None
    for r in rows:
        if prev_up is None or r.is_up != prev_up:
            transitions.append(r)
        prev_up = r.is_up

    total = len(transitions)
    # Reverse to show newest first
    transitions.reverse()
    start = (page - 1) * page_size
    items = [{
        "id": r.id, "monitor_id": r.monitor_id, "is_up": r.is_up,
        "status_code": r.status_code, "response_ms": r.response_ms,
        "error": r.error, "checked_at": r.checked_at.isoformat() if r.checked_at else None,
    } for r in transitions[start:start + page_size]]
    return {"total": total, "page": page, "page_size": page_size, "items": items}


# ── Probe logic ───────────────────────────────────────────────────────────────

def _probe_http(monitor: SiteMonitor) -> tuple[bool, int | None, float, str | None]:
    codes = [int(x.strip()) for x in monitor.expected_status_codes.split(",") if x.strip()]
    if not codes:
        codes = [200]
    try:
        start = time.perf_counter()
        resp = httpx.request(
            method=monitor.http_method.upper(),
            url=monitor.target,
            timeout=monitor.timeout,
            follow_redirects=True,
        )
        elapsed = (time.perf_counter() - start) * 1000
        ok = resp.status_code in codes
        err = None if ok else f"状态码 {resp.status_code} 不在期望范围"
        return ok, resp.status_code, round(elapsed, 2), err
    except httpx.TimeoutException:
        return False, None, 0, f"HTTP 超时（{monitor.timeout}秒）"
    except httpx.ConnectError as e:
        return False, None, 0, f"连接失败: {e}"
    except Exception as e:
        return False, None, 0, str(e)[:256]


def _probe_tcp(monitor: SiteMonitor) -> tuple[bool, int | None, float, str | None]:
    host, _, port_str = monitor.target.partition(":")
    port = int(port_str) if port_str else 80
    try:
        start = time.perf_counter()
        with socket.create_connection((host, port), timeout=monitor.timeout):
            elapsed = (time.perf_counter() - start) * 1000
        return True, None, round(elapsed, 2), None
    except socket.timeout:
        return False, None, 0, f"TCP 超时（{monitor.timeout}秒）"
    except socket.gaierror:
        return False, None, 0, "无法解析主机名"
    except ConnectionRefusedError:
        return False, None, 0, "连接被拒绝"
    except OSError as e:
        msg = e.strerror if hasattr(e, "strerror") else str(e)
        return False, None, 0, f"网络错误: {msg}"


def run_single_check(monitor: SiteMonitor) -> SiteCheckResult:
    was_up = monitor.is_up
    db = SessionLocal()

    ok = False
    status_code = None
    response_ms: float = 0
    error: str | None = None

    for attempt in range(monitor.retries + 1):
        if attempt > 0:
            time.sleep(1)
        if monitor.monitor_type == "http":
            ok, status_code, response_ms, error = _probe_http(monitor)
        else:
            ok, status_code, response_ms, error = _probe_tcp(monitor)
        if ok:
            break

    try:
        result = SiteCheckResult(
            monitor_id=monitor.id,
            is_up=ok,
            status_code=status_code,
            response_ms=response_ms,
            error=error,
        )
        db.add(result)

        m = db.query(SiteMonitor).filter(SiteMonitor.id == monitor.id).first()
        if m:
            m.is_up = ok
            m.last_checked_at = china_now()
            m.last_response_ms = response_ms
        db.commit()
        db.refresh(result)

        if was_up and not ok:
            logger.info("Site %s (%s) went DOWN", monitor.name, monitor.target)
            _send_down_alert(db, m or monitor, error)
        elif not was_up and ok:
            logger.info("Site %s (%s) recovered", monitor.name, monitor.target)
            _send_up_alert(db, m or monitor)

        return result
    finally:
        db.close()


def _get_alert_emails(db: Session, monitor: SiteMonitor) -> list[str]:
    from app.config import settings
    if monitor.notification_group_id:
        from app.services.notification_service import get_recipient_emails
        emails = get_recipient_emails(db, monitor.notification_group_id)
        if emails:
            return emails
    return [settings.alert_email] if settings.alert_email else []


def _send_down_alert(db: Session, monitor: SiteMonitor, error: str | None) -> None:
    from datetime import timedelta
    from app.config import settings
    if not settings.smtp_host:
        return
    if not monitor.alert_enabled:
        return
    now = china_now()
    if monitor.last_alerted_at and monitor.last_alerted_at > now - timedelta(hours=1):
        return  # already alerted within 1 hour
    emails = _get_alert_emails(db, monitor)
    if not emails:
        return
    try:
        from app.services.email_service import send_email
        subject = f"[Ops Platform] 站点不可达: {monitor.name}"
        body = f"""站点监控告警

名称: {monitor.name}
目标: {monitor.target}
类型: {monitor.monitor_type.upper()}
错误: {error or '连接失败'}
时间: {now.strftime('%Y-%m-%d %H:%M')} (北京时间)

Ops Platform 站点监控
"""
        for addr in emails:
            send_email(addr, subject, body)
        monitor.last_alerted_at = now
        db.commit()
    except Exception:
        pass


def _send_up_alert(db: Session, monitor: SiteMonitor) -> None:
    from app.config import settings
    if not settings.smtp_host:
        return
    if not monitor.alert_enabled:
        return
    emails = _get_alert_emails(db, monitor)
    if not emails:
        return
    try:
        from app.services.email_service import send_email
        now = china_now()
        subject = f"[Ops Platform] 站点已恢复: {monitor.name}"
        body = f"""站点监控恢复通知

名称: {monitor.name}
目标: {monitor.target}
类型: {monitor.monitor_type.upper()}
状态: 已恢复正常
时间: {now.strftime('%Y-%m-%d %H:%M')} (北京时间)

Ops Platform 站点监控
"""
        for addr in emails:
            send_email(addr, subject, body)
    except Exception:
        pass


# ── Background check ───────────────────────────────────────────────────────────

def check_all_monitors():
    """Single-pass: iterate all monitors and check those due for probing."""
    db = SessionLocal()
    try:
        monitors = db.query(SiteMonitor).all()
    finally:
        db.close()

    now = china_now()
    for m in monitors:
        if m.last_checked_at is None or (now - m.last_checked_at).total_seconds() >= m.check_interval:
            run_single_check(m)
