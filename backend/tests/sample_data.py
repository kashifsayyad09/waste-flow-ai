"""In-test sample bins for UNIT tests only (the app itself reads from MySQL)."""
from datetime import datetime, timezone

from app.schemas.bin import Bin

_T0 = datetime(2026, 10, 1, tzinfo=timezone.utc)

# (id, fill, waste, days, temp, overflow_h)
_ROWS = [
    ("BIN-001", 92, "organic", 2, 36, 4), ("BIN-002", 61, "mixed", 1, 33, 14), ("BIN-003", 38, "plastic", 0, 31, 40),
    ("BIN-004", 97, "organic", 3, 37, 2), ("BIN-005", 78, "mixed", 2, 34, 8), ("BIN-006", 45, "paper", 1, 30, 30),
    ("BIN-007", 88, "organic", 1, 35, 6), ("BIN-008", 22, "glass", 0, 29, 60), ("BIN-009", 69, "mixed", 2, 32, 11),
    ("BIN-010", 55, "plastic", 1, 31, 22),
]


def make_bin(**overrides) -> Bin:
    data = dict(
        id="T-1", name="Test", location="Test", latitude=17.4, longitude=78.4, fill_level=50,
        waste_type="mixed", last_collected=_T0, days_since_collection=1,
        temperature=28, estimated_overflow_time=20, status="normal",
    )
    return Bin(**{**data, **overrides})


SAMPLE_BINS = [
    make_bin(id=i, name=i, location=i, fill_level=f, waste_type=w, days_since_collection=d, temperature=t, estimated_overflow_time=o)
    for i, f, w, d, t, o in _ROWS
]
