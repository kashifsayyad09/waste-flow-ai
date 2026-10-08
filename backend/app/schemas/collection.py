from datetime import datetime, timezone
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

CollectionStatus = Literal["completed", "skipped", "failed"]


class CollectionCreate(BaseModel):
    bin_id: str = Field(min_length=1, max_length=20)
    collected_at: datetime | None = Field(default=None, description="UTC; defaults to now")
    collection_status: CollectionStatus = "completed"
    notes: str | None = Field(default=None, max_length=500)

    @field_validator("collected_at")
    @classmethod
    def _to_utc(cls, v: datetime | None) -> datetime | None:
        if v is None:
            return None
        return (v.replace(tzinfo=timezone.utc) if v.tzinfo is None else v.astimezone(timezone.utc))


class CollectionRecord(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    bin_id: str
    collected_at: datetime
    collection_status: CollectionStatus
    notes: str | None
    created_at: datetime
