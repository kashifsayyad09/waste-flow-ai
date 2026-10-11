"""MCP tools: discovery, validation, error handling, and consistency with the deterministic engine."""
import asyncio
from contextlib import contextmanager

import pytest
from mcp.client import Client
from mcp.server.mcpserver.exceptions import ToolError

from app.services.collection_plan import build_collection_plan
from app.services.priority_engine import calculate_priority, rank_bins
from tests.conftest import call
from wasteflow_mcp import tools as tools_module

EXPECTED_TOOLS = {"get_bin_details", "list_bins_by_priority", "get_critical_bins", "get_collection_plan", "get_bin_priority_explanation"}


def run(coro):
    return asyncio.run(coro)


def test_tool_discovery_exposes_exactly_the_five_read_only_tools(server_with_sample_data):
    async def go():
        async with Client(server_with_sample_data) as c:
            return (await c.list_tools()).tools

    tools = run(go())
    assert {t.name for t in tools} == EXPECTED_TOOLS
    for t in tools:
        params = set(t.input_schema.get("properties", {}))
        assert not params & {"sql", "query", "statement", "where", "table"}, t.name  # no free-form query surface
        assert t.description


def test_argument_constraints_are_published_in_the_schema(server_with_sample_data):
    async def go():
        async with Client(server_with_sample_data) as c:
            return {t.name: t.input_schema for t in (await c.list_tools()).tools}

    schemas = run(go())
    assert schemas["get_bin_details"]["properties"]["bin_id"]["pattern"]
    assert schemas["list_bins_by_priority"]["properties"]["limit"]["maximum"] == 20
    assert schemas["get_collection_plan"]["properties"]["limit"]["minimum"] == 1


@pytest.mark.parametrize("name,args", [
    ("get_bin_details", {}), ("get_bin_details", {"bin_id": ""}), ("get_bin_details", {"bin_id": "BIN-1'; DROP TABLE bins;--"}),
    ("get_bin_details", {"bin_id": "x" * 21}), ("get_bin_details", {"bin_id": 5}), ("get_bin_priority_explanation", {"bin_id": "../etc/passwd"}),
    ("list_bins_by_priority", {"limit": 0}), ("list_bins_by_priority", {"limit": 21}), ("list_bins_by_priority", {"limit": "ten"}),
    ("list_bins_by_priority", {"waste_type": "plutonium"}), ("list_bins_by_priority", {"min_level": "EXTREME"}),
    ("get_collection_plan", {"limit": -1}),
])
def test_invalid_arguments_are_rejected(server_with_sample_data, name, args):
    is_error, text = run(call(server_with_sample_data, name, args))
    assert is_error, (name, args, text)


def test_unknown_extra_arguments_are_ignored_and_change_nothing(server_with_sample_data):
    # MCP 2.x ignores undeclared arguments instead of rejecting them; they can never reach SQL or the engine.
    _, plain = run(call(server_with_sample_data, "get_critical_bins"))
    is_error, with_extra = run(call(server_with_sample_data, "get_critical_bins", {"sql": "DROP TABLE bins", "limit": 1}))
    assert not is_error and with_extra == plain


def test_get_bin_details_returns_engine_values(server_with_sample_data, sample_bins):
    is_error, data = run(call(server_with_sample_data, "get_bin_details", {"bin_id": "BIN-004"}))
    expected = calculate_priority(next(b for b in sample_bins if b.id == "BIN-004"))
    assert not is_error and data["bin_id"] == "BIN-004"
    assert data["priority_score"] == expected.priority_score == 97 and data["priority_level"] == "CRITICAL"
    assert data["reasons"] == expected.reasons and data["fill_level_percent"] == 97


def test_missing_bin_is_a_clear_error_not_fabricated_data(server_with_sample_data):
    for name in ("get_bin_details", "get_bin_priority_explanation"):
        is_error, text = run(call(server_with_sample_data, name, {"bin_id": "BIN-999"}))
        assert is_error and "BIN-999" in text and "not found" in text


