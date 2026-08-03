from sqlalchemy.orm import Session

from app.models.host import Host
from app.models.credential import Credential
from app.schemas.host import HostCreate, HostUpdate, HostImportRequest
from app.services.credential_service import decrypt
from app.services.aws_service import AwsError, get_boto3_session


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


def import_from_ec2(db: Session, data: HostImportRequest) -> Host:
    """Import an EC2 instance as a managed host.

    Raises AwsError if the AWS credential is invalid or the instance is not found.
    """
    from app.services.aws_service import _ec2_client, _describe_instances, _parse_ec2_instance

    # Validate AWS credential
    session = get_boto3_session(db, data.aws_credential_id)

    # Validate SSH credential if provided
    if data.credential_id is not None:
        cred = db.query(Credential).filter(Credential.id == data.credential_id).first()
        if not cred:
            raise AwsError(f"SSH 凭证 id={data.credential_id} 不存在")
        if cred.type not in ("ssh_key", "ssh_password", "generic"):
            raise AwsError("SSH 凭证类型不正确，请选择 ssh_key/ssh_password 类型")

    # Fetch EC2 instance details
    try:
        ec2 = _ec2_client(session, data.aws_region)
        raw = _describe_instances(ec2, InstanceIds=[data.aws_instance_id])
    except Exception as exc:
        raise AwsError(f"EC2 DescribeInstances {data.aws_instance_id} 失败: {exc}") from exc

    if not raw:
        raise AwsError(f"实例 {data.aws_instance_id} 在 {data.aws_region} 中未找到 (可能已终止)")

    inst = _parse_ec2_instance(raw[0])

    host = Host(
        name=data.name or inst["name"],
        hostname=inst["public_ip"] or inst["private_ip"] or inst["instance_id"],
        port=data.port or 22,
        username=data.username or "root",
        credential_id=data.credential_id,
        aws_instance_id=data.aws_instance_id,
        aws_region=data.aws_region,
        aws_credential_id=data.aws_credential_id,
        description=data.description or f"EC2: {data.aws_instance_id} ({inst['instance_type']}, {inst['availability_zone']})",
    )
    db.add(host)
    db.commit()
    db.refresh(host)
    return host
