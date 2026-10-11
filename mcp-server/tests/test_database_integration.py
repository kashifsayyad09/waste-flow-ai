"""MCP tools against the REAL database (read-only). Skipped when MySQL is not reachable."""
import asyncio

import pytest
from mcp.client import Client

from app.database import check_database, get_session_factory
from app.services import bin_service
from app.services.priority_engine import rank_bins
from tests.conftest import call
from wasteflow_mcp.tools import build_server

pytestmark = pytest.mark.integration


@pytest.fixture(scope="module", autouse=True)
def need_db():
    if not check_database():
        pytest.skip("MySQL not configured/reachable")


def run(coro):
    return asyncio.run(coro)


def db_bins():
    with get_session_factory()() as db:
        return bin_service.list_bins(db)


def test_tools_return_database_rows_not_mock_data():
    bins = db_bins()
    ranked = rank_bins(bins)
    is_error, data = run(call(build_server(), "list_bins_by_priority", {"limit": 20}))
    assert not is_error and data["total_bins_in_database"] == len(bins)
    assert [b["bin_id"] for b in data["bins"]] == [b.id for b, _ in ranked][:20]
    assert [b["priority_score"] for b in data["bins"]] == [p.priority_score for _, p in ranked][:20]
    first = bins[0]
    is_error, detail = run(call(build_server(), "get_bin_details", {"bin_id": first.id}))
    assert not is_error and detail["location"] == first.location and detail["fill_level_percent"] == first.fill_level


def test_unknown_bin_in_real_database_is_an_error():
    is_error, text = run(call(build_server(), "get_bin_details", {"bin_id": "NO-SUCH-BIN"}))
    assert is_error and "not found" in text


def test_critical_bins_and_plan_agree_with_the_engine():
    ranked = rank_bins(db_bins())
    is_error, crit = run(call(build_server(), "get_critical_bins"))
    assert not is_error and [b["bin_id"] for b in crit["bins"]] == [b.id for b, p in ranked if p.priority_level == "CRITICAL"]
    is_error, plan = run(call(build_server(), "get_collection_plan", {"limit": 20}))
    assert [s["bin_id"] for s in plan["collection_order"]] == [b.id for b, _ in ranked][:20]


def test_the_server_cannot_write(tmp_path):
    before = [(b.id, b.fill_level) for b in db_bins()]

    async def go():
        async with Client(build_server()) as c:
            names = {t.name for t in (await c.list_tools()).tools}
            assert not any(n.startswith(("create", "update", "delete", "set", "record", "execute", "run_sql")) for n in names)
            await c.call_tool("get_critical_bins", {})

    run(go())
    assert [(b.id, b.fill_level) for b in db_bins()] == before
