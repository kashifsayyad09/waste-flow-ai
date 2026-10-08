from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

PriorityLevel = Literal["LOW", "MEDIUM", "HIGH", "CRITICAL"]


class FactorScore(BaseModel):
    factor: str
    points: float
    max_points: int


class PriorityResult(BaseModel):
    bin_id: str
    priority_score: int = Field(ge=0, le=100)
    priority_level: PriorityLevel
    reasons: list[str]
    breakdown: list[FactorScore]


class CollectionStep(BaseModel):
    rank: int
    bin_id: str
    bin_name: str
    location: str
    priority_score: int
    priority_level: PriorityLevel
    reason: str


class CollectionPlan(BaseModel):
    generated_at: datetime
    total_bins: int
    collection_order: list[CollectionStep]
