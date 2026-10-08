"""Deterministic, explainable priority engine.

Score (0-100) = sum of five capped factor contributions:

    fill level            45
    estimated overflow    20
    days since collection 15
    waste type            10
    temperature           10

Every factor is a plain function of the bin, so tuning means editing the
tables below. No randomness, no external services.
"""
from app.schemas.bin import Bin
from app.schemas.priority import FactorScore, PriorityLevel, PriorityResult

MAX_POINTS = {"Fill level": 45, "Overflow window": 20, "Collection delay": 15, "Waste type": 10, "Temperature": 10}

# (fill_from, fill_to, points_at_from, points_at_to): linear within each band
FILL_BANDS = [(0, 50, 0, 9), (50, 75, 9, 22), (75, 90, 22, 36), (90, 100, 36, 45)]
DAYS_POINTS = {0: 0, 1: 6, 2: 12}  # 3+ days -> DAYS_MAX
DAYS_MAX = 15
OVERFLOW_BANDS = [(2, 20), (6, 16), (12, 9), (24, 4)]  # (hours <=, points); beyond -> 0
WASTE_POINTS = {"organic": 10, "mixed": 5, "plastic": 3, "paper": 3, "glass": 2}
# (min temp C, organic points, other points)
TEMP_BANDS = [(35, 10, 4), (30, 6, 2), (25, 3, 0)]

LEVELS: list[tuple[int, PriorityLevel]] = [(85, "CRITICAL"), (70, "HIGH"), (40, "MEDIUM"), (0, "LOW")]


def level_for(score: int) -> PriorityLevel:
    return next(level for floor, level in LEVELS if score >= floor)


def _fill_points(fill: float) -> float:
    fill = max(0.0, min(100.0, fill))
    for lo, hi, p_lo, p_hi in FILL_BANDS:
        if fill <= hi:
            return p_lo + (p_hi - p_lo) * (fill - lo) / (hi - lo)
    return float(FILL_BANDS[-1][3])


def _days_points(days: int) -> int:
    return DAYS_POINTS.get(days, DAYS_MAX)


def _overflow_points(hours: int) -> int:
    return next((p for limit, p in OVERFLOW_BANDS if hours <= limit), 0)


def _temperature_points(temp: float, organic: bool) -> int:
    for floor, organic_pts, other_pts in TEMP_BANDS:
        if temp >= floor:
            return organic_pts if organic else other_pts
    return 0


def calculate_priority(bin_: Bin) -> PriorityResult:
    organic = bin_.waste_type == "organic"
    # (factor, points, reason shown when the factor is a real driver, else None)
    factors: list[tuple[str, float, str | None]] = [
        ("Fill level", _fill_points(bin_.fill_level),
         f"{bin_.fill_level}% full" if bin_.fill_level >= 50 else None),
        ("Overflow window", _overflow_points(bin_.estimated_overflow_time),
         f"Estimated overflow in {bin_.estimated_overflow_time} hours" if bin_.estimated_overflow_time <= 12 else None),
        ("Collection delay", _days_points(bin_.days_since_collection),
         f"{bin_.days_since_collection} day{'s' if bin_.days_since_collection != 1 else ''} since last collection"
         if bin_.days_since_collection >= 1 else None),
        ("Waste type", WASTE_POINTS[bin_.waste_type], "Organic waste" if organic else None),
        ("Temperature", _temperature_points(bin_.temperature, organic),
         f"High temperature ({bin_.temperature:g}°C)" if bin_.temperature >= 30 else None),
    ]
    total = sum(points for _, points, _ in factors)
    score = max(0, min(100, round(total)))
    ranked = sorted(factors, key=lambda f: f[1], reverse=True)  # stable: strongest driver first
    return PriorityResult(
        bin_id=bin_.id,
        priority_score=score,
        priority_level=level_for(score),
        reasons=[reason for _, _, reason in ranked if reason],
        breakdown=[FactorScore(factor=n, points=round(p, 1), max_points=MAX_POINTS[n]) for n, p, _ in factors],
    )


def rank_bins(bins: list[Bin]) -> list[tuple[Bin, PriorityResult]]:
    """Highest priority first; ties broken by bin id for stable output."""
    pairs = [(b, calculate_priority(b)) for b in bins]
    return sorted(pairs, key=lambda p: (-p[1].priority_score, p[0].id))
