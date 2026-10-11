from typing import Literal

from pydantic import BaseModel, Field, field_validator

DataStatus = Literal["verified", "partial", "no_data_used", "unavailable"]
WasteCategory = Literal["organic", "plastic", "paper_cardboard", "metal", "glass", "electronic", "hazardous", "mixed", "unknown"]


class ChatRequest(BaseModel):
    message: str = Field(min_length=1, max_length=500)

    @field_validator("message")
    @classmethod
    def _clean(cls, v: str) -> str:
        v = "".join(ch for ch in v if ch.isprintable() or ch in "\n\t").strip()
        if not v:
            raise ValueError("message must not be blank")
        return v


class ReferencedBin(BaseModel):
    bin_id: str
    priority_score: int | None = None
    priority_level: Literal["LOW", "MEDIUM", "HIGH", "CRITICAL"] | None = None


class ChatResponse(BaseModel):
    status: Literal["ok", "unavailable"]
    answer: str
    referenced_bins: list[ReferencedBin]
    tools_used: list[str]
    data_status: DataStatus
    warnings: list[str] = []
    model: str | None = None


class ClassificationResult(BaseModel):
    category: WasteCategory
    confidence: float | None = Field(default=None, description="Always null: the provider returns no calibrated confidence")
    explanation: str
    handling_guidance: str
    limitations: list[str]


class AIStatus(BaseModel):
    chat_available: bool
    classification_available: bool
    text_model: str | None
    vision_model: str | None
    mcp_configured: bool
    notes: list[str]
