from pathlib import Path

from pydantic import SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict

ENV_FILE = Path(__file__).resolve().parents[1] / ".env"
PLACEHOLDER_MARK = "<"


class MCPSettings(BaseSettings):
    """The MCP server's own settings (mcp-server/.env or the process environment).

    Database credentials are read by the backend's Settings (DB_HOST, DB_USER, ...) from the
    same process environment. Give this service a SELECT-only database user.
    """

    model_config = SettingsConfigDict(env_file=ENV_FILE, extra="ignore")

    mcp_api_token: SecretStr = SecretStr("")
    mcp_host: str = "127.0.0.1"
    mcp_port: int = 8001
    mcp_path: str = "/mcp"
    # Extra Host header values accepted (comma-separated), e.g. a private DNS name. localhost is always allowed.
    mcp_allowed_hosts: str = ""

    def token_problem(self) -> str | None:
        token = self.mcp_api_token.get_secret_value()
        if not token or token.startswith(PLACEHOLDER_MARK):
            return "MCP_API_TOKEN is not set"
        if len(token) < 32:
            return "MCP_API_TOKEN must be at least 32 characters (generate one with: python -c \"import secrets; print(secrets.token_urlsafe(48))\")"
        return None

    @property
    def allowed_hosts(self) -> list[str]:
        hosts = [f"127.0.0.1:{self.mcp_port}", f"localhost:{self.mcp_port}", f"[::1]:{self.mcp_port}"]
        for h in self.mcp_allowed_hosts.split(","):
            h = h.strip()
            if h:
                hosts.append(h if ":" in h else f"{h}:{self.mcp_port}")
        return hosts
