from datetime import datetime
from urllib.parse import urlparse

from pydantic import BaseModel, Field, field_validator


def _validate_panel_url(value: str) -> str:
    value = (value or "").strip().rstrip("/")
    parsed = urlparse(value)
    if (
        parsed.scheme not in ("http", "https")
        or not parsed.netloc
        or parsed.username
        or parsed.password
        or parsed.query
        or parsed.fragment
    ):
        raise ValueError("面板地址必须为 http(s) URL，且不能包含用户名密码、查询参数或片段")
    return value


class BaotaPanelCreate(BaseModel):
    name: str = Field(min_length=1, max_length=128)
    panel_url: str = Field(min_length=1, max_length=512)
    api_key: str = Field(min_length=1, max_length=256)
    verify_tls: bool = True
    enabled: bool = True

    @field_validator("name", "api_key")
    @classmethod
    def _strip_required(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("不能为空")
        return value

    @field_validator("panel_url")
    @classmethod
    def _url(cls, value: str) -> str:
        return _validate_panel_url(value)


class BaotaPanelUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=128)
    panel_url: str | None = Field(default=None, min_length=1, max_length=512)
    api_key: str | None = Field(default=None, max_length=256)
    verify_tls: bool | None = None
    enabled: bool | None = None

    @field_validator("name")
    @classmethod
    def _strip_name(cls, value: str | None) -> str | None:
        if value is None:
            return None
        value = value.strip()
        if not value:
            raise ValueError("名称不能为空")
        return value

    @field_validator("panel_url")
    @classmethod
    def _url(cls, value: str | None) -> str | None:
        return None if value is None else _validate_panel_url(value)


class BaotaPanelResponse(BaseModel):
    id: int
    name: str
    panel_url: str
    verify_tls: bool = True
    enabled: bool = True
    api_key_configured: bool = False
    created_at: datetime | None = None
    updated_at: datetime | None = None


class BaotaSite(BaseModel):
    id: int
    name: str


class BaotaOrder(BaseModel):
    index: str
    domains: list[str] = Field(default_factory=list)
    status: str = ""
    cert_timeout: int = 0
    auth_type: str = ""


class BaotaTestResponse(BaseModel):
    ok: bool = True
    message: str = ""
    sites: list[BaotaSite] = Field(default_factory=list)
    orders: list[BaotaOrder] = Field(default_factory=list)


class CertProviderItem(BaseModel):
    key: str
    name: str
    enabled: bool = True
