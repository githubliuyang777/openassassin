from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.middleware.auth_middleware import get_current_admin_user, get_current_user
from app.schemas.domain import DomainCreate, DomainBatchImport, DomainResponse, DomainUpdate
from app.services import cert_provider_service, cert_renew_service, domain_service

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


@router.put("/{domain_id}", response_model=DomainResponse)
def update_domain(
    domain_id: int,
    body: DomainUpdate,
    db: Session = Depends(get_db),
    _user: dict = Depends(get_current_user),
):
    dom = db.query(domain_service.Domain).filter(domain_service.Domain.id == domain_id).first()
    if not dom:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="域名不存在")
    try:
        dom = domain_service.update_domain(db, dom, body)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc))
    return _to_response(dom)


@router.post("/{domain_id}/renew-cert", status_code=status.HTTP_202_ACCEPTED)
def renew_cert(
    domain_id: int,
    background: BackgroundTasks,
    db: Session = Depends(get_db),
    _user: dict = Depends(get_current_admin_user),
):
    dom = db.query(domain_service.Domain).filter(domain_service.Domain.id == domain_id).first()
    if not dom:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="域名不存在")
    provider_key = dom.cert_provider or "none"
    provider = cert_provider_service.get_provider(provider_key)
    if not provider:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="该域名未接入证书维护平台")
    try:
        provider.validate_config(db, dom.cert_provider_config or {})
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc))
    if cert_renew_service.is_renew_running():
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="已有证书续签任务进行中")
    background.add_task(cert_renew_service.renew_domain, domain_id)
    return {"message": "已开始续签"}


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


@router.post("/batch-set-notification-group")
def batch_set_notification_group(
    body: dict,
    db: Session = Depends(get_db),
    _user: dict = Depends(get_current_user),
):
    ids = body.get("ids", [])
    group_id = body.get("notification_group_id")
    count = domain_service.batch_set_notification_group(db, ids, group_id)
    return {"updated": count}


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
    """Convert Domain model to response dict with computed days_remaining."""
    return domain_service.domain_dict(dom)
