from datetime import datetime
from pydantic import BaseModel, Field


class DomainCreate(BaseModel):
    domain: str
    port: int = 443


class DomainBatchImport(BaseModel):
    domains: list[str]


class DomainResponse(BaseModel):
    id: int
    domain: str
    port: int
    ssl_subject: str | None = None
    ssl_issuer: str | None = None
    ssl_not_before: datetime | None = None
    ssl_not_after: datetime | None = None
    ssl_expired: bool = False
    alert_enabled: bool = True
    days_remaining: int | None = None
    last_checked_at: datetime | None = None
    created_at: datetime | None = None

    model_config = {"from_attributes": True}
