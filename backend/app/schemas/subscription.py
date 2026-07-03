from datetime import datetime
from pydantic import BaseModel, Field


class SubscriptionCreate(BaseModel):
    name: str
    repo_url: str
    repo_platform: str = "github"
    repo_owner: str = ""
    repo_name: str = ""


class SubscriptionUpdate(BaseModel):
    name: str | None = None
    repo_url: str | None = None
    repo_platform: str | None = None
    repo_owner: str | None = None
    repo_name: str | None = None


class SubscriptionResponse(BaseModel):
    id: int
    name: str
    repo_url: str
    repo_platform: str
    repo_owner: str
    repo_name: str
    last_version: str
    last_checked_at: datetime | None = None
    alert_count: int = 0
    created_at: datetime | None = None
    updated_at: datetime | None = None

    model_config = {"from_attributes": True}


class SubscriptionAlertResponse(BaseModel):
    id: int
    subscription_id: int
    alert_type: str
    title: str
    summary: str
    url: str
    occurred_at: datetime | None = None
    is_read: bool = False
    created_at: datetime | None = None

    model_config = {"from_attributes": True}


class RepoLookupRequest(BaseModel):
    repo_url: str


class RepoLookupResponse(BaseModel):
    repo_owner: str
    repo_name: str
    repo_platform: str
    description: str = ""
    latest_version: str = ""
