from datetime import datetime
from typing import Optional, List

from pydantic import BaseModel


# ── Recipient ─────────────────────────────────────────────────────────────────

class NotificationRecipientCreate(BaseModel):
    name: str
    channel_type: str = "email"
    address: str
    group_id: int


class NotificationRecipientUpdate(BaseModel):
    name: Optional[str] = None
    channel_type: Optional[str] = None
    address: Optional[str] = None
    group_id: Optional[int] = None


class NotificationRecipientResponse(BaseModel):
    id: int
    name: str
    channel_type: str
    address: str
    group_id: int
    created_at: Optional[datetime] = None

    model_config = {"from_attributes": True}


# ── Group ─────────────────────────────────────────────────────────────────────

class NotificationGroupCreate(BaseModel):
    name: str


class NotificationGroupUpdate(BaseModel):
    name: Optional[str] = None


class NotificationGroupResponse(BaseModel):
    id: int
    name: str
    recipients: List[NotificationRecipientResponse] = []
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    model_config = {"from_attributes": True}
