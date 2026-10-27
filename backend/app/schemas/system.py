from pydantic import BaseModel


class VersionInfo(BaseModel):
    version: str
