from datetime import datetime
from typing import Optional
from pydantic import BaseModel


class ScriptCreate(BaseModel):
    name: str
    description: str = ""
    type: str  # shell | python
    content: str
    timeout: int = 300
    env_vars: dict = {}


class ScriptUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    type: Optional[str] = None
    content: Optional[str] = None
    timeout: Optional[int] = None
    env_vars: Optional[dict] = None


class ScriptResponse(BaseModel):
    id: int
    name: str
    description: str
    type: str
    content: str
    timeout: int
    env_vars: dict
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class ScriptExecuteRequest(BaseModel):
    credential_ids: list[int] = []
