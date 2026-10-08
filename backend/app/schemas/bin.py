from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

WasteType = Literal["organic", "plastic", "paper", "glass", "mixed"]
BinStatus = Literal["normal", "warning", "critical"]


class Bin(BaseModel):
    id: str
    name: str
    location: str
    latitude: float = Field(ge=-90, le=90)
    longitude: float = Field(ge=-180, le=180)
    fill_level: int = Field(ge=0, le=100, description="Percent full")
    waste_type: WasteType
    last_collected: datetime
    days_since_collection: int = Field(ge=0)
    temperature: float = Field(description="Degrees Celsius")
    estimated_overflow_time: int = Field(ge=0, description="Hours until overflow")
    status: BinStatus
