from datetime import datetime
from pydantic import BaseModel


class AuditLogResponse(BaseModel):
    id: int
    user_id: int
    username: str
    action: str
    resource: str
    resource_type: str
    detail: str
    ip_address: str
    ip_location: str
    user_agent: str
    status_code: int
    created_at: datetime | None = None

    model_config = {"from_attributes": True}


class AuditLogListResponse(BaseModel):
    items: list[AuditLogResponse]
    total: int
    page: int
    page_size: int
