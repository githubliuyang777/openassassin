from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class TestEmailRequest(BaseModel):
    email: str = Field(
        min_length=3,
        max_length=254,
        pattern=r"^[^@\s]+@[^@\s]+\.[^@\s]+$",
    )
    provider: Literal["auto", "primary", "fallback"] = "auto"


class SmtpProviderStatus(BaseModel):
    configured: bool
    host: str | None = None
    port: int | None = None
    from_addr: str | None = Field(default=None, alias="from")
    use_tls: bool = True
    health: Literal["closed", "open", "half_open"] = "closed"
    last_error: str | None = None
    last_success_at: datetime | None = None

    model_config = ConfigDict(populate_by_name=True)


class SmtpStatusResponse(BaseModel):
    configured: bool
    alert_configured: bool
    transactional_configured: bool
    primary: SmtpProviderStatus
    fallback: SmtpProviderStatus
    alert_failover_enabled: bool
    active_circuit: Literal["primary", "fallback"] | None = None
    # Legacy top-level fields: primary SMTP only.
    host: str | None = None
    port: int | None = None
    from_addr: str | None = Field(default=None, alias="from")
    use_tls: bool = True

    model_config = ConfigDict(populate_by_name=True)


class TestEmailResponse(BaseModel):
    message: str
    provider: Literal["primary", "fallback"] | None = None
    failover: bool = False
