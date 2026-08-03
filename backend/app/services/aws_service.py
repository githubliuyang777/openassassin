"""AWS service layer — boto3 session management and EC2 operations.

Credentials are stored as AES-256-GCM encrypted JSON in the credentials table
(type="aws"). This module decrypts them, creates boto3 Sessions, and wraps the
EC2 API into simple return dicts consumed by the API layer.
"""

import json
import logging

import boto3
from botocore.exceptions import ClientError, BotoCoreError, NoCredentialsError
from sqlalchemy.orm import Session

from app.config import settings
from app.models.credential import Credential
from app.services import credential_service

logger = logging.getLogger(__name__)


class AwsError(Exception):
    """Raised when an AWS operation cannot proceed (bad creds, missing region, etc.)."""


# ---------------------------------------------------------------------------
# session helpers
# ---------------------------------------------------------------------------

def _decrypt_aws_data(db: Session, credential_id: int) -> dict:
    """Look up an AWS credential and return its decrypted JSON payload."""
    cred = db.query(Credential).filter(Credential.id == credential_id).first()
    if not cred:
        raise AwsError(f"凭证 id={credential_id} 不存在")
    if cred.type != "aws":
        raise AwsError("该凭证不是 AWS 类型")
    try:
        return json.loads(credential_service.decrypt(cred.encrypted_value))
    except (json.JSONDecodeError, ValueError) as exc:
        raise AwsError(f"AWS 凭证 JSON 解析失败: {exc}") from exc


def get_boto3_session(db: Session, credential_id: int) -> boto3.Session:
    """Return a boto3 Session for the given AWS credential."""
    data = _decrypt_aws_data(db, credential_id)
    try:
        return boto3.Session(
            aws_access_key_id=data["access_key_id"],
            aws_secret_access_key=data["secret_access_key"],
            aws_session_token=data.get("session_token"),
            region_name=data.get("region", settings.aws_default_region),
        )
    except KeyError as exc:
        raise AwsError(f"AWS 凭证缺少必需字段: {exc}") from exc


# ---------------------------------------------------------------------------
# credential validation
# ---------------------------------------------------------------------------

def validate_aws_credentials(data: dict) -> dict:
    """Call sts:GetCallerIdentity to verify AWS credentials.

    `data` is the **decrypted** credential JSON dict (access_key_id, secret_access_key, …).
    Returns identity info on success; raises AwsError on failure.
    """
    try:
        session = boto3.Session(
            aws_access_key_id=data["access_key_id"],
            aws_secret_access_key=data["secret_access_key"],
            aws_session_token=data.get("session_token"),
            region_name=data.get("region", settings.aws_default_region),
        )
        sts = session.client("sts")
        identity = sts.get_caller_identity()
        return {
            "account_id": identity["Account"],
            "arn": identity["Arn"],
            "user_id": identity["UserId"],
        }
    except KeyError as exc:
        raise AwsError(f"缺少必需字段: {exc}") from exc
    except (NoCredentialsError, ClientError) as exc:
        raise AwsError(f"AWS 凭据验证失败: {exc}") from exc


# ---------------------------------------------------------------------------
# EC2 helpers
# ---------------------------------------------------------------------------

def _ec2_client(session: boto3.Session, region: str):
    return session.client("ec2", region_name=region)


def _describe_instances(ec2, **filters) -> list[dict]:
    """Call ec2.describe_instances and flatten the reservation list."""
    instances: list[dict] = []
    paginator = ec2.get_paginator("describe_instances")
    for page in paginator.paginate(**filters):
        for reservation in page.get("Reservations", []):
            instances.extend(reservation.get("Instances", []))
    return instances


