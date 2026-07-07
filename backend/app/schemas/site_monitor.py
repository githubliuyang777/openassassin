from datetime import datetime

from pydantic import BaseModel, Field


class SiteMonitorCreate(BaseModel):
    name: str
    target: str
    monitor_type: str = "http"
    http_method: str = "GET"
    expected_status_codes: str = "200"
    timeout: int = Field(default=10, ge=1, le=60)
    retries: int = Field(default=2, ge=0, le=10)
    check_interval: int = Field(default=300, ge=30)
    alert_enabled: bool = True
    group_name: str = ""


class SiteMonitorUpdate(BaseModel):
    name: str | None = None
    target: str | None = None
    monitor_type: str | None = None
    http_method: str | None = None
    expected_status_codes: str | None = None
    timeout: int | None = None
    retries: int | None = None
    check_interval: int | None = None
    alert_enabled: bool | None = None
    group_name: str | None = None


class SiteMonitorResponse(BaseModel):
    id: int
    name: str
    target: str
    monitor_type: str
    http_method: str
    expected_status_codes: str
    timeout: int
    retries: int
    check_interval: int
    alert_enabled: bool
    group_name: str
    is_up: bool
    last_checked_at: datetime | None = None
    last_response_ms: float | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None

    model_config = {"from_attributes": True}


class SiteCheckResultResponse(BaseModel):
    id: int
    monitor_id: int
    is_up: bool
    status_code: int | None = None
    response_ms: float | None = None
    error: str | None = None
    checked_at: datetime | None = None

    model_config = {"from_attributes": True}
