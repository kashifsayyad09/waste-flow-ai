from datetime import datetime, timezone

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.schemas.bin import Bin
from app.services.collection_plan import build_collection_plan
from app.services.bin_service import list_bins
from app.services.priority_engine import calculate_priority, level_for

client = TestClient(app)


def make_bin(**overrides) -> Bin:
    data = dict(
        id="T-1", name="Test", location="Test", latitude=17.4, longitude=78.4, fill_level=50,
        waste_type="mixed", last_collected=datetime.now(timezone.utc), days_since_collection=1,
        temperature=28, estimated_overflow_time=20, status="normal",
    )
    return Bin(**{**data, **overrides})


HIGH_RISK = make_bin(fill_level=97, waste_type="organic", days_since_collection=3, temperature=37, estimated_overflow_time=2)
LOW_RISK = make_bin(fill_level=10, waste_type="glass", days_since_collection=0, temperature=22, estimated_overflow_time=72)


def test_health():
    r = client.get("/health")
    assert r.status_code == 200 and r.json()["status"] == "ok"


def test_list_bins():
    r = client.get("/api/v1/bins")
    assert r.status_code == 200
    assert 8 <= len(r.json()) <= 12


def test_get_bin_and_404():
    assert client.get("/api/v1/bins/BIN-001").json()["id"] == "BIN-001"
    assert client.get("/api/v1/bins/NOPE").status_code == 404


def test_high_risk_outranks_low_risk():
    assert calculate_priority(HIGH_RISK).priority_score > calculate_priority(LOW_RISK).priority_score


def test_score_bounds():
    for b in (HIGH_RISK, LOW_RISK, *list_bins()):
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


def test_priorities_endpoint_sorted():
    scores = [p["priority_score"] for p in client.get("/api/v1/priorities").json()]
    assert scores == sorted(scores, reverse=True) and scores


def test_collection_plan_sorted_and_ranked():
    plan = client.get("/api/v1/collection-plan").json()
    order = plan["collection_order"]
    assert plan["total_bins"] == len(order) == len(list_bins())
    assert [s["rank"] for s in order] == list(range(1, len(order) + 1))
    scores = [s["priority_score"] for s in order]
    assert scores == sorted(scores, reverse=True)
    assert all(s["reason"] for s in order)


def test_plan_puts_riskiest_first():
    plan = build_collection_plan([LOW_RISK, HIGH_RISK.model_copy(update={"id": "T-2"})])
    assert plan.collection_order[0].bin_id == "T-2"
