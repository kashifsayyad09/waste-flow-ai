"""Phase 1 in-memory bin data (Hyderabad demo locations).

Phase 2 replaces the source behind bin_service with a database.
"""
from datetime import datetime, timedelta, timezone

from app.schemas.bin import Bin

_NOW = datetime.now(timezone.utc).replace(minute=0, second=0, microsecond=0)

# (id, name, location, lat, lng, fill, waste, days, temp, overflow_h, status)
_ROWS = [
    ("BIN-001", "Charminar Market Bin", "Charminar Market", 17.3616, 78.4747, 92, "organic", 2, 36, 4, "critical"),
    ("BIN-002", "Hitec City Metro Bin", "Hitec City Metro Station", 17.4435, 78.3772, 61, "mixed", 1, 33, 14, "normal"),
    ("BIN-003", "Banjara Hills Bin", "Road No. 12, Banjara Hills", 17.4126, 78.4482, 38, "plastic", 0, 31, 40, "normal"),
    ("BIN-004", "Begum Bazaar Fish Market Bin", "Begum Bazaar", 17.3700, 78.4730, 97, "organic", 3, 37, 2, "critical"),
    ("BIN-005", "Secunderabad Station Bin", "Secunderabad Railway Station", 17.4344, 78.5013, 78, "mixed", 2, 34, 8, "warning"),
    ("BIN-006", "Financial District Bin", "Gachibowli Financial District", 17.4180, 78.3420, 45, "paper", 1, 30, 30, "normal"),
    ("BIN-007", "Madhapur Food Court Bin", "Madhapur Food Court", 17.4486, 78.3908, 88, "organic", 1, 35, 6, "warning"),
    ("BIN-008", "Jubilee Hills Check Post Bin", "Jubilee Hills Check Post", 17.4326, 78.4071, 22, "glass", 0, 29, 60, "normal"),
    ("BIN-009", "Kukatpally Housing Board Bin", "KPHB Colony", 17.4948, 78.3996, 69, "mixed", 2, 32, 11, "normal"),
    ("BIN-010", "Necklace Road Bin", "Necklace Road", 17.4156, 78.4619, 55, "plastic", 1, 31, 22, "normal"),
]

MOCK_BINS: list[Bin] = [
    Bin(
        id=i, name=n, location=loc, latitude=lat, longitude=lng, fill_level=fill,
        waste_type=w, last_collected=_NOW - timedelta(days=d), days_since_collection=d,
        temperature=t, estimated_overflow_time=o, status=s,
    )
    for i, n, loc, lat, lng, fill, w, d, t, o, s in _ROWS
]
