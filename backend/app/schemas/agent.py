from pydantic import BaseModel


class AgentReportRequest(BaseModel):
    hostname: str = ""
    cpu_percent: float = 0.0
    cpu_count: int = 0
    mem_percent: float = 0.0
    mem_total_mb: float = 0.0
    mem_used_mb: float = 0.0
    disk_percent: float = 0.0
    disk_total_gb: float = 0.0
    disk_used_gb: float = 0.0
    load_1m: float = 0.0
    load_5m: float = 0.0
    load_15m: float = 0.0
    net_rx_bytes: int = 0
    net_tx_bytes: int = 0
    process_count: int = 0
    uptime_seconds: int = 0
    agent_version: str = ""


class AgentReportResponse(BaseModel):
    ok: bool = True


class AgentEventItem(BaseModel):
    timestamp: str = ""
    category: str = ""
    severity: str = "info"
    source: str = ""
    title: str = ""
    detail: str = ""
    labels: dict = {}


class AgentEventsRequest(BaseModel):
    events: list[AgentEventItem] = []


class HostStatusSummary(BaseModel):
    id: int
    name: str
    hostname: str
    is_online: bool
    last_seen_at: str | None = None
    cpu_usage: float = 0.0
    mem_usage: float = 0.0
    disk_usage: float = 0.0
    agent_version: str = ""

    model_config = {"from_attributes": True}
