import json
import logging
import secrets
from datetime import timedelta

from sqlalchemy.orm import Session

from app.config import settings
from app.database import china_now
from app.models.host import Host
from app.models.host_metric import HostMetric
from app.models.host_event import HostEvent
from app.schemas.agent import AgentReportRequest, AgentEventItem

logger = logging.getLogger(__name__)


def generate_agent_token() -> str:
    return "oa_" + secrets.token_hex(16)


def generate_agent_token_unique(db: Session) -> str:
    for _ in range(10):
        token = generate_agent_token()
        if not db.query(Host).filter(Host.agent_token == token).first():
            return token
    raise RuntimeError("Failed to generate unique agent token after 10 attempts")


def process_report(db: Session, host_id: int, data: AgentReportRequest) -> None:
    now = china_now()

    host = db.query(Host).filter(Host.id == host_id).first()
    if host:
        host.cpu_usage = data.cpu_percent
        if data.cpu_count > 0:
            host.cpu_count = data.cpu_count
        host.mem_usage = data.mem_percent
        host.disk_usage = data.disk_percent
        if data.agent_version:
            host.agent_version = data.agent_version
        host.last_seen_at = now
        host.is_online = True
        if not host.name and data.hostname:
            host.name = data.hostname

    metric = HostMetric(
        host_id=host_id,
        cpu_percent=data.cpu_percent,
        cpu_count=data.cpu_count,
        mem_total_mb=data.mem_total_mb,
        mem_used_mb=data.mem_used_mb,
        mem_percent=data.mem_percent,
        disk_total_gb=data.disk_total_gb,
        disk_used_gb=data.disk_used_gb,
        disk_percent=data.disk_percent,
        load_1m=data.load_1m,
        load_5m=data.load_5m,
        load_15m=data.load_15m,
        net_rx_bytes=data.net_rx_bytes,
        net_tx_bytes=data.net_tx_bytes,
        process_count=data.process_count,
        uptime_seconds=data.uptime_seconds,
        collected_at=now,
    )
    db.add(metric)
    db.commit()


def get_all_host_status(db: Session) -> list[dict]:
    hosts = db.query(Host).order_by(Host.updated_at.desc()).all()
    return [{
        "id": h.id, "name": h.name, "hostname": h.hostname,
        "is_online": h.is_online,
        "last_seen_at": h.last_seen_at.isoformat() if h.last_seen_at else None,
        "cpu_usage": h.cpu_usage, "cpu_count": h.cpu_count, "mem_usage": h.mem_usage,
        "disk_usage": h.disk_usage, "agent_version": h.agent_version,
    } for h in hosts]


def get_host_metrics(db: Session, host_id: int, hours: int = 24) -> list[dict]:
    start = china_now() - timedelta(hours=hours)
    rows = (
        db.query(HostMetric)
        .filter(HostMetric.host_id == host_id, HostMetric.collected_at >= start)
        .order_by(HostMetric.collected_at.asc())
        .all()
    )
    if not rows:
        return []

    bucket_minutes = {1: 1, 6: 2, 24: 5, 168: 30}
    bucket_m = bucket_minutes.get(hours, 5)

    bucketed = []
    bucket_start = rows[0].collected_at
    s = {"cpu": 0.0, "mem": 0.0, "disk": 0.0, "load": 0.0, "n": 0}

    for r in rows:
        if r.collected_at and (r.collected_at - bucket_start).total_seconds() >= bucket_m * 60:
            bucketed.append(_make_point(bucket_start, s))
            bucket_start = r.collected_at
            s = {"cpu": 0.0, "mem": 0.0, "disk": 0.0, "load": 0.0, "n": 0}
        s["cpu"] += r.cpu_percent
        s["mem"] += r.mem_percent
        s["disk"] += r.disk_percent
        s["load"] += r.load_1m
        s["n"] += 1

    if s["n"] > 0:
        bucketed.append(_make_point(bucket_start, s))
    return bucketed


def _make_point(ts, s: dict) -> dict:
    n = s["n"]
    return {
        "collected_at": ts.isoformat() if ts else None,
        "cpu_percent": round(s["cpu"] / n, 1),
        "mem_percent": round(s["mem"] / n, 1),
        "disk_percent": round(s["disk"] / n, 1),
        "load_1m": round(s["load"] / n, 2),
    }


