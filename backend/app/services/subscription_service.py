import json
import logging
import re
from datetime import datetime, timezone
from urllib.request import Request, urlopen

from sqlalchemy.orm import Session

from app.config import settings
from app.database import SessionLocal
from app.models.subscription import Subscription, SubscriptionAlert

logger = logging.getLogger(__name__)

_GITHUB_URL_RE = re.compile(r"https?://github\.com/([^/]+)/([^/]+)/?")


def list_subscriptions(db: Session) -> list[dict]:
    subs = db.query(Subscription).order_by(Subscription.updated_at.desc()).all()
    results = []
    for s in subs:
        alert_count = (
            db.query(SubscriptionAlert)
            .filter(SubscriptionAlert.subscription_id == s.id, SubscriptionAlert.is_read == False)
            .count()
        )
        results.append({
            "id": s.id, "name": s.name, "repo_url": s.repo_url,
            "repo_platform": s.repo_platform, "repo_owner": s.repo_owner, "repo_name": s.repo_name,
            "last_version": s.last_version, "last_checked_at": s.last_checked_at,
            "alert_count": alert_count,
            "alert_enabled": getattr(s, 'alert_enabled', True),
            "notification_group_id": getattr(s, 'notification_group_id', None),
            "created_at": s.created_at, "updated_at": s.updated_at,
        })
    return results


def get_subscription(db: Session, sub_id: int) -> Subscription | None:
    return db.query(Subscription).filter(Subscription.id == sub_id).first()


def create_subscription(db: Session, data) -> Subscription:
    sub = Subscription(**data.model_dump())
    db.add(sub)
    db.commit()
    db.refresh(sub)
    return sub


def update_subscription(db: Session, sub: Subscription, data) -> Subscription:
    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(sub, field, value)
    db.commit()
    db.refresh(sub)
    return sub


def delete_subscription(db: Session, sub: Subscription) -> None:
    db.query(SubscriptionAlert).filter(SubscriptionAlert.subscription_id == sub.id).delete()
    db.delete(sub)
    db.commit()


def list_alerts(db: Session, sub_id: int) -> list[SubscriptionAlert]:
    return (
        db.query(SubscriptionAlert)
        .filter(SubscriptionAlert.subscription_id == sub_id)
        .order_by(SubscriptionAlert.occurred_at.desc())
        .all()
    )


def mark_alert_read(db: Session, alert_id: int) -> None:
    alert = db.query(SubscriptionAlert).filter(SubscriptionAlert.id == alert_id).first()
    if alert:
        alert.is_read = True
        db.commit()


def lookup_repo(repo_url: str) -> dict:
    m = _GITHUB_URL_RE.match(repo_url.strip())
    if not m:
        return {"repo_owner": "", "repo_name": "", "repo_platform": "", "description": "", "latest_version": ""}
    owner, name = m.group(1), m.group(2).rstrip(".git")
    description = ""
    latest_version = ""
    try:
        req = Request(
            f"https://api.github.com/repos/{owner}/{name}",
            headers={"User-Agent": "ops-platform/1.0", "Accept": "application/vnd.github+json"},
        )
        with urlopen(req, timeout=5) as resp:
            data = json.loads(resp.read().decode())
            description = data.get("description", "") or ""
    except Exception:
        pass
    try:
        req = Request(
            f"https://api.github.com/repos/{owner}/{name}/releases?per_page=1",
            headers={"User-Agent": "ops-platform/1.0", "Accept": "application/vnd.github+json"},
        )
        with urlopen(req, timeout=5) as resp:
            releases = json.loads(resp.read().decode())
            if releases and isinstance(releases, list) and len(releases) > 0:
                latest_version = releases[0].get("tag_name", "") or ""
    except Exception:
        pass
    return {
        "repo_owner": owner, "repo_name": name, "repo_platform": "github",
        "description": description, "latest_version": latest_version,
    }


