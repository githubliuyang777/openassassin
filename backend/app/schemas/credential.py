from datetime import datetime
from typing import Optional
from pydantic import BaseModel


class CredentialCreate(BaseModel):
    name: str
    key: str
    value: str
    description: str = ""


class CredentialResponse(BaseModel):
    id: int
    name: str
    key: str
    description: str
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class CredentialRevealResponse(BaseModel):
    id: int
    name: str
    key: str
    value: str
    description: str