def test_list_bins_by_priority_is_sorted_and_limited(server_with_sample_data, sample_bins):
    is_error, data = run(call(server_with_sample_data, "list_bins_by_priority", {"limit": 3}))
    ranked = rank_bins(sample_bins)
    assert not is_error and data["returned"] == 3 and data["total_bins_in_database"] == len(sample_bins)
    assert [b["bin_id"] for b in data["bins"]] == [b.id for b, _ in ranked[:3]]
    assert [b["priority_score"] for b in data["bins"]] == [p.priority_score for _, p in ranked[:3]]


def test_filters_combine_waste_type_and_minimum_level(server_with_sample_data, sample_bins):
    is_error, data = run(call(server_with_sample_data, "list_bins_by_priority", {"waste_type": "organic", "min_level": "HIGH"}))
    assert not is_error
    ids = [b["bin_id"] for b in data["bins"]]
    assert ids == ["BIN-004", "BIN-001", "BIN-007"] and all(b["waste_type"] == "organic" for b in data["bins"])
    assert all(b["priority_level"] in ("HIGH", "CRITICAL") for b in data["bins"])


def test_critical_bins_are_exactly_the_engines_critical_bins(server_with_sample_data, sample_bins):
    is_error, data = run(call(server_with_sample_data, "get_critical_bins"))
    expected = [b.id for b, p in rank_bins(sample_bins) if p.priority_level == "CRITICAL"]
    assert not is_error and [b["bin_id"] for b in data["bins"]] == expected == ["BIN-004", "BIN-001"]


def test_collection_plan_matches_the_engine_plan(server_with_sample_data, sample_bins):
    is_error, data = run(call(server_with_sample_data, "get_collection_plan", {"limit": 5}))
    expected = build_collection_plan(sample_bins).collection_order[:5]
    assert not is_error
    assert [(s["rank"], s["bin_id"], s["priority_score"]) for s in data["collection_order"]] == [(s.rank, s.bin_id, s.priority_score) for s in expected]
    assert "not a driving route" in data["note"]


def test_priority_explanation_includes_breakdown_and_inputs(server_with_sample_data):
    is_error, data = run(call(server_with_sample_data, "get_bin_priority_explanation", {"bin_id": "BIN-001"}))
    assert not is_error and data["priority_score"] == 86
    assert sum(f["points"] for f in data["factor_breakdown"]) == pytest.approx(86, abs=1)
    assert data["inputs"]["fill_level_percent"] == 92 and data["maximum_points_per_factor"]["Fill level"] == 45


def test_database_unavailable_is_reported_not_papered_over(monkeypatch):
    @contextmanager
    def broken():
        raise ToolError("Database unavailable: current data cannot be verified.")
        yield  # pragma: no cover

    monkeypatch.setattr(tools_module, "open_session", broken)
    for name, args in [("get_critical_bins", {}), ("get_bin_details", {"bin_id": "BIN-001"}), ("get_collection_plan", {})]:
        is_error, text = run(call(tools_module.build_server(), name, args))
        assert is_error and "Database unavailable" in text


def test_sqlalchemy_failures_become_safe_errors(monkeypatch):
    from sqlalchemy.exc import OperationalError
    from app.services import ai_data

    def boom(db, *a, **k):
        raise OperationalError("SELECT secret", {}, Exception("Access denied for user 'svc'@'10.1.2.3' password=hunter2"))

    @contextmanager
    def fake_session():
        yield object()

    monkeypatch.setattr(tools_module, "open_session", fake_session)
    monkeypatch.setattr(ai_data, "critical_bins", boom)
    is_error, text = run(call(tools_module.build_server(), "get_critical_bins"))
    assert is_error and "Database unavailable" in text
    for leaked in ("hunter2", "svc", "10.1.2.3", "SELECT secret"):
        assert leaked not in text


def test_unexpected_exceptions_do_not_leak_details(server_with_sample_data, monkeypatch):
    from app.services import ai_data
    monkeypatch.setattr(ai_data, "critical_bins", lambda db: (_ for _ in ()).throw(RuntimeError("internal-secret-xyz")))
    is_error, text = run(call(server_with_sample_data, "get_critical_bins"))
    assert is_error and "internal-secret-xyz" not in text
