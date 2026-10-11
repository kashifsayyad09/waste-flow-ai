import pytest

from app.services.priority_engine import calculate_priority, level_for
from tests.sample_data import SAMPLE_BINS, make_bin

HIGH_RISK = make_bin(fill_level=97, waste_type="organic", days_since_collection=3, temperature=37, estimated_overflow_time=2)
LOW_RISK = make_bin(fill_level=10, waste_type="glass", days_since_collection=0, temperature=22, estimated_overflow_time=72)


def test_high_risk_outranks_low_risk():
    assert calculate_priority(HIGH_RISK).priority_score > calculate_priority(LOW_RISK).priority_score


def test_score_bounds():
    for b in (HIGH_RISK, LOW_RISK, *SAMPLE_BINS):
        assert 0 <= calculate_priority(b).priority_score <= 100
    assert calculate_priority(HIGH_RISK.model_copy(update={"fill_level": 100})).priority_score == 100
    assert calculate_priority(LOW_RISK).priority_level == "LOW"


def test_deterministic():
    assert calculate_priority(HIGH_RISK) == calculate_priority(HIGH_RISK)


@pytest.mark.parametrize("score,level", [(0, "LOW"), (39, "LOW"), (40, "MEDIUM"), (69, "MEDIUM"),
                                         (70, "HIGH"), (84, "HIGH"), (85, "CRITICAL"), (100, "CRITICAL")])
def test_levels(score, level):
    assert level_for(score) == level


def test_reasons_explain_score():
    result = calculate_priority(HIGH_RISK)
    assert result.priority_level == "CRITICAL"
    assert "97% full" in result.reasons and "Organic waste" in result.reasons
    assert calculate_priority(LOW_RISK).reasons == []


def test_sample_data_covers_every_level():
    assert {calculate_priority(b).priority_level for b in SAMPLE_BINS} == {"LOW", "MEDIUM", "HIGH", "CRITICAL"}


# --- edge cases and invariants -----------------------------------------------------------------

@pytest.mark.parametrize("overrides", [
    dict(fill_level=0, estimated_overflow_time=0, days_since_collection=0, temperature=-10),
    dict(fill_level=100, estimated_overflow_time=0, days_since_collection=999, temperature=80, waste_type="organic"),
    dict(fill_level=100, estimated_overflow_time=10_000, days_since_collection=0, temperature=0),
    dict(fill_level=0, estimated_overflow_time=0, days_since_collection=0, temperature=45, waste_type="organic"),
])
def test_extreme_inputs_stay_in_range_and_have_a_level(overrides):
    r = calculate_priority(make_bin(**overrides))
    assert 0 <= r.priority_score <= 100
    assert r.priority_level in {"LOW", "MEDIUM", "HIGH", "CRITICAL"}
    assert sum(f.points for f in r.breakdown) <= 100.5 and all(f.points <= f.max_points for f in r.breakdown)


def _score(**kw) -> int:
    return calculate_priority(make_bin(**kw)).priority_score


def test_more_fill_never_lowers_priority():
    scores = [_score(fill_level=f) for f in range(0, 101)]
    assert scores == sorted(scores)


def test_shorter_overflow_window_never_lowers_priority():
    scores = [_score(estimated_overflow_time=h) for h in range(72, -1, -1)]
    assert scores == sorted(scores)


def test_more_days_never_lowers_priority_and_caps_at_three():
    scores = [_score(days_since_collection=d) for d in range(0, 8)]
    assert scores == sorted(scores) and scores[3] == scores[7]


def test_heat_hurts_organic_more_than_other_waste():
    hot_cold_organic = _score(waste_type="organic", temperature=37) - _score(waste_type="organic", temperature=20)
    hot_cold_glass = _score(waste_type="glass", temperature=37) - _score(waste_type="glass", temperature=20)
    assert hot_cold_organic > hot_cold_glass >= 0


def test_ties_are_broken_deterministically_by_bin_id():
    from app.services.collection_plan import build_collection_plan
    a, b = make_bin(id="B-2"), make_bin(id="B-1")
    assert [s.bin_id for s in build_collection_plan([a, b]).collection_order] == ["B-1", "B-2"]
