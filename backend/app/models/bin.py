from datetime import datetime

from sqlalchemy import Enum, Integer, Numeric, String, text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, UTCDateTime


class BinModel(Base):
    """Mirrors table `bins` in schema.sql."""

    __tablename__ = "bins"

    id: Mapped[str] = mapped_column(String(20), primary_key=True)
    name: Mapped[str] = mapped_column(String(120))
    location: Mapped[str] = mapped_column(String(160))
    latitude: Mapped[float] = mapped_column(Numeric(9, 6, asdecimal=False))
    longitude: Mapped[float] = mapped_column(Numeric(9, 6, asdecimal=False))
    fill_level: Mapped[int] = mapped_column(Integer)
    waste_type: Mapped[str] = mapped_column(Enum("organic", "plastic", "paper", "glass", "mixed", name="waste_type"))
    last_collected: Mapped[datetime] = mapped_column(UTCDateTime)
    days_since_collection: Mapped[int] = mapped_column(Integer, server_default=text("0"))
    temperature: Mapped[float] = mapped_column(Numeric(4, 1, asdecimal=False))
    estimated_overflow_time: Mapped[int] = mapped_column(Integer)
    status: Mapped[str] = mapped_column(Enum("normal", "warning", "critical", name="bin_status"), server_default="normal")
    created_at: Mapped[datetime] = mapped_column(UTCDateTime, server_default=text("CURRENT_TIMESTAMP"))
    updated_at: Mapped[datetime] = mapped_column(UTCDateTime, server_default=text("CURRENT_TIMESTAMP"))