def check_updates(sub_id: int) -> int:
    """Check a single subscription for new releases/advisories. Returns alert count added."""
    db = SessionLocal()
    try:
        sub = db.query(Subscription).filter(Subscription.id == sub_id).first()
        if not sub:
            return 0
        count = 0
        new_releases = _fetch_new_releases(sub)
        for r in new_releases:
            _save_alert(db, sub, "release", r["title"], r["summary"], r["url"], r["ref_id"], r["occurred_at"])
            count += 1
        new_advisories = _fetch_new_advisories(sub)
        for a in new_advisories:
            _save_alert(db, sub, "advisory", a["title"], a["summary"], a["url"], a["ref_id"], a["occurred_at"])
            count += 1
        sub.last_checked_at = datetime.now(timezone.utc).replace(tzinfo=None)
        db.commit()
        return count
    except Exception:
        logger.warning("check_updates failed for subscription %s", sub_id, exc_info=True)
        return 0
    finally:
        db.close()


def _save_alert(db, sub, alert_type, title, summary, url, ref_id, occurred_at):
    existing = (
        db.query(SubscriptionAlert)
        .filter(SubscriptionAlert.subscription_id == sub.id, SubscriptionAlert.ref_id == ref_id)
        .first()
    )
    if existing:
        return
    alert = SubscriptionAlert(
        subscription_id=sub.id, alert_type=alert_type,
        title=title, summary=summary, url=url,
        ref_id=ref_id, occurred_at=occurred_at,
    )
    db.add(alert)
    if alert_type == "release":
        sub.last_version = ref_id
    elif alert_type == "advisory":
        sub.last_advisory_ghsa_id = ref_id


def _fetch_new_releases(sub: Subscription) -> list[dict]:
    results = []
    try:
        url = f"https://api.github.com/repos/{sub.repo_owner}/{sub.repo_name}/releases?per_page=5"
        req = Request(url, headers={"User-Agent": "ops-platform/1.0", "Accept": "application/vnd.github+json"})
        with urlopen(req, timeout=10) as resp:
            releases = json.loads(resp.read().decode())
        if not isinstance(releases, list):
            return results
        for r in releases:
            tag = r.get("tag_name", "")
            published = r.get("published_at", "")
            if tag and tag != sub.last_version:
                occurred = _parse_iso(published)
                if sub.last_checked_at and occurred and occurred <= sub.last_checked_at:
                    continue
                results.append({
                    "title": f"{sub.name} {tag} Released",
                    "summary": r.get("body", "")[:500] or "",
                    "url": r.get("html_url", ""),
                    "ref_id": tag,
                    "occurred_at": occurred,
                })
    except Exception:
        logger.debug("fetch releases failed for %s/%s", sub.repo_owner, sub.repo_name)
    return results


def _fetch_new_advisories(sub: Subscription) -> list[dict]:
    results = []
    try:
        url = f"https://api.github.com/repos/{sub.repo_owner}/{sub.repo_name}/security-advisories?per_page=5"
        req = Request(url, headers={"User-Agent": "ops-platform/1.0", "Accept": "application/vnd.github+json"})
        with urlopen(req, timeout=10) as resp:
            advisories = json.loads(resp.read().decode())
        if not isinstance(advisories, list):
            return results
        for a in advisories:
            ghsa_id = a.get("ghsa_id", "")
            published = a.get("published_at", "")
            if ghsa_id and ghsa_id != sub.last_advisory_ghsa_id:
                occurred = _parse_iso(published)
                if sub.last_checked_at and occurred and occurred <= sub.last_checked_at:
                    continue
                results.append({
                    "title": f"Security Advisory {ghsa_id}",
                    "summary": a.get("summary", "")[:500] or "",
                    "url": a.get("html_url", ""),
                    "ref_id": ghsa_id,
                    "occurred_at": occurred,
                })
    except Exception:
        logger.debug("fetch advisories failed for %s/%s", sub.repo_owner, sub.repo_name)
    return results


def _parse_iso(val: str | None) -> datetime | None:
    if not val:
        return None
    try:
        val = val.replace("Z", "+00:00")
        return datetime.fromisoformat(val).replace(tzinfo=None)
    except (ValueError, TypeError):
        return None


def check_all_subscriptions() -> int:
    """Check all subscriptions. Called from background task. Returns total alerts found."""
    db = SessionLocal()
    try:
        subs = db.query(Subscription).all()
    finally:
        db.close()
    total = 0
    for s in subs:
        total += check_updates(s.id)
    return total
