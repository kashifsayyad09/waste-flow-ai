"""Integration tests against the REAL MySQL database from backend/.env.

Skipped automatically when the database is not reachable. Writes happen inside a
transaction that is rolled back, so the database is never modified or recreated.
Run only these:  pytest -m integration      Skip them:  pytest -m "not integration"
"""
import pytest
from sqlalchemy import inspect, text

from app.database import get_engine
from app.models import BinModel, CollectionRecordModel

pytestmark = pytest.mark.integration


def test_database_connection(db_session):
    assert db_session.execute(text("SELECT 1")).scalar() == 1
    assert db_session.execute(text("SELECT VERSION()")).scalar()


def test_models_match_schema_sql(db_session):
    inspector = inspect(get_engine())
    for model in (BinModel, CollectionRecordModel):
        db_cols = {c["name"] for c in inspector.get_columns(model.__tablename__)}
        assert db_cols == {c.name for c in model.__table__.columns}, model.__tablename__
        pk = inspector.get_pk_constraint(model.__tablename__)["constrained_columns"]
        assert pk == [c.name for c in model.__table__.primary_key.columns]
    fks = inspector.get_foreign_keys("collection_records")
    assert [(f["constrained_columns"], f["referred_table"], f["referred_columns"]) for f in fks] == [(["bin_id"], "bins", ["id"])]


def test_health_reports_connected(db_client, database_available):
    r = db_client.get("/health")
    assert r.status_code == 200 and r.json()["database"] == "connected"


def test_bins_come_from_database(db_client):
    bins = db_client.get("/api/v1/bins").json()
    assert bins
    first = bins[0]
    assert {"id", "name", "location", "latitude", "longitude", "fill_level", "waste_type", "last_collected",
            "days_since_collection", "temperature", "estimated_overflow_time", "status"} <= first.keys()
    assert first["last_collected"].endswith(("Z", "+00:00"))  # timezone-aware UTC


def test_bin_detail_and_missing_bin(db_client):
    bin_id = db_client.get("/api/v1/bins").json()[0]["id"]
    assert db_client.get(f"/api/v1/bins/{bin_id}").json()["id"] == bin_id
    r = db_client.get("/api/v1/bins/DOES-NOT-EXIST")
    assert r.status_code == 404 and "DOES-NOT-EXIST" in r.json()["detail"]


def test_priority_from_database_records(db_client):
    priorities = db_client.get("/api/v1/priorities").json()
    scores = [p["priority_score"] for p in priorities]
    assert scores == sorted(scores, reverse=True)
    assert all(0 <= s <= 100 for s in scores)
    assert all(p["priority_level"] in {"LOW", "MEDIUM", "HIGH", "CRITICAL"} for p in priorities)
    assert all(p["breakdown"] for p in priorities)


def test_collection_plan_from_database(db_client):
    plan = db_client.get("/api/v1/collection-plan").json()
    scores = [s["priority_score"] for s in plan["collection_order"]]
    assert plan["total_bins"] == len(scores) == len(db_client.get("/api/v1/bins").json())
    assert scores == sorted(scores, reverse=True)


def _fullest_bin(client):
    return max(client.get("/api/v1/bins").json(), key=lambda b: b["fill_level"])


def test_create_collection_updates_bin_in_one_transaction(db_client):
    before = _fullest_bin(db_client)
    score_before = next(p for p in db_client.get("/api/v1/priorities").json() if p["bin_id"] == before["id"])["priority_score"]

    r = db_client.post("/api/v1/collections", json={"bin_id": before["id"], "notes": "integration test"})
    assert r.status_code == 201
    record = r.json()
    assert record["bin_id"] == before["id"] and record["collection_status"] == "completed" and record["id"] > 0

    after = db_client.get(f"/api/v1/bins/{before['id']}").json()
    assert after["fill_level"] == 0 and after["days_since_collection"] == 0 and after["status"] == "normal"
    assert after["last_collected"] >= before["last_collected"]
    score_after = next(p for p in db_client.get("/api/v1/priorities").json() if p["bin_id"] == before["id"])["priority_score"]
    assert score_after < score_before

    listed = db_client.get("/api/v1/collections", params={"bin_id": before["id"]}).json()
    assert listed[0]["id"] == record["id"]


def test_skipped_collection_is_recorded_but_does_not_reset_bin(db_client):
    before = _fullest_bin(db_client)
    r = db_client.post("/api/v1/collections", json={"bin_id": before["id"], "collection_status": "skipped"})
    assert r.status_code == 201
    assert db_client.get(f"/api/v1/bins/{before['id']}").json()["fill_level"] == before["fill_level"]


def test_collection_for_unknown_bin_is_404_and_writes_nothing(db_client, db_session):
    count_before = db_session.query(CollectionRecordModel).count()
    r = db_client.post("/api/v1/collections", json={"bin_id": "DOES-NOT-EXIST"})
    assert r.status_code == 404
    assert db_session.query(CollectionRecordModel).count() == count_before
