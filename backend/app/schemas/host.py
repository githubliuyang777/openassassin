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
    created_at: datetime | None = None
    updated_at: datetime | None = None

    model_config = {"from_attributes": True}
