from pydantic import BaseModel


class TestEmailRequest(BaseModel):
    email: str
