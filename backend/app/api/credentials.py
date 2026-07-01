from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.middleware.auth_middleware import get_current_user
from app.schemas.credential import CredentialCreate, CredentialUpdate, CredentialResponse, CredentialRevealResponse
from app.models.credential import Credential
from app.services import credential_service

router = APIRouter(prefix="/credentials", tags=["credentials"])


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
    encrypted = credential_service.encrypt(data.value)
    cred = Credential(
        name=data.name,
        key=data.key,
        encrypted_value=encrypted,
        description=data.description,
        type=data.type,
        expires_at=data.expires_at,
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
