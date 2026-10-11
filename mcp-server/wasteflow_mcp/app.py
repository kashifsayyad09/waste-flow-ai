from mcp.server.transport_security import TransportSecuritySettings
from starlette.types import ASGIApp

from wasteflow_mcp.auth import BearerTokenMiddleware
from wasteflow_mcp.config import MCPSettings
from wasteflow_mcp.tools import build_server


def create_app(settings: MCPSettings | None = None) -> ASGIApp:
    """Streamable-HTTP MCP app: bearer auth on every request + Host/Origin (DNS-rebinding) checks."""
    settings = settings or MCPSettings()
    problem = settings.token_problem()
    if problem:
        raise RuntimeError(problem)
    server = build_server()
    http_app = server.streamable_http_app(
        streamable_http_path=settings.mcp_path,
        host=settings.mcp_host,
        transport_security=TransportSecuritySettings(
            enable_dns_rebinding_protection=True, allowed_hosts=settings.allowed_hosts, allowed_origins=[],
        ),
    )
    return BearerTokenMiddleware(http_app, settings.mcp_api_token.get_secret_value())
