from datetime import datetime
from typing import Optional

from pydantic import BaseModel


class DingTalkConfigUpdate(BaseModel):
    webhook_url: Optional[str] = None
    secret: Optional[str] = None
    is_enabled: Optional[bool] = None


class DingTalkConfigResponse(BaseModel):
    id: int
    webhook_url: str = ""
    is_enabled: bool = False
    secret_configured: bool = False
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    model_config = {"from_attributes": True}


class DingTalkStatusResponse(BaseModel):
    configured: bool
    enabled: bool
    webhook_masked: Optional[str] = None
