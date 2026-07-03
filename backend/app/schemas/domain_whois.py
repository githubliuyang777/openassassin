from datetime import datetime
from pydantic import BaseModel


class DomainWhoisCreate(BaseModel):
    domain: str


class DomainWhoisBatchImport(BaseModel):
    domains: list[str]


class DomainWhoisResponse(BaseModel):
    id: int
    domain: str
    whois_expiry_date: datetime | None = None
    whois_creation_date: datetime | None = None
    whois_registrar: str | None = None
    whois_statuses: str | None = None
    whois_nameservers: str | None = None
    alert_enabled: bool = True
    days_remaining: int | None = None
    last_checked_at: datetime | None = None
    created_at: datetime | None = None

    model_config = {"from_attributes": True}
