from datetime import datetime

from pydantic import BaseModel


class NotepadCreate(BaseModel):
    title: str
    content: str = ""


class NotepadUpdate(BaseModel):
    title: str | None = None
    content: str | None = None


class NotepadResponse(BaseModel):
    id: int
    title: str
    content: str
    created_at: datetime | None = None
    updated_at: datetime | None = None

    model_config = {"from_attributes": True}
