from datetime import datetime

from sqlalchemy import BigInteger, Enum, ForeignKey, String, text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, UTCDateTime


class CollectionRecordModel(Base):
    """Mirrors table `collection_records` in schema.sql."""

    __tablename__ = "collection_records"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    bin_id: Mapped[str] = mapped_column(String(20), ForeignKey("bins.id", onupdate="CASCADE", ondelete="RESTRICT"))
    collected_at: Mapped[datetime] = mapped_column(UTCDateTime)
    collection_status: Mapped[str] = mapped_column(
        Enum("completed", "skipped", "failed", name="collection_status"), server_default="completed"
    )
    notes: Mapped[str | None] = mapped_column(String(500), nullable=True)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime, server_default=text("CURRENT_TIMESTAMP"))