def _parse_ec2_instance(inst: dict) -> dict:
    """Extract the fields we expose to the frontend from a raw EC2 dict."""
    tags = {t["Key"]: t["Value"] for t in inst.get("Tags", [])}
    return {
        "instance_id": inst["InstanceId"],
        "name": tags.get("Name", inst["InstanceId"]),
        "instance_type": inst["InstanceType"],
        "state": inst["State"]["Name"],          # running | stopped | …
        "private_ip": inst.get("PrivateIpAddress", ""),
        "public_ip": inst.get("PublicIpAddress", ""),
        "launch_time": inst["LaunchTime"].isoformat() if inst.get("LaunchTime") else "",
        "availability_zone": inst["Placement"]["AvailabilityZone"],
        "tags": tags,
    }


def list_ec2_instances(db: Session, credential_id: int, region: str) -> list[dict]:
    """Return parsed EC2 instances for a credential + region."""
    session = get_boto3_session(db, credential_id)
    try:
        ec2 = _ec2_client(session, region)
        raw = _describe_instances(ec2)
    except (ClientError, BotoCoreError) as exc:
        raise AwsError(f"EC2 DescribeInstances 失败 ({region}): {exc}") from exc
    return [_parse_ec2_instance(inst) for inst in raw]


def get_ec2_instance(db: Session, credential_id: int, region: str, instance_id: str) -> dict:
    """Return a single EC2 instance detail dict."""
    session = get_boto3_session(db, credential_id)
    try:
        ec2 = _ec2_client(session, region)
        raw = _describe_instances(ec2, InstanceIds=[instance_id])
    except (ClientError, BotoCoreError) as exc:
        raise AwsError(f"EC2 DescribeInstances {instance_id} 失败: {exc}") from exc
    if not raw:
        raise AwsError(f"实例 {instance_id} 在 {region} 中未找到")
    inst = raw[0]
    result = _parse_ec2_instance(inst)
    # additional detail fields
    result["security_groups"] = [
        {"id": sg["GroupId"], "name": sg.get("GroupName", "")}
        for sg in inst.get("SecurityGroups", [])
    ]
    result["volumes"] = [
        {
            "id": b["Ebs"]["VolumeId"] if "Ebs" in b else "",
            "device": b["DeviceName"],
            "size_gb": vol.get("Size", 0) if (vol := _resolve_volume(ec2, b)) else 0,
        }
        for b in inst.get("BlockDeviceMappings", [])
    ]
    result["vpc_id"] = inst.get("VpcId", "")
    result["subnet_id"] = inst.get("SubnetId", "")
    return result


def _resolve_volume(ec2, block_device: dict) -> dict | None:
    """Optional: fetch volume details for a block-device mapping."""
    ebs = block_device.get("Ebs", {})
    vol_id = ebs.get("VolumeId")
    if not vol_id:
        return None
    try:
        resp = ec2.describe_volumes(VolumeIds=[vol_id])
        vols = resp.get("Volumes", [])
        return vols[0] if vols else None
    except Exception:
        return None


def ec2_instance_action(
    db: Session, credential_id: int, region: str, instance_id: str, action: str
) -> dict:
    """Start / stop / reboot an EC2 instance. Returns the new state."""
    valid = {"start", "stop", "reboot"}
    if action not in valid:
        raise AwsError(f"无效操作 '{action}'，仅支持: {', '.join(sorted(valid))}")
    session = get_boto3_session(db, credential_id)
    ec2 = _ec2_client(session, region)
    try:
        meth = getattr(ec2, f"{action}_instances")
        meth(InstanceIds=[instance_id])
        # fetch new state
        desc = _describe_instances(ec2, InstanceIds=[instance_id])
        new_state = desc[0]["State"]["Name"] if desc else "unknown"
    except (ClientError, BotoCoreError) as exc:
        raise AwsError(f"EC2 {action} {instance_id} 失败: {exc}") from exc
    return {"instance_id": instance_id, "action": action, "new_state": new_state}


def list_aws_regions() -> list[str]:
    """Return the configured AWS region list (comma-separated in settings)."""
    return [r.strip() for r in settings.aws_regions.split(",") if r.strip()]
