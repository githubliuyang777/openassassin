from pydantic import BaseModel


class SiteMonitorSummary(BaseModel):
    id: int
    name: str
    target: str
    is_up: bool
    response_ms: float | None = None


class SiteMonitorOverview(BaseModel):
    total: int
    up: int
    down: int
    items: list[SiteMonitorSummary]


class DomainCertSummary(BaseModel):
    id: int
    domain: str
    ssl_expired: bool
    days_remaining: int | None = None


class DomainCertOverview(BaseModel):
    total: int
    valid: int
    expiring: int
    expired: int
    items: list[DomainCertSummary]


class DomainWhoisSummary(BaseModel):
    id: int
    domain: str
    days_remaining: int | None = None


class DomainWhoisOverview(BaseModel):
    total: int
    valid: int
    expiring: int
    expired: int
    items: list[DomainWhoisSummary]


class MonitorSummaryResponse(BaseModel):
    site_monitors: SiteMonitorOverview
    domain_certs: DomainCertOverview
    domain_whois: DomainWhoisOverview
