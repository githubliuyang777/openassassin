from pydantic import BaseModel, Field, field_validator


class BatchIdsRequest(BaseModel):
    ids: list[int] = Field(min_length=1, max_length=500)

    @field_validator("ids")
    @classmethod
    def validate_ids(cls, ids: list[int]) -> list[int]:
        if any(item <= 0 for item in ids):
            raise ValueError("ids must be positive integers")
        return list(dict.fromkeys(ids))


class BatchDeleteRequest(BatchIdsRequest):
    pass


class BatchToggleAlertRequest(BatchIdsRequest):
    enabled: bool = True


class BatchSetNotificationGroupRequest(BatchIdsRequest):
    notification_group_id: int | None = None


class BatchDeleteResponse(BaseModel):
    deleted: int
    missing: list[int] = Field(default_factory=list)
