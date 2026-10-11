from functools import lru_cache
from pathlib import Path

from pydantic import SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict

ENV_FILE = Path(__file__).resolve().parent.parent / ".env"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=ENV_FILE, extra="ignore")

    app_env: str = "development"
    host: str = "127.0.0.1"
    port: int = 8000
    # Comma-separated list, e.g. "http://localhost,http://localhost:5173"
    cors_origins: str = "http://localhost"

    # AWS RDS MySQL (all from backend/.env, never hardcoded)
    db_host: str = ""
    db_port: int = 3306
    db_name: str = "wasteflow"
    db_user: str = ""
    db_password: SecretStr = SecretStr("")
    db_ssl_ca: str = ""  # path to the AWS RDS CA bundle; REQUIRED when APP_ENV=production
    db_pool_size: int = 5
    db_max_overflow: int = 5
    db_pool_timeout: int = 10  # seconds to wait for a free connection

    # --- Phase 3: AI (all optional; features report "not configured" when unset) ---
    groq_api_key: SecretStr = SecretStr("")
    groq_text_model: str = ""  # a text/tool-calling model available to YOUR Groq account
    groq_vision_model: str = ""  # a vision-capable model available to YOUR Groq account
    groq_base_url: str = ""  # leave empty for the real Groq API; tests point it at a local fake
    groq_timeout_seconds: float = 30.0
    groq_max_retries: int = 1
    mcp_server_url: str = ""  # e.g. http://127.0.0.1:8001/mcp (MCP runs on the backend EC2)
    mcp_api_token: SecretStr = SecretStr("")
    mcp_timeout_seconds: float = 20.0
    ai_max_tool_rounds: int = 4
    ai_rate_limit_per_minute: int = 20
    upload_max_bytes: int = 3 * 1024 * 1024  # Groq limits base64 images to 4 MB

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]

    @property
    def is_production(self) -> bool:
        return self.app_env.strip().lower() == "production"

    @staticmethod
    def _set(value: str) -> bool:
        """True for a real value; empty or <PLACEHOLDER> counts as unset."""
        value = value.strip()
        return bool(value) and not value.startswith("<")

    @property
    def groq_text_ready(self) -> bool:
        return self._set(self.groq_api_key.get_secret_value()) and self._set(self.groq_text_model)

    @property
    def groq_vision_ready(self) -> bool:
        return self._set(self.groq_api_key.get_secret_value()) and self._set(self.groq_vision_model)

    @property
    def mcp_ready(self) -> bool:
        return self._set(self.mcp_server_url) and self._set(self.mcp_api_token.get_secret_value())

    @property
    def database_configured(self) -> bool:
        """False while the .env still holds empty values or <PLACEHOLDERS>."""
        values = (self.db_host, self.db_user)
        return all(v and not v.startswith("<") for v in values)


@lru_cache
def get_settings() -> Settings:
    return Settings()
