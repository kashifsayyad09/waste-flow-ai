"""Phase 3 must not change the deterministic engine: pin its exact outputs."""
from app.services.collection_plan import build_collection_plan
from app.services.priority_engine import MAX_POINTS, calculate_priority, rank_bins
from tests.sample_data import SAMPLE_BINS

# Scores established in Phases 1-2 and shown on the live dashboard.
EXPECTED = [("BIN-004", 97, "CRITICAL"), ("BIN-001", 86, "CRITICAL"), ("BIN-007", 76, "HIGH"), ("BIN-005", 53, "MEDIUM"),
            ("BIN-009", 47, "MEDIUM"), ("BIN-002", 32, "LOW"), ("BIN-010", 27, "LOW"), ("BIN-006", 19, "LOW"),
            ("BIN-003", 12, "LOW"), ("BIN-008", 6, "LOW")]


def test_scores_levels_and_order_are_unchanged():
    got = [(b.id, p.priority_score, p.priority_level) for b, p in rank_bins(SAMPLE_BINS)]
    assert got == EXPECTED


def test_collection_plan_order_is_unchanged():
    plan = build_collection_plan(SAMPLE_BINS)
    assert [(s.rank, s.bin_id, s.priority_score) for s in plan.collection_order] == [(i + 1, b, s) for i, (b, s, _) in enumerate(EXPECTED)]


def test_factor_weights_are_unchanged():
    assert MAX_POINTS == {"Fill level": 45, "Overflow window": 20, "Collection delay": 15, "Waste type": 10, "Temperature": 10}
    assert calculate_priority(SAMPLE_BINS[0]).reasons[0] == "92% full"


def test_engine_does_not_import_any_ai_code():
    import app.services.priority_engine as engine
    src = open(engine.__file__, encoding="utf-8").read()
    assert "groq" not in src.lower() and "mcp" not in src.lower() and "app.ai" not in src
