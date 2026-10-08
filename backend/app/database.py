"""SQLAlchemy engine, session factory and FastAPI session dependency.

The schema is owned by schema.sql. Nothing here creates or alters tables.
"""
import logging
from collections.abc import Iterator
from functools import lru_cache

from sqlalchemy import Engine, create_engine, text
from sqlalchemy.engine import URL
from sqlalchemy.orm import Session, sessionmaker

from app.config import Settings, get_settings

logger = logging.getLogger("wasteflow.database")


class DatabaseNotConfigured(RuntimeError):
    """DB_* values are missing in backend/.env."""


def build_url(settings: Settings) -> URL:
    # URL.create escapes special characters in the password safely.
    return URL.create(
        "mysql+pymysql",
        username=settings.db_user,
        password=settings.db_password.get_secret_value(),
        host=settings.db_host,
        port=settings.db_port,
        database=settings.db_name,
        query={"charset": "utf8mb4"},
    )


@lru_cache
def get_engine() -> Engine:
    settings = get_settings()
    if not settings.database_configured:
        raise DatabaseNotConfigured("Set DB_HOST, DB_USER, DB_PASSWORD in backend/.env")
    connect_args: dict = {
        "connect_timeout": 5,
        "read_timeout": 15,
        "write_timeout": 15,
        "init_command": "SET time_zone = '+00:00'",  # timestamps are UTC
    }
    if settings.db_ssl_ca:
        connect_args["ssl"] = {"ca": settings.db_ssl_ca}
    return create_engine(build_url(settings), pool_pre_ping=True, pool_recycle=280, connect_args=connect_args)


@lru_cache
def get_session_factory() -> sessionmaker[Session]:
    return sessionmaker(bind=get_engine(), autoflush=False, expire_on_commit=False)


def get_db() -> Iterator[Session]:
    """FastAPI dependency: one session per request."""
    db = get_session_factory()()
    try:
        yield db
    finally:
        db.close()


def check_database() -> bool:
    """True if a trivial query succeeds. Never raises, never leaks details."""
    try:
        with get_engine().connect() as conn:
            conn.execute(text("SELECT 1"))
        return True
    except Exception as exc:  # noqa: BLE001 - health check must not raise
        logger.warning("Database check failed: %s", type(exc).__name__)
        return False
