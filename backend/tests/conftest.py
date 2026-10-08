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
