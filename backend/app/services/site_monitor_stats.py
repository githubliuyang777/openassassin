import csv
import io
from datetime import datetime, timedelta, timezone
from collections import defaultdict

from sqlalchemy.orm import Session

from app.models.site_monitor import SiteMonitor, SiteCheckResult
from app.database import china_now


def _period_start(dt: datetime, period: str) -> datetime:
    if period == "monthly":
        return dt.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    return dt.replace(month=1, day=1, hour=0, minute=0, second=0, microsecond=0)


def calc_monitor_sla(db: Session, monitor: SiteMonitor, start: datetime, end: datetime) -> dict:
    """Calculate SLA for a single monitor over [start, end]."""
    checks = (
        db.query(SiteCheckResult)
        .filter(
            SiteCheckResult.monitor_id == monitor.id,
            SiteCheckResult.checked_at >= start,
            SiteCheckResult.checked_at <= end,
        )
        .order_by(SiteCheckResult.checked_at.asc())
        .all()
    )

    if not checks:
        return {"name": monitor.name, "sla": None, "checks": 0, "down_count": 0}

    downtime_seconds = 0
    down_count = 0
    prev_time = start

    for c in checks:
        if not c.is_up:
            down_count += 1
            gap = (c.checked_at - prev_time).total_seconds()
            if gap > 0 and gap < 7200:  # cap gap at 2h to avoid huge spikes
                downtime_seconds += gap
        else:
            if down_count > 0:
                gap = (c.checked_at - prev_time).total_seconds()
                if 0 < gap < 7200:
                    downtime_seconds += gap
        prev_time = c.checked_at

    total_seconds = (end - start).total_seconds()
    sla = max(0.0, 100.0 - (downtime_seconds / total_seconds * 100.0)) if total_seconds > 0 else 100.0
    return {
        "name": monitor.name,
        "target": monitor.target,
        "monitor_type": monitor.monitor_type,
        "sla": round(sla, 2),
        "checks": len(checks),
        "down_count": down_count,
    }


def get_all_monitors_sla(db: Session, period: str) -> list[dict]:
    """Calculate SLA for all monitors for the given period (monthly/annual)."""
    now = china_now()
    start = _period_start(now, period)
    end = now

    monitors = db.query(SiteMonitor).order_by(SiteMonitor.name).all()
    results = []
    for m in monitors:
        r = calc_monitor_sla(db, m, start, end)
        r["period"] = period
        results.append(r)
    return results


def export_sla_csv(db: Session, period: str) -> str:
    """Generate CSV string for SLA export."""
    rows = get_all_monitors_sla(db, period)
    output = io.StringIO()
    writer = csv.writer(output)
    now = china_now()
    label = f"{now.year}年{now.month}月" if period == "monthly" else f"{now.year}年"

    writer.writerow([f"SLA 报告 — {label}", "", "", "", "", ""])
    writer.writerow(["名称", "类型", "目标", f"{label} SLA (%)", "检查次数", "故障次数"])
    for r in rows:
        writer.writerow([
            r["name"], r["monitor_type"], r["target"],
            f"{r['sla']}%" if r["sla"] is not None else "N/A",
            r["checks"], r["down_count"],
        ])
    return output.getvalue()


def get_heatmap_data(db: Session, monitor_id: int, days: int) -> list[dict]:
    """Get heatmap data for a monitor over the last N days, bucketed for display."""
    now = china_now()
    start = now - timedelta(days=days)

    checks = (
        db.query(SiteCheckResult)
        .filter(
            SiteCheckResult.monitor_id == monitor_id,
            SiteCheckResult.checked_at >= start,
        )
        .order_by(SiteCheckResult.checked_at.asc())
        .all()
    )

    if not checks:
        return []

    # Bucket size depends on time range
    bucket_minutes = {1: 5, 3: 15, 7: 30, 30: 120}.get(days, 30)

    buckets: dict[str, bool] = {}
    for c in checks:
        # Floor to bucket boundary
        ts = c.checked_at
        minute = (ts.minute // bucket_minutes) * bucket_minutes
        key = ts.replace(minute=minute, second=0, microsecond=0).isoformat()
        # In a bucket, if any check is down, the bucket is down
        if key not in buckets:
            buckets[key] = c.is_up
        else:
            buckets[key] = buckets[key] and c.is_up

    return [
        {"time": k, "is_up": v}
        for k, v in sorted(buckets.items())
    ]
