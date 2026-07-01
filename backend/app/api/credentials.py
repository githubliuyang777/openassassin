import base64
import yaml
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.database import get_db, CHINA_TZ, china_now
from app.middleware.auth_middleware import get_current_user
from app.schemas.credential import CredentialCreate, CredentialUpdate, CredentialResponse, CredentialRevealResponse
from app.models.credential import Credential
from app.services import credential_service

router = APIRouter(prefix="/credentials", tags=["credentials"])


def _parse_kubeconfig_expiry(content: str) -> datetime | None:
    """Try to extract client certificate expiry from kubeconfig content. Returns None if not found."""
    if not content:
        return None
    try:
        cfg = yaml.safe_load(content)
    except Exception:
        return None

    cert_b64 = None
    for user in cfg.get("users", []) or []:
        u = user.get("user", {}) or {}
        if u.get("client-certificate-data"):
            cert_b64 = u["client-certificate-data"]
            break

    if not cert_b64:
        return None

    try:
        der = base64.b64decode(cert_b64)
        from cryptography import x509
        cert = x509.load_pem_x509_certificate(der) if der.startswith(b"-----") else x509.load_der_x509_certificate(der)
        utc_expiry = cert.not_valid_after_utc if hasattr(cert, 'not_valid_after_utc') else cert.not_valid_after.replace(tzinfo=timezone.utc)
        return utc_expiry.astimezone(CHINA_TZ).replace(tzinfo=None)
    except Exception:
        return None


@router.post("/parse-kubeconfig")
def parse_kubeconfig(body: dict):
    """Parse a kubeconfig value and extract the client certificate expiry date."""
    content = body.get("value", "")
    if not content:
        raise HTTPException(status_code=400, detail="请提供 kubeconfig 内容")

    expires_at = _parse_kubeconfig_expiry(content)
    if expires_at is None:
        raise HTTPException(status_code=400, detail="kubeconfig 中未找到 client-certificate-data 或证书解析失败")

    return {
        "expires_at": expires_at.strftime("%Y-%m-%dT%H:%M:%S"),
        "days_left": (expires_at - china_now()).days,
    }


@router.get("", response_model=list[CredentialResponse])
def list_credentials(
    db: Session = Depends(get_db),
    _user: dict = Depends(get_current_user),
):
    return db.query(Credential).order_by(Credential.updated_at.desc()).all()


@router.post("", response_model=CredentialResponse, status_code=201)
def create_credential(
    data: CredentialCreate,
    db: Session = Depends(get_db),
    _user: dict = Depends(get_current_user),
):
    expires_at = data.expires_at
    if expires_at is None and data.type == "kubeconfig":
        expires_at = _parse_kubeconfig_expiry(data.value)

    encrypted = credential_service.encrypt(data.value)
    cred = Credential(
        name=data.name,
        key=data.key,
        encrypted_value=encrypted,
        description=data.description,
        type=data.type,
        expires_at=expires_at,
    )
    db.add(cred)
    db.commit()
    db.refresh(cred)
    return cred


@router.get("/{credential_id}", response_model=CredentialRevealResponse)
def reveal_credential(
    credential_id: int,
    db: Session = Depends(get_db),
    _user: dict = Depends(get_current_user),
):
    cred = db.query(Credential).filter(Credential.id == credential_id).first()
    if not cred:
        raise HTTPException(status_code=404, detail="密钥不存在")
    return CredentialRevealResponse(
        id=cred.id,
        name=cred.name,
        key=cred.key,
        value=credential_service.decrypt(cred.encrypted_value),
        description=cred.description,
        type=cred.type,
        expires_at=cred.expires_at,
        alert_enabled=cred.alert_enabled,
    )


@router.put("/{credential_id}", response_model=CredentialResponse)
def update_credential(
    credential_id: int,
    data: CredentialUpdate,
    db: Session = Depends(get_db),
    _user: dict = Depends(get_current_user),
):
    cred = db.query(Credential).filter(Credential.id == credential_id).first()
    if not cred:
        raise HTTPException(status_code=404, detail="密钥不存在")
    for k, v in data.model_dump(exclude_unset=True).items():
        setattr(cred, k, v)
    db.commit()
    db.refresh(cred)
    return cred


@router.delete("/{credential_id}", status_code=204)
def delete_credential(
    credential_id: int,
    db: Session = Depends(get_db),
    _user: dict = Depends(get_current_user),
):
    cred = db.query(Credential).filter(Credential.id == credential_id).first()
    if not cred:
        raise HTTPException(status_code=404, detail="密钥不存在")
    db.delete(cred)
    db.commit()
