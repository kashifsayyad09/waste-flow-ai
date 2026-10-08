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
