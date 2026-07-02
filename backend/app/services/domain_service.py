from __future__ import annotations

import re
import ssl
import socket
from datetime import datetime, timezone

from cryptography import x509
from cryptography.hazmat.backends import default_backend
from sqlalchemy.orm import Session

from app.models.domain import Domain

_DOMAIN_RE = re.compile(
    r"^(?:[a-zA-Z0-9](?:[a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?\.)+[a-zA-Z]{2,}$"
)


def _parse_domain_entry(entry: str) -> tuple[str, int] | None:
    """Parse a domain entry like 'example.com' or 'example.com:8443'."""
    entry = entry.strip()
    if not entry:
        return None
    if ":" in entry:
        parts = entry.rsplit(":", 1)
        domain = parts[0].strip()
        try:
            port = int(parts[1].strip())
        except ValueError:
            return None
    else:
        domain = entry
        port = 443
    if not _DOMAIN_RE.match(domain):
        return None
    return domain, port


def check_domain_cert(domain: str, port: int = 443) -> dict | None:
    """Fetch and parse SSL certificate from a domain. Returns cert info dict or None on failure."""
    try:
        pem = ssl.get_server_certificate((domain, port), timeout=10)
    except Exception:
        return None

    try:
        cert = x509.load_pem_x509_certificate(pem.encode(), default_backend())
    except Exception:
        return None

    try:
        not_after = cert.not_valid_after_utc
    except AttributeError:
        not_after = cert.not_valid_after.replace(tzinfo=timezone.utc)

    try:
        not_before = cert.not_valid_before_utc
    except AttributeError:
        not_before = cert.not_valid_before.replace(tzinfo=timezone.utc)

    now = datetime.now(timezone.utc)
    return {
        "ssl_subject": cert.subject.rfc4514_string(),
        "ssl_issuer": cert.issuer.rfc4514_string(),
        "ssl_not_before": not_before.replace(tzinfo=None),
        "ssl_not_after": not_after.replace(tzinfo=None),
        "ssl_expired": now > not_after,
        "last_checked_at": datetime.now(timezone.utc).replace(tzinfo=None),
    }


def add_domain(db: Session, domain: str, port: int = 443) -> Domain:
    """Add a single domain and immediately check its certificate."""
    dom = Domain(domain=domain.lower(), port=port)
    db.add(dom)
    db.flush()
    _update_cert(db, dom)
    db.commit()
    db.refresh(dom)
    return dom


def batch_import(db: Session, entries: list[str]) -> dict:
    """Batch import domains. Returns {added, skipped, invalid} counts."""
    result = {"added": 0, "skipped": 0, "invalid": 0}
    for entry in entries:
        parsed = _parse_domain_entry(entry)
        if not parsed:
            result["invalid"] += 1
            continue
        domain, port = parsed
        domain_lower = domain.lower()
        existing = db.query(Domain).filter(Domain.domain == domain_lower).first()
        if existing:
            result["skipped"] += 1
            continue
        dom = Domain(domain=domain_lower, port=port)
        db.add(dom)
        db.flush()
        _update_cert(db, dom)
        result["added"] += 1
    db.commit()
    return result


def list_domains(db: Session) -> list[dict]:
    """List all domains with computed days_remaining."""
    domains = db.query(Domain).order_by(Domain.id.desc()).all()
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    results = []
    for d in domains:
        data = {
            "id": d.id,
            "domain": d.domain,
            "port": d.port,
            "ssl_subject": d.ssl_subject,
            "ssl_issuer": d.ssl_issuer,
            "ssl_not_before": d.ssl_not_before,
            "ssl_not_after": d.ssl_not_after,
            "ssl_expired": d.ssl_expired,
            "days_remaining": None,
            "last_checked_at": d.last_checked_at,
            "created_at": d.created_at,
        }
        if d.ssl_not_after:
            delta = d.ssl_not_after - now
            data["days_remaining"] = delta.days
        results.append(data)
    return results


def refresh_domain(db: Session, domain_id: int) -> Domain | None:
    """Refresh certificate info for a single domain."""
    dom = db.query(Domain).filter(Domain.id == domain_id).first()
    if not dom:
        return None
    _update_cert(db, dom)
    db.commit()
    db.refresh(dom)
    return dom


def refresh_all_domains(db: Session) -> int:
    """Refresh certificate info for all domains. Returns count of refreshed domains."""
    domains = db.query(Domain).all()
    for dom in domains:
        _update_cert(db, dom)
    db.commit()
    return len(domains)


def delete_domain(db: Session, domain_id: int) -> bool:
    """Delete a domain. Returns True if deleted, False if not found."""
    dom = db.query(Domain).filter(Domain.id == domain_id).first()
    if not dom:
        return False
    db.delete(dom)
    db.commit()
    return True


def _update_cert(db: Session, dom: Domain) -> None:
    """Update cert info on a domain object (does not commit)."""
    info = check_domain_cert(dom.domain, dom.port)
    if info:
        dom.ssl_subject = info["ssl_subject"]
        dom.ssl_issuer = info["ssl_issuer"]
        dom.ssl_not_before = info["ssl_not_before"]
        dom.ssl_not_after = info["ssl_not_after"]
        dom.ssl_expired = info["ssl_expired"]
        dom.last_checked_at = info["last_checked_at"]
    else:
        dom.last_checked_at = datetime.now(timezone.utc).replace(tzinfo=None)
