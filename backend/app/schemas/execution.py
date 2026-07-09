from datetime import datetime
from typing import Optional
from pydantic import BaseModel


class ExecutionResponse(BaseModel):
    id: int
    script_id: int
    status: str
    started_at: datetime
    finished_at: Optional[datetime] = None
    exit_code: Optional[int] = None
    triggered_by: str
    credential_ids: list[int] = []

    model_config = {"from_attributes": True}


class ExecutionListResponse(BaseModel):
    total: int
    page: int
    page_size: int
    items: list[ExecutionResponse]
