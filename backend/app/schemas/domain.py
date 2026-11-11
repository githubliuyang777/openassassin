from datetime import datetime
from pydantic import BaseModel, Field


class DomainCreate(BaseModel):
    domain: str
    port: int = 443


class DomainBatchImport(BaseModel):
    domains: list[str]


class DomainUpdate(BaseModel):
    port: int | None = Field(default=None, ge=1, le=65535)
    alert_enabled: bool | None = None
    notification_group_id: int | None = None
    cert_provider: str | None = None
    cert_provider_config: dict | None = None
    cert_auto_renew: bool | None = None


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
    notification_group_id: int | None = None
    cert_provider: str = "none"
    cert_provider_config: dict = Field(default_factory=dict)
    cert_auto_renew: bool = False
    last_renew_attempt_at: datetime | None = None
    last_renew_status: str = ""
    last_renew_error: str = ""
    days_remaining: int | None = None
    last_checked_at: datetime | None = None
    created_at: datetime | None = None

    model_config = {"from_attributes": True}
