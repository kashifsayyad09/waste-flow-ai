from datetime import datetime, timezone

from app.schemas.bin import Bin
from app.schemas.priority import CollectionPlan, CollectionStep
from app.services.priority_engine import rank_bins

_TOP_REASONS = 3


def build_collection_plan(bins: list[Bin]) -> CollectionPlan:
    """Priority-ordered collection list. No GPS routing in Phase 1."""
    steps = [
        CollectionStep(
            rank=rank,
            bin_id=b.id,
            bin_name=b.name,
            location=b.location,
            priority_score=p.priority_score,
            priority_level=p.priority_level,
            reason=", ".join(p.reasons[:_TOP_REASONS]) or "Low urgency across all factors",
        )
        for rank, (b, p) in enumerate(rank_bins(bins), start=1)
    ]
    return CollectionPlan(generated_at=datetime.now(timezone.utc), total_bins=len(steps), collection_order=steps)
