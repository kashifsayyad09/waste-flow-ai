"""API tests with the data layer replaced by sample bins — no database needed."""
import app.main as main_module
from app.config import Settings
from app.database import DatabaseNotConfigured, build_url, check_database, get_engine
from app.services.collection_plan import build_collection_plan
from tests.sample_data import SAMPLE_BINS, make_bin


def test_health_connected(unit_client, monkeypatch):
    monkeypatch.setattr(main_module, "check_database", lambda: True)
    r = unit_client.get("/health")
    assert r.status_code == 200
    assert r.json()["status"] == "ok" and r.json()["database"] == "connected"


def test_health_unhealthy_leaks_nothing(unit_client, monkeypatch):
    monkeypatch.setattr(main_module, "check_database", lambda: False)
    r = unit_client.get("/health")
    assert r.status_code == 503
    assert r.json() == {"status": "unhealthy", "database": "unreachable"}


def test_bins_and_detail(unit_client):
    assert len(unit_client.get("/api/v1/bins").json()) == len(SAMPLE_BINS)
    assert unit_client.get("/api/v1/bins/BIN-001").json()["id"] == "BIN-001"


def test_missing_bin_is_404(unit_client):
    r = unit_client.get("/api/v1/bins/NOPE")
    assert r.status_code == 404 and "NOPE" in r.json()["detail"]


def test_priorities_sorted_and_in_range(unit_client):
    scores = [p["priority_score"] for p in unit_client.get("/api/v1/priorities").json()]
    assert scores == sorted(scores, reverse=True)
    assert all(0 <= s <= 100 for s in scores)


def test_collection_plan_sorted_and_ranked(unit_client):
    plan = unit_client.get("/api/v1/collection-plan").json()
    order = plan["collection_order"]
    assert plan["total_bins"] == len(order) == len(SAMPLE_BINS)
    assert [s["rank"] for s in order] == list(range(1, len(order) + 1))
    scores = [s["priority_score"] for s in order]
    assert scores == sorted(scores, reverse=True) and all(s["reason"] for s in order)


def test_plan_puts_riskiest_first():
    risky = make_bin(id="T-2", fill_level=97, waste_type="organic", days_since_collection=3, temperature=37, estimated_overflow_time=2)
    quiet = make_bin(id="T-1", fill_level=10, waste_type="glass", days_since_collection=0, temperature=22, estimated_overflow_time=72)
    assert build_collection_plan([quiet, risky]).collection_order[0].bin_id == "T-2"


def test_collection_payload_validation(unit_client):
    assert unit_client.post("/api/v1/collections", json={"bin_id": "BIN-001", "collection_status": "exploded"}).status_code == 422
    assert unit_client.post("/api/v1/collections", json={}).status_code == 422


def test_database_url_never_exposes_password():
    s = Settings(_env_file=None, db_host="h.example", db_user="u", db_password="p@ss/w:rd")
    url = build_url(s)
    assert url.password == "p@ss/w:rd"                      # escaped correctly by SQLAlchemy
    assert "p@ss" not in url.render_as_string(hide_password=True)
    assert "p@ss" not in repr(s)                            # SecretStr hides it in repr


def test_unconfigured_database_is_reported_not_crashed(monkeypatch):
    monkeypatch.setattr("app.database.get_settings", lambda: Settings(_env_file=None, db_host="<RDS_ENDPOINT>", db_user=""))
    get_engine.cache_clear()
    try:
        assert check_database() is False
        try:
            get_engine()
            raise AssertionError("expected DatabaseNotConfigured")
        except DatabaseNotConfigured:
            pass
    finally:
        get_engine.cache_clear()
