from pydantic import BaseModel


class VersionInfo(BaseModel):
    version: str


class TracingInfo(BaseModel):
    enabled: bool
    ui_url: str
