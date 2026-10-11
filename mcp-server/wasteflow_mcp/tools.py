"""MCP tool definitions. Every tool is read-only, takes validated arguments and delegates to
app.services.ai_data (database + deterministic priority engine). No SQL is accepted from callers."""
import logging
from contextlib import contextmanager
from typing import Annotated, Iterator

from mcp.server.mcpserver import MCPServer
from mcp.server.mcpserver.exceptions import ToolError
from pydantic import Field
from sqlalchemy.exc import SQLAlchemyError

import wasteflow_mcp  # noqa: F401  (ensures the backend package is importable)
from app.database import DatabaseNotConfigured, get_session_factory  # noqa: E402
from app.services import ai_data  # noqa: E402

logger = logging.getLogger("wasteflow.mcp")

BinId = Annotated[str, Field(pattern=r"^[A-Za-z0-9_-]{1,20}$", description="Bin identifier, e.g. BIN-004")]
Limit = Annotated[int, Field(ge=1, le=20, description="Maximum number of bins to return (1-20)")]

INSTRUCTIONS = (
    "Read-only access to WasteFlow bin data. Priority scores, levels and ordering come from the "
    "deterministic priority engine; never estimate them yourself."
)


@contextmanager
def open_session() -> Iterator:
    """Overridable in tests. Raises ToolError (safe message) when the database is unavailable."""
    try:
        db = get_session_factory()()
    except (DatabaseNotConfigured, SQLAlchemyError) as exc:
        logger.warning("Database unavailable: %s", type(exc).__name__)
        raise ToolError("Database unavailable: current data cannot be verified.") from None
    try:
        yield db
    finally:
        db.close()


def _guard(fn, *args, **kwargs):
    """Run a data call, converting expected failures into safe, informative tool errors."""
    try:
        with open_session() as db:
            return fn(db, *args, **kwargs)
    except ai_data.BinNotFoundError as exc:
        raise ToolError(f"Bin {exc.bin_id} was not found in the database.") from None
    except (DatabaseNotConfigured, SQLAlchemyError) as exc:
        logger.warning("Database error in tool: %s", type(exc).__name__)
        raise ToolError("Database unavailable: current data cannot be verified.") from None


def build_server() -> MCPServer:
    server = MCPServer("wasteflow-ai", instructions=INSTRUCTIONS)

    @server.tool(description="Get one bin's current readings and its deterministic priority score, level and reasons.")
    def get_bin_details(bin_id: BinId) -> dict:
        return _guard(ai_data.bin_details, bin_id)

    @server.tool(description=(
        "List bins ordered by the deterministic priority engine (highest first). Optionally filter by waste_type "
        "(organic, plastic, paper, glass, mixed) and/or min_level (LOW, MEDIUM, HIGH, CRITICAL). Includes fill level, "
        "temperature and estimated overflow hours."))
    def list_bins_by_priority(
        limit: Limit = 10,
        waste_type: ai_data.WasteType | None = None,
        min_level: ai_data.Level | None = None,
    ) -> dict:
        return _guard(ai_data.bins_by_priority, limit, waste_type, min_level)

    @server.tool(description="List bins whose deterministic priority level is CRITICAL right now.")
    def get_critical_bins() -> dict:
        return _guard(ai_data.critical_bins)

    @server.tool(description="Get the recommended collection order (priority-ranked, not a driving route), with a reason per bin.")
    def get_collection_plan(limit: Limit = 10) -> dict:
        return _guard(ai_data.collection_plan, limit)

    @server.tool(description="Explain one bin's priority: score, level, reasons, per-factor points and the inputs used.")
    def get_bin_priority_explanation(bin_id: BinId) -> dict:
        return _guard(ai_data.priority_explanation, bin_id)

    return server
