"""Pydantic schemas for AWS endpoints."""

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, field_validator

# -- EC2 -------------------------------------------------------------------

VALID_EC2_ACTIONS = {"start", "stop", "reboot"}


class Ec2ActionRequest(BaseModel):
    credential_id: int
    region: str
    action: str  # start | stop | reboot

    @field_validator("action")
    @classmethod
    def action_must_be_valid(cls, v: str) -> str:
        if v not in VALID_EC2_ACTIONS:
            raise ValueError(f"无效操作 '{v}'，仅支持: {', '.join(sorted(VALID_EC2_ACTIONS))}")
        return v

    @field_validator("region")
    @classmethod
    def region_not_empty(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("region 不能为空")
        return v.strip()


class Ec2InstanceResponse(BaseModel):
    instance_id: str
    name: str
    instance_type: str
    state: str
    private_ip: str
    public_ip: str
    launch_time: str
    availability_zone: str
    tags: dict[str, str]


class Ec2InstanceDetailResponse(Ec2InstanceResponse):
    security_groups: list[dict] = []
    volumes: list[dict] = []
    vpc_id: str = ""
    subnet_id: str = ""


class Ec2ActionResponse(BaseModel):
    instance_id: str
    action: str
    new_state: str


# -- Credential validation --------------------------------------------------

class ValidateAwsRequest(BaseModel):
    value: str  # raw JSON string (decrypted client-side not needed — server decrypts)


class ValidateAwsResponse(BaseModel):
    account_id: str
    arn: str
    user_id: str
