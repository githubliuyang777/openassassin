from pydantic import BaseModel


class AlertItemResponse(BaseModel):
    id: str
    source: str
    message: str
    severity: str
    link: str | None = None

    model_config = {"from_attributes": True}
