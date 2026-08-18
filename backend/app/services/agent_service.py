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

    # Check usage thresholds and send alerts
    if host:
        _check_usage_alerts(db, host, data)


def _check_usage_alerts(db: Session, host, data: AgentReportRequest) -> None:
    """Check CPU/mem/disk usage with consecutive confirmation and recovery notification."""
    from app.services.notification_service import send_group_notification
    from app.config import settings

    if not host.alert_enabled:
        return

    now = china_now()
    consecutive_required = settings.host_agent_alert_consecutive

    # Check which metrics exceed thresholds
    over_items = []
    if data.cpu_percent >= settings.host_agent_alert_cpu_percent:
        over_items.append(f"CPU 使用率 {data.cpu_percent}%（阈值 {settings.host_agent_alert_cpu_percent}%）")
    if data.mem_percent >= settings.host_agent_alert_mem_percent:
        over_items.append(f"内存使用率 {data.mem_percent}%（阈值 {settings.host_agent_alert_mem_percent}%）")
    if data.disk_percent >= settings.host_agent_alert_disk_percent:
        over_items.append(f"磁盘使用率 {data.disk_percent}%（阈值 {settings.host_agent_alert_disk_percent}%）")

    is_over = len(over_items) > 0

    if is_over:
        host.consecutive_alerts += 1

        # Consecutive count reached AND not already in alert state → trigger alert
        if host.consecutive_alerts >= consecutive_required and not host.alert_active:
            host.alert_active = True
            host.last_alerted_at = now

            duration_sec = host.consecutive_alerts * 30  # approximate based on report interval
            subject = f"[openAssassin] 主机资源告警: {host.name}"
            body = (
                f"主机 {host.name}（{host.hostname}）资源使用率持续超过阈值\n\n"
                + "\n".join(f"- {item}" for item in over_items)
                + f"\n\n连续 {host.consecutive_alerts} 次上报超阈值（持续约 {duration_sec} 秒）"
                + f"\n当前状态: CPU {data.cpu_percent}% | 内存 {data.mem_percent}% | 磁盘 {data.disk_percent}%"
                + f"\n告警时间: {now.strftime('%Y-%m-%d %H:%M:%S')}"
                + "\n\n请及时检查主机资源使用情况。"
            )

            try:
                send_group_notification(
                    db, host.notification_group_id, settings.alert_email, subject, body,
                )
                logger.info("Usage alert sent for host %d: %s", host.id, ", ".join(over_items))
            except Exception as e:
                logger.error("Failed to send usage alert for host %d: %s", host.id, e)

    else:
        # Below threshold — check if recovery notification needed
        if host.alert_active:
            host.alert_active = False
            host.consecutive_alerts = 0

            subject = f"[openAssassin] 主机资源恢复: {host.name}"
            body = (
                f"主机 {host.name}（{host.hostname}）资源使用率已恢复正常\n\n"
                f"当前状态: CPU {data.cpu_percent}% | 内存 {data.mem_percent}% | 磁盘 {data.disk_percent}%"
                f"\n恢复时间: {now.strftime('%Y-%m-%d %H:%M:%S')}"
            )

            try:
                send_group_notification(
                    db, host.notification_group_id, settings.alert_email, subject, body,
                )
                logger.info("Recovery notification sent for host %d", host.id)
            except Exception as e:
                logger.error("Failed to send recovery notification for host %d: %s", host.id, e)
        else:
            host.consecutive_alerts = 0

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
    """Process and store system events reported by agent, trigger alerts for critical events."""
    if not events:
        return

    host = db.query(Host).filter(Host.id == host_id).first()
    host_name = host.name if host else f"host-{host_id}"

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

    # Alert notifications
    _check_and_notify_events(db, host_id, host_name, host, events)


def _check_and_notify_events(db: Session, host_id: int, host_name: str, host, events: list[AgentEventItem]) -> None:
    """Check events and send notifications for critical/warning conditions."""
    from app.services.notification_service import send_group_notification
    from app.config import settings

    notification_group_id = host.notification_group_id if host else None
    fallback_email = settings.alert_email

    for evt in events:
        should_notify = False
        subject = ""
        body = ""

        # 1. OOM Kill — immediate critical alert
        if evt.category == "oom" and evt.severity == "critical":
            should_notify = True
            subject = f"[openAssassin] OOM Kill 告警: {host_name}"
            body = (
                f"主机 {host_name} 发生 OOM Kill 事件\n\n"
                f"事件: {evt.title}\n"
                f"详情: {evt.detail}\n"
                f"时间: {evt.timestamp}\n\n"
                f"请及时检查主机内存使用情况。"
            )

        # 2. Container OOM — immediate critical alert
        elif evt.category == "container" and evt.labels.get("action") == "oom":
            should_notify = True
            container = evt.labels.get("container", "unknown")
            subject = f"[openAssassin] 容器 OOM 告警: {host_name}"
            body = (
                f"主机 {host_name} 上容器发生 OOM\n\n"
                f"容器: {container}\n"
                f"镜像: {evt.labels.get('image', 'unknown')}\n"
                f"时间: {evt.timestamp}\n\n"
                f"请检查容器内存限制配置。"
            )

        # 3. Container die with non-zero exit code — check for repeated failures
        elif evt.category == "container" and evt.labels.get("action") == "die":
            exit_code = evt.labels.get("exit_code", "0")
            if exit_code != "0":
                container = evt.labels.get("container", "unknown")
                # Count recent die events for this container in last 5 minutes
                recent_count = (
                    db.query(HostEvent)
                    .filter(
                        HostEvent.host_id == host_id,
                        HostEvent.category == "container",
                        HostEvent.created_at >= china_now() - timedelta(minutes=5),
                    )
                    .count()
                )
                if recent_count >= 3:
                    should_notify = True
                    subject = f"[openAssassin] 容器反复退出告警: {host_name}"
                    body = (
                        f"主机 {host_name} 上容器频繁退出\n\n"
                        f"容器: {container}\n"
                        f"退出码: {exit_code}\n"
                        f"近 5 分钟事件数: {recent_count}\n"
                        f"时间: {evt.timestamp}\n\n"
                        f"请检查容器日志排查原因。"
                    )

        if should_notify:
            try:
                send_group_notification(db, notification_group_id, fallback_email, subject, body)
                logger.info("Event alert sent for host %d: %s", host_id, subject)
            except Exception as e:
                logger.error("Failed to send event alert for host %d: %s", host_id, e)


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
