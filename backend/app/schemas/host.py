from datetime import datetime
from pydantic import BaseModel


class HostCreate(BaseModel):
    name: str
    hostname: str
    port: int = 22
    username: str
    credential_id: int | None = None
    aws_instance_id: str | None = None
    aws_region: str | None = None
    aws_credential_id: int | None = None
    description: str = ""


class HostImportRequest(BaseModel):
    aws_credential_id: int
    aws_region: str
    aws_instance_id: str
    name: str | None = None
    username: str | None = None
    port: int = 22
    credential_id: int | None = None
    description: str | None = None


class HostUpdate(BaseModel):
    name: str | None = None
    hostname: str | None = None
    port: int | None = None
    username: str | None = None
    credential_id: int | None = None
    aws_instance_id: str | None = None
    aws_region: str | None = None
    aws_credential_id: int | None = None
    description: str | None = None
    alert_enabled: bool | None = None
    notification_group_id: int | None = None


class HostResponse(BaseModel):
    id: int
    name: str
    hostname: str
    port: int
    username: str
    credential_id: int | None = None
    aws_instance_id: str | None = None
    aws_region: str | None = None
    aws_credential_id: int | None = None
    description: str
    agent_version: str = ""
    last_seen_at: datetime | None = None
    is_online: bool = False
    cpu_usage: float = 0.0
    cpu_count: int = 0
    mem_usage: float = 0.0
    disk_usage: float = 0.0
    alert_enabled: bool = True
    notification_group_id: int | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None

    model_config = {"from_attributes": True}
