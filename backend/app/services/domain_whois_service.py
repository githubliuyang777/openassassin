from __future__ import annotations

import re
from datetime import datetime, timezone

import whois
from sqlalchemy.orm import Session

from app.models.domain_whois import DomainWhois

_DOMAIN_RE = re.compile(
    r"^(?:[a-zA-Z0-9](?:[a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?\.)+[a-zA-Z]{2,}$"
)


def _lookup_whois(domain: str) -> dict | None:
    """Query WHOIS for a domain. Returns parsed info dict or None on failure."""
    try:
        w = whois.query(domain)
    except Exception:
        return None

    if not w:
        return None

    return {
        "whois_expiry_date": _to_naive(w.expiration_date),
        "whois_creation_date": _to_naive(w.creation_date),
        "whois_registrar": w.registrar or "",
        "whois_statuses": "\n".join(w.statuses) if w.statuses else "",
        "whois_nameservers": "\n".join(w.name_servers) if w.name_servers else "",
        "last_checked_at": datetime.now(timezone.utc).replace(tzinfo=None),
    }


def _to_naive(dt) -> datetime | None:
    if dt is None:
        return None
    if dt.tzinfo is not None:
        return dt.astimezone(timezone.utc).replace(tzinfo=None)
    return dt


def _parse_domain_entry(entry: str) -> str | None:
    domain = entry.strip()
    if not domain:
        return None
    if ":" in domain:
        domain = domain.rsplit(":", 1)[0].strip()
    if not _DOMAIN_RE.match(domain):
        return None
    return domain.lower()


def add_domain(db: Session, domain: str) -> DomainWhois:
    dom = DomainWhois(domain=domain.lower())
    db.add(dom)
    db.flush()
    _update_whois(db, dom)
    db.commit()
    db.refresh(dom)
    return dom


def batch_import(db: Session, entries: list[str]) -> dict:
    result = {"added": 0, "skipped": 0, "invalid": 0}
    for entry in entries:
        parsed = _parse_domain_entry(entry)
        if not parsed:
            result["invalid"] += 1
            continue
        existing = db.query(DomainWhois).filter(DomainWhois.domain == parsed).first()
        if existing:
            result["skipped"] += 1
            continue
        dom = DomainWhois(domain=parsed)
        db.add(dom)
        db.flush()
        _update_whois(db, dom)
        result["added"] += 1
    db.commit()
    return result


def list_domains(db: Session) -> list[dict]:
    domains = db.query(DomainWhois).order_by(
        DomainWhois.whois_expiry_date.is_(None),
        DomainWhois.whois_expiry_date.asc()
    ).all()
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    results = []
    for d in domains:
        data = {
            "id": d.id,
            "domain": d.domain,
            "whois_expiry_date": d.whois_expiry_date,
            "whois_creation_date": d.whois_creation_date,
            "whois_registrar": d.whois_registrar,
            "whois_statuses": d.whois_statuses,
            "whois_nameservers": d.whois_nameservers,
            "alert_enabled": d.alert_enabled,
            "days_remaining": None,
            "last_checked_at": d.last_checked_at,
            "created_at": d.created_at,
        }
        if d.whois_expiry_date:
            data["days_remaining"] = (d.whois_expiry_date - now).days
        results.append(data)
    return results


def refresh_domain(db: Session, domain_id: int) -> DomainWhois | None:
    dom = db.query(DomainWhois).filter(DomainWhois.id == domain_id).first()
    if not dom:
        return None
    _update_whois(db, dom)
    db.commit()
    db.refresh(dom)
    return dom


def refresh_all_domains(db: Session) -> int:
    domains = db.query(DomainWhois).all()
    for dom in domains:
        _update_whois(db, dom)
    db.commit()
    return len(domains)


def toggle_alert(db: Session, domain_id: int) -> DomainWhois | None:
    dom = db.query(DomainWhois).filter(DomainWhois.id == domain_id).first()
    if not dom:
        return None
    dom.alert_enabled = not dom.alert_enabled
    db.commit()
    db.refresh(dom)
    return dom


def batch_toggle_alert(db: Session, ids: list[int], enabled: bool) -> int:
    query = db.query(DomainWhois)
    if ids:
        query = query.filter(DomainWhois.id.in_(ids))
    count = query.update({DomainWhois.alert_enabled: enabled}, synchronize_session=False)
    db.commit()
    return count


def delete_domain(db: Session, domain_id: int) -> bool:
    dom = db.query(DomainWhois).filter(DomainWhois.id == domain_id).first()
    if not dom:
        return False
    db.delete(dom)
    db.commit()
    return True


def _update_whois(db: Session, dom: DomainWhois) -> None:
    info = _lookup_whois(dom.domain)
    if info:
        dom.whois_expiry_date = info["whois_expiry_date"]
        dom.whois_creation_date = info["whois_creation_date"]
        dom.whois_registrar = info["whois_registrar"]
        dom.whois_statuses = info["whois_statuses"]
        dom.whois_nameservers = info["whois_nameservers"]
        dom.last_checked_at = info["last_checked_at"]
    else:
        dom.last_checked_at = datetime.now(timezone.utc).replace(tzinfo=None)
