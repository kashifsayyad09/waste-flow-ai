"""Client for the separate MCP server (streamable HTTP + bearer token)."""
import json
import logging
from contextlib import AsyncExitStack, asynccontextmanager
from dataclasses import dataclass
from typing import Any, AsyncIterator, Protocol

import httpx2
from mcp.client import Client
from mcp.client.streamable_http import streamable_http_client

from app.config import Settings

logger = logging.getLogger("wasteflow.ai.mcp")


class MCPUnavailable(Exception):
    """The MCP server could not be reached, or rejected our credentials."""


@dataclass(frozen=True)
class ToolSpec:
    name: str
    description: str
    input_schema: dict


@dataclass(frozen=True)
class ToolResult:
    is_error: bool
    text: str

    def json(self) -> Any | None:
        try:
            return json.loads(self.text)
        except (ValueError, TypeError):
            return None


class ToolConnection(Protocol):
    async def list_tools(self) -> list[ToolSpec]: ...
    async def call_tool(self, name: str, arguments: dict) -> ToolResult: ...


class _Connection:
    def __init__(self, client: Client):
        self._client = client

    async def list_tools(self) -> list[ToolSpec]:
        result = await self._client.list_tools()
        return [ToolSpec(t.name, t.description or "", dict(t.input_schema)) for t in result.tools]

    async def call_tool(self, name: str, arguments: dict) -> ToolResult:
        r = await self._client.call_tool(name, arguments)
        text = "\n".join(getattr(c, "text", "") for c in r.content)
        return ToolResult(bool(r.is_error), text)


class MCPToolClient:
    def __init__(self, settings: Settings):
        self._settings = settings

    @property
    def configured(self) -> bool:
        return self._settings.mcp_ready

    @asynccontextmanager
    async def connect(self) -> AsyncIterator[ToolConnection]:
        s = self._settings
        if not s.mcp_ready:
            raise MCPUnavailable("MCP server is not configured")
        stack = AsyncExitStack()
        try:
            http = httpx2.AsyncClient(
                headers={"Authorization": f"Bearer {s.mcp_api_token.get_secret_value()}"},
                timeout=s.mcp_timeout_seconds,
            )
            await stack.enter_async_context(http)
            transport = streamable_http_client(s.mcp_server_url.strip(), http_client=http)
            client = await stack.enter_async_context(Client(transport, read_timeout_seconds=s.mcp_timeout_seconds))
        except BaseException as exc:  # includes ExceptionGroup raised for 401/refused connections
            await stack.aclose()
            if isinstance(exc, (KeyboardInterrupt, SystemExit)):
                raise
            logger.warning("MCP connection failed: %s", type(exc).__name__)
            raise MCPUnavailable("MCP server unreachable or rejected the request") from None
        try:
            yield _Connection(client)
        finally:
            try:
                await stack.aclose()
            except BaseException as exc:  # noqa: BLE001 - closing must never mask the real result
                logger.debug("MCP close error: %s", type(exc).__name__)
