import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.database import check_database, get_db, get_engine
from app.main import app
from app.services import bin_service
from tests.sample_data import SAMPLE_BINS


@pytest.fixture
def unit_client(monkeypatch):
    """API client with NO database: the data layer is replaced by sample bins."""
    def _no_db():
        yield object()

    app.dependency_overrides[get_db] = _no_db
    monkeypatch.setattr(bin_service, "list_bins", lambda db: list(SAMPLE_BINS))
    monkeypatch.setattr(bin_service, "get_bin", lambda db, bin_id: next((b for b in SAMPLE_BINS if b.id == bin_id), None))
    yield TestClient(app)
    app.dependency_overrides.clear()


@pytest.fixture(scope="session")
def database_available() -> bool:
    return check_database()


@pytest.fixture
def db_session(database_available):
    """A real RDS/MySQL session inside an outer transaction that is ALWAYS rolled back.

    Commits made by the code under test only release a SAVEPOINT, so integration
    tests never leave data behind and never need the database recreated.
    """
    if not database_available:
        pytest.skip("MySQL is not configured/reachable (set DB_* in backend/.env)")
    connection = get_engine().connect()
    outer = connection.begin()
    session = Session(bind=connection, join_transaction_mode="create_savepoint", autoflush=False, expire_on_commit=False)
    yield session
    session.close()
    outer.rollback()
    connection.close()


@pytest.fixture
def db_client(db_session):
    def _use_test_session():
        yield db_session

    app.dependency_overrides[get_db] = _use_test_session
    yield TestClient(app)
    app.dependency_overrides.clear()


# --- Phase 3 (AI) fixtures -------------------------------------------------------------------------
from app.ai import rate_limit as _rate_limit  # noqa: E402
from app.ai.groq_service import GroqService  # noqa: E402
from app.api.ai_routes import get_groq_service, get_mcp_client  # noqa: E402
from app.config import Settings, get_settings  # noqa: E402


def make_ai_settings(**overrides) -> Settings:
    base = dict(
        _env_file=None, groq_api_key="gsk_test_key_not_real", groq_text_model="test-text-model", groq_vision_model="test-vision-model",
        mcp_server_url="http://127.0.0.1:1/mcp", mcp_api_token="t" * 40, groq_max_retries=0, groq_timeout_seconds=5,
    )
    return Settings(**{**base, **overrides})


@pytest.fixture(autouse=True)
def _reset_rate_limiter():
    _rate_limit.reset()
    yield
    _rate_limit.reset()


@pytest.fixture
def ai_client():
    """Factory: ai_client(settings=..., groq=..., mcp=...) -> TestClient with AI dependencies replaced."""
    def build(settings: Settings | None = None, groq=None, mcp=None) -> TestClient:
        app.dependency_overrides[get_settings] = lambda: settings or make_ai_settings()
        if groq is not None:
            app.dependency_overrides[get_groq_service] = lambda: groq
        if mcp is not None:
            app.dependency_overrides[get_mcp_client] = lambda: mcp
        return TestClient(app)

    yield build
    app.dependency_overrides.clear()
