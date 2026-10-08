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
    db_ssl_ca: str = ""  # optional CA bundle path

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]

    @property
    def database_configured(self) -> bool:
        """False while the .env still holds empty values or <PLACEHOLDERS>."""
        values = (self.db_host, self.db_user)
        return all(v and not v.startswith("<") for v in values)


@lru_cache
def get_settings() -> Settings:
    return Settings()
