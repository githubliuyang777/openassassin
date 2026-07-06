from sqlalchemy.orm import Session

from app.models.host import Host
from app.models.credential import Credential
from app.schemas.host import HostCreate, HostUpdate
from app.services.credential_service import decrypt


class HostNotFoundError(ValueError):
    """Raised when the host_id does not exist."""
    pass


class MissingCredentialError(ValueError):
    """Raised when the host has no credential configured or the credential was deleted."""
    pass


def list_hosts(db: Session) -> list[Host]:
    return db.query(Host).order_by(Host.updated_at.desc()).all()


def get_host(db: Session, host_id: int) -> Host | None:
    return db.query(Host).filter(Host.id == host_id).first()


def create_host(db: Session, data: HostCreate) -> Host:
    host = Host(**data.model_dump())
    db.add(host)
    db.commit()
    db.refresh(host)
    return host


def update_host(db: Session, host: Host, data: HostUpdate) -> Host:
    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(host, field, value)
    db.commit()
    db.refresh(host)
    return host


def delete_host(db: Session, host: Host) -> None:
    db.delete(host)
    db.commit()


def get_ssh_connection_info(db: Session, host_id: int) -> dict:
    host = db.query(Host).filter(Host.id == host_id).first()
    if not host:
        raise HostNotFoundError("主机不存在")
    if not host.credential_id:
        raise MissingCredentialError("未配置认证凭证")

    cred = db.query(Credential).filter(Credential.id == host.credential_id).first()
    if not cred:
        raise MissingCredentialError("凭证不存在或已被删除")

    return {
        "name": host.name,
        "hostname": host.hostname,
        "port": host.port,
        "username": host.username,
        "auth_type": cred.type,
        "auth_value": decrypt(cred.encrypted_value),
    }
