"""Data access seam: Phase 2 swaps the mock source for a database here."""
from app.data.mock_bins import MOCK_BINS
from app.schemas.bin import Bin


def list_bins() -> list[Bin]:
    return list(MOCK_BINS)


def get_bin(bin_id: str) -> Bin | None:
    return next((b for b in MOCK_BINS if b.id == bin_id), None)
