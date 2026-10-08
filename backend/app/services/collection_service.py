from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import BinModel, CollectionRecordModel
from app.schemas.collection import CollectionCreate

# After a completed collection the bin is empty; overflow is no longer imminent.
POST_COLLECTION_OVERFLOW_HOURS = 72


class BinNotFound(Exception):
    def __init__(self, bin_id: str):
        super().__init__(f"Bin {bin_id} not found")
        self.bin_id = bin_id


def list_records(db: Session, bin_id: str | None = None, limit: int = 50) -> list[CollectionRecordModel]:
    stmt = select(CollectionRecordModel).order_by(CollectionRecordModel.collected_at.desc(), CollectionRecordModel.id.desc())
    if bin_id:
        stmt = stmt.where(CollectionRecordModel.bin_id == bin_id)
    return list(db.scalars(stmt.limit(limit)).all())


def create_record(db: Session, payload: CollectionCreate) -> CollectionRecordModel:
    """Insert a record and, for completed collections, reset the bin — in ONE transaction."""
    now = datetime.now(timezone.utc).replace(microsecond=0)  # DATETIME has 1s precision
    collected_at = (payload.collected_at or now).replace(microsecond=0)
    try:
        bin_ = db.scalar(select(BinModel).where(BinModel.id == payload.bin_id).with_for_update())
        if bin_ is None:
            raise BinNotFound(payload.bin_id)

        record = CollectionRecordModel(
            bin_id=bin_.id, collected_at=collected_at,
            collection_status=payload.collection_status, notes=payload.notes,
        )
        db.add(record)

        # Only a completed collection empties the bin, and a back-dated entry
        # must never move last_collected backwards.
        if payload.collection_status == "completed" and collected_at >= bin_.last_collected:
            bin_.last_collected = collected_at
            bin_.days_since_collection = max(0, (now - collected_at).days)
            bin_.fill_level = 0
            bin_.estimated_overflow_time = POST_COLLECTION_OVERFLOW_HOURS
            bin_.status = "normal"

        db.commit()
    except Exception:
        db.rollback()
        raise
    db.refresh(record)
    return record
