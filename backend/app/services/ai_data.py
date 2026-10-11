"""Read-only, AI-facing views of application data.

Shared by the MCP server tools (and testable on their own). All numbers come from the
database and the deterministic priority engine; nothing here calculates or invents a score.
"""
from typing import Literal

from sqlalchemy.orm import Session

from app.schemas.bin import Bin
from app.schemas.priority import PriorityResult
from app.services import bin_service
from app.services.collection_plan import build_collection_plan
from app.services.priority_engine import MAX_POINTS, rank_bins

LEVEL_ORDER = {"LOW": 0, "MEDIUM": 1, "HIGH": 2, "CRITICAL": 3}
WasteType = Literal["organic", "plastic", "paper", "glass", "mixed"]
Level = Literal["LOW", "MEDIUM", "HIGH", "CRITICAL"]


class BinNotFoundError(LookupError):
    def __init__(self, bin_id: str):
        super().__init__(f"Bin {bin_id} not found")
        self.bin_id = bin_id


def _compact(b: Bin, p: PriorityResult) -> dict:
    """Small, model-friendly record (no coordinates, no timestamps) to keep prompts short."""
    return {
        "bin_id": b.id, "name": b.name, "location": b.location, "waste_type": b.waste_type,
        "fill_level_percent": b.fill_level, "temperature_c": b.temperature,
        "days_since_collection": b.days_since_collection, "estimated_overflow_hours": b.estimated_overflow_time,
        "priority_score": p.priority_score, "priority_level": p.priority_level, "reasons": p.reasons,
    }


def bin_details(db: Session, bin_id: str) -> dict:
    b = bin_service.get_bin(db, bin_id)
    if b is None:
        raise BinNotFoundError(bin_id)
    from app.services.priority_engine import calculate_priority

    p = calculate_priority(b)
    return {
        **_compact(b, p),
        "latitude": b.latitude, "longitude": b.longitude,
        "last_collected_utc": b.last_collected.isoformat(), "sensor_status": b.status,
    }


def bins_by_priority(db: Session, limit: int = 10, waste_type: WasteType | None = None, min_level: Level | None = None) -> dict:
    ranked = rank_bins(bin_service.list_bins(db))
    matching = [
        (b, p) for b, p in ranked
        if (waste_type is None or b.waste_type == waste_type)
        and (min_level is None or LEVEL_ORDER[p.priority_level] >= LEVEL_ORDER[min_level])
    ]
    return {
        "total_bins_in_database": len(ranked), "matching_bins": len(matching), "returned": min(limit, len(matching)),
        "ordering": "highest priority first (deterministic priority engine)",
        "bins": [_compact(b, p) for b, p in matching[:limit]],
    }


def critical_bins(db: Session) -> dict:
    return bins_by_priority(db, limit=50, min_level="CRITICAL") | {"filter": "priority_level == CRITICAL"}


def collection_plan(db: Session, limit: int = 10) -> dict:
    plan = build_collection_plan(bin_service.list_bins(db))
    data = plan.model_dump(mode="json")
    data["collection_order"] = data["collection_order"][:limit]
    data["returned"] = len(data["collection_order"])
    data["note"] = "Priority order only; this is not a driving route."
    return data


def priority_explanation(db: Session, bin_id: str) -> dict:
    from app.services.priority_engine import calculate_priority

    b = bin_service.get_bin(db, bin_id)
    if b is None:
        raise BinNotFoundError(bin_id)
    p = calculate_priority(b)
    return {
        "bin_id": b.id, "priority_score": p.priority_score, "priority_level": p.priority_level, "reasons": p.reasons,
        "factor_breakdown": [f.model_dump() for f in p.breakdown],
        "maximum_points_per_factor": MAX_POINTS,
        "levels": "0-39 LOW, 40-69 MEDIUM, 70-84 HIGH, 85-100 CRITICAL",
        "inputs": {
            "fill_level_percent": b.fill_level, "waste_type": b.waste_type, "temperature_c": b.temperature,
            "days_since_collection": b.days_since_collection, "estimated_overflow_hours": b.estimated_overflow_time,
        },
    }
