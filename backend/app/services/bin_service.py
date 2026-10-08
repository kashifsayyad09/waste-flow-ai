"""Bin data access (AWS RDS MySQL via SQLAlchemy). Read-only here; writes live in collection_service."""
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import BinModel
from app.schemas.bin import Bin


def list_bins(db: Session) -> list[Bin]:
    rows = db.scalars(select(BinModel).order_by(BinModel.id)).all()
    return [Bin.model_validate(r) for r in rows]


def get_bin(db: Session, bin_id: str) -> Bin | None:
    row = db.get(BinModel, bin_id)
    return Bin.model_validate(row) if row else None
