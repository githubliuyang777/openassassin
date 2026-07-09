from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.middleware.auth_middleware import get_current_user
from app.schemas.domain_whois import DomainWhoisCreate, DomainWhoisBatchImport, DomainWhoisResponse
from app.services import domain_whois_service

router = APIRouter(prefix="/whois-domains", tags=["whois-domains"])


@router.get("", response_model=list[DomainWhoisResponse])
def list_domains(db: Session = Depends(get_db), _user: dict = Depends(get_current_user)):
    return domain_whois_service.list_domains(db)


@router.post("", response_model=DomainWhoisResponse, status_code=status.HTTP_201_CREATED)
def create_domain(
    body: DomainWhoisCreate,
    db: Session = Depends(get_db),
    _user: dict = Depends(get_current_user),
):
    existing = db.query(domain_whois_service.DomainWhois).filter(
        domain_whois_service.DomainWhois.domain == body.domain.lower()
    ).first()
    if existing:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="域名已存在")
    dom = domain_whois_service.add_domain(db, body.domain)
    return _to_response(dom)


@router.post("/batch-import")
def batch_import_domains(
    body: DomainWhoisBatchImport,
    db: Session = Depends(get_db),
    _user: dict = Depends(get_current_user),
):
    result = domain_whois_service.batch_import(db, body.domains)
    domains = domain_whois_service.list_domains(db)
    return {"result": result, "domains": domains}


@router.post("/refresh")
def refresh_all(
    db: Session = Depends(get_db),
    _user: dict = Depends(get_current_user),
):
    count = domain_whois_service.refresh_all_domains(db)
    domains = domain_whois_service.list_domains(db)
    return {"refreshed": count, "domains": domains}


@router.post("/{domain_id}/refresh", response_model=DomainWhoisResponse)
def refresh_single(
    domain_id: int,
    db: Session = Depends(get_db),
    _user: dict = Depends(get_current_user),
):
    dom = domain_whois_service.refresh_domain(db, domain_id)
    if not dom:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="域名不存在")
    return _to_response(dom)


@router.put("/{domain_id}/toggle-alert", response_model=DomainWhoisResponse)
def toggle_alert(
    domain_id: int,
    db: Session = Depends(get_db),
    _user: dict = Depends(get_current_user),
):
    dom = domain_whois_service.toggle_alert(db, domain_id)
    if not dom:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="域名不存在")
    return _to_response(dom)


@router.post("/batch-toggle-alert")
def batch_toggle_alert(
    body: dict,
    db: Session = Depends(get_db),
    _user: dict = Depends(get_current_user),
):
    ids = body.get("ids", [])
    enabled = body.get("enabled", True)
    count = domain_whois_service.batch_toggle_alert(db, ids, enabled)
    domains = domain_whois_service.list_domains(db)
    return {"updated": count, "domains": domains}


@router.post("/batch-set-notification-group")
def batch_set_notification_group(
    body: dict,
    db: Session = Depends(get_db),
    _user: dict = Depends(get_current_user),
):
    ids = body.get("ids", [])
    group_id = body.get("notification_group_id")
    count = domain_whois_service.batch_set_notification_group(db, ids, group_id)
    return {"updated": count}


@router.delete("/{domain_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_domain(
    domain_id: int,
    db: Session = Depends(get_db),
    _user: dict = Depends(get_current_user),
):
    ok = domain_whois_service.delete_domain(db, domain_id)
    if not ok:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="域名不存在")


def _to_response(dom) -> dict:
    from datetime import datetime, timezone
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    data = {
        "id": dom.id,
        "domain": dom.domain,
        "whois_expiry_date": dom.whois_expiry_date,
        "whois_creation_date": dom.whois_creation_date,
        "whois_registrar": dom.whois_registrar,
        "whois_statuses": dom.whois_statuses,
        "whois_nameservers": dom.whois_nameservers,
        "alert_enabled": dom.alert_enabled,
        "days_remaining": None,
        "last_checked_at": dom.last_checked_at,
        "created_at": dom.created_at,
    }
    if dom.whois_expiry_date:
        data["days_remaining"] = (dom.whois_expiry_date - now).days
    return data
