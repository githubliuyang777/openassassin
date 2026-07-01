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


class CredentialUpdate(BaseModel):
    description: Optional[str] = None
    type: Optional[str] = None
    expires_at: Optional[datetime] = None
    alert_enabled: Optional[bool] = None


class CredentialResponse(BaseModel):
    id: int
    name: str
    key: str
    description: str
    type: str
    expires_at: Optional[datetime] = None
    alert_enabled: bool = True
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
