import importlib.util
import json
import sys
from contextlib import contextmanager
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "mcp-server"))
sys.path.insert(0, str(ROOT / "backend"))

import wasteflow_mcp  # noqa: E402,F401
from mcp.client import Client  # noqa: E402
from wasteflow_mcp import tools as tools_module  # noqa: E402

# Reuse the backend's sample bins (same data the engine tests pin) without a package-name clash.
_spec = importlib.util.spec_from_file_location("backend_sample_data", ROOT / "backend" / "tests" / "sample_data.py")
sample_data = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(sample_data)


@pytest.fixture
def sample_bins():
    return sample_data.SAMPLE_BINS


@pytest.fixture
def server_with_sample_data(monkeypatch, sample_bins):
    """The real MCP server whose data layer returns sample bins instead of touching MySQL."""
    from app.services import bin_service

    @contextmanager
    def fake_session():
        yield object()

    monkeypatch.setattr(tools_module, "open_session", fake_session)
    monkeypatch.setattr(bin_service, "list_bins", lambda db: list(sample_bins))
    monkeypatch.setattr(bin_service, "get_bin", lambda db, bin_id: next((b for b in sample_bins if b.id == bin_id), None))
    return tools_module.build_server()


async def call(server, name, args=None):
    async with Client(server) as c:
        r = await c.call_tool(name, args or {})
    text = "\n".join(getattr(x, "text", "") for x in r.content)
    return r.is_error, (json.loads(text) if not r.is_error else text)
