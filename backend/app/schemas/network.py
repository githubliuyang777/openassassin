from pydantic import BaseModel, Field


class NetworkTestRequest(BaseModel):
    host: str
    port: int = Field(default=80, ge=1, le=65535)
    timeout: float = Field(default=5.0, ge=0.5, le=30.0)


class NetworkTestResponse(BaseModel):
    success: bool
    host: str
    port: int
    latency_ms: float | None = None
    error: str | None = None