def get_latest_metric(db: Session, host_id: int) -> dict | None:
    row = (
        db.query(HostMetric)
        .filter(HostMetric.host_id == host_id)
        .order_by(HostMetric.collected_at.desc())
        .first()
    )
    if not row:
        return None
    return {
        "id": row.id, "host_id": row.host_id,
        "cpu_percent": row.cpu_percent, "cpu_count": row.cpu_count,
        "mem_total_mb": row.mem_total_mb, "mem_used_mb": row.mem_used_mb,
        "mem_percent": row.mem_percent,
        "disk_total_gb": row.disk_total_gb, "disk_used_gb": row.disk_used_gb,
        "disk_percent": row.disk_percent,
        "load_1m": row.load_1m, "load_5m": row.load_5m, "load_15m": row.load_15m,
        "net_rx_bytes": row.net_rx_bytes, "net_tx_bytes": row.net_tx_bytes,
        "process_count": row.process_count, "uptime_seconds": row.uptime_seconds,
        "collected_at": row.collected_at.isoformat() if row.collected_at else None,
    }


def check_offline_hosts(db: Session) -> None:
    threshold = china_now() - timedelta(minutes=settings.host_agent_offline_minutes)
    db.query(Host).filter(
        Host.agent_token.isnot(None),
        Host.last_seen_at.isnot(None),
        Host.last_seen_at < threshold,
        Host.is_online.is_(True),
    ).update({"is_online": False}, synchronize_session=False)
    db.commit()


def cleanup_old_metrics(db: Session) -> None:
    threshold = china_now() - timedelta(days=settings.host_agent_metrics_retention_days)
    deleted = (
        db.query(HostMetric)
        .filter(HostMetric.collected_at < threshold)
        .delete(synchronize_session=False)
    )
    db.commit()
    if deleted:
        logger.info("Cleaned up %d old host metrics (retention=%d days)",
                    deleted, settings.host_agent_metrics_retention_days)


def process_events(db: Session, host_id: int, events: list[AgentEventItem]) -> None:
    """Process and store system events reported by agent."""
    if not events:
        return
    for evt in events:
        # Parse timestamp
        from datetime import datetime
        try:
            ts = datetime.fromisoformat(evt.timestamp.replace("Z", "+00:00"))
        except (ValueError, AttributeError):
            ts = china_now()

        record = HostEvent(
            host_id=host_id,
            category=evt.category,
            severity=evt.severity,
            source=evt.source,
            title=evt.title[:256] if evt.title else "",
            detail=evt.detail,
            labels=json.dumps(evt.labels, ensure_ascii=False) if evt.labels else "{}",
            created_at=ts,
        )
        db.add(record)

        # Log critical events
        if evt.severity == "critical":
            logger.warning("CRITICAL event on host %d: [%s] %s", host_id, evt.category, evt.title)

    db.commit()


def get_host_events(db: Session, host_id: int, hours: int = 24,
                    severity: str | None = None, category: str | None = None) -> list[dict]:
    """Get host events with optional filtering."""
    start = china_now() - timedelta(hours=hours)
    query = db.query(HostEvent).filter(
        HostEvent.host_id == host_id,
        HostEvent.created_at >= start,
    )
    if severity:
        query = query.filter(HostEvent.severity == severity)
    if category:
        query = query.filter(HostEvent.category == category)

    rows = query.order_by(HostEvent.created_at.desc()).limit(200).all()
    return [{
        "id": r.id, "host_id": r.host_id,
        "category": r.category, "severity": r.severity,
        "source": r.source, "title": r.title,
        "detail": r.detail, "labels": r.labels,
        "created_at": r.created_at.isoformat() if r.created_at else None,
    } for r in rows]


def cleanup_old_events(db: Session) -> None:
    """Delete host events older than retention period."""
    threshold = china_now() - timedelta(days=settings.host_agent_metrics_retention_days)
    deleted = (
        db.query(HostEvent)
        .filter(HostEvent.created_at < threshold)
        .delete(synchronize_session=False)
    )
    db.commit()
    if deleted:
        logger.info("Cleaned up %d old host events (retention=%d days)",
                    deleted, settings.host_agent_metrics_retention_days)
