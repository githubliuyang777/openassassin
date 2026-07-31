from datetime import datetime
from typing import Optional
from pydantic import BaseModel


class CredentialCreate(BaseModel):
    name: str
    key: str
    value: str
    description: str = ""
    type: str = "generic"
    expires_at: Optional[datetime] = None
    alert_enabled: bool = True
    notification_group_id: Optional[int] = None


class CredentialUpdate(BaseModel):
    description: Optional[str] = None
    type: Optional[str] = None
    expires_at: Optional[datetime] = None
    alert_enabled: Optional[bool] = None
    notification_group_id: Optional[int] = None


class CredentialResponse(BaseModel):
    id: int
    name: str
    key: str
    description: str
    type: str
    expires_at: Optional[datetime] = None
    alert_enabled: bool = True
    notification_group_id: Optional[int] = None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class CredentialRevealResponse(BaseModel):
    id: int
    name: str
    key: str
    value: str
    description: str
    type: str
    expires_at: Optional[datetime] = None
    alert_enabled: bool = True
    notification_group_id: Optional[int] = None
