from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.middleware.auth_middleware import get_current_user
from app.schemas.domain import DomainCreate, DomainBatchImport, DomainResponse
from app.services import domain_service

router = APIRouter(prefix="/domains", tags=["domains"])


@router.get("", response_model=list[DomainResponse])
def list_domains(db: Session = Depends(get_db), _user: dict = Depends(get_current_user)):
    return domain_service.list_domains(db)


@router.post("", response_model=DomainResponse, status_code=status.HTTP_201_CREATED)
def create_domain(
    body: DomainCreate,
    db: Session = Depends(get_db),
    _user: dict = Depends(get_current_user),
):
    existing = db.query(domain_service.Domain).filter(
        domain_service.Domain.domain == body.domain.lower()
    ).first()
    if existing:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="域名已存在")
    dom = domain_service.add_domain(db, body.domain, body.port)
    return _to_response(dom)


@router.post("/batch-import")
def batch_import_domains(
    body: DomainBatchImport,
    db: Session = Depends(get_db),
    _user: dict = Depends(get_current_user),
):
    result = domain_service.batch_import(db, body.domains)
    # Refresh to get the full list after import
    domains = domain_service.list_domains(db)
    return {"result": result, "domains": domains}


@router.post("/refresh")
def refresh_all(
    db: Session = Depends(get_db),
    _user: dict = Depends(get_current_user),
):
    count = domain_service.refresh_all_domains(db)
    domains = domain_service.list_domains(db)
    return {"refreshed": count, "domains": domains}


@router.post("/{domain_id}/refresh", response_model=DomainResponse)
def refresh_single(
    domain_id: int,
    db: Session = Depends(get_db),
    _user: dict = Depends(get_current_user),
):
    dom = domain_service.refresh_domain(db, domain_id)
    if not dom:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="域名不存在")
    return _to_response(dom)


@router.put("/{domain_id}/toggle-alert", response_model=DomainResponse)
def toggle_alert(
    domain_id: int,
    db: Session = Depends(get_db),
    _user: dict = Depends(get_current_user),
):
    dom = domain_service.toggle_alert(db, domain_id)
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
    count = domain_service.batch_toggle_alert(db, ids, enabled)
    domains = domain_service.list_domains(db)
    return {"updated": count, "domains": domains}


@router.delete("/{domain_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_domain(
    domain_id: int,
    db: Session = Depends(get_db),
    _user: dict = Depends(get_current_user),
):
    ok = domain_service.delete_domain(db, domain_id)
    if not ok:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="域名不存在")


def _to_response(dom) -> dict:
    """Convert Domain model to response dict with days_remaining."""
    from datetime import datetime, timezone
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    data = {
        "id": dom.id,
        "domain": dom.domain,
        "port": dom.port,
        "ssl_subject": dom.ssl_subject,
        "ssl_issuer": dom.ssl_issuer,
        "ssl_not_before": dom.ssl_not_before,
        "ssl_not_after": dom.ssl_not_after,
        "ssl_expired": dom.ssl_expired,
        "alert_enabled": dom.alert_enabled,
        "days_remaining": None,
        "last_checked_at": dom.last_checked_at,
        "created_at": dom.created_at,
    }
    if dom.ssl_not_after:
        data["days_remaining"] = (dom.ssl_not_after - now).days
    return data
