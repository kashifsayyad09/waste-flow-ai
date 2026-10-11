"""Database configuration, failure handling and log hygiene (no database needed)."""
import logging

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.exc import OperationalError

from app.config import Settings
from app.database import DatabaseNotConfigured, build_connect_args, build_url, get_db
from app.main import app
from app.services import bin_service

SECRET = "S3cr3t-pa$$word"


def make_settings(**kw) -> Settings:
    base = dict(_env_file=None, db_host="db.example.internal", db_user="svc", db_password=SECRET)
    return Settings(**{**base, **kw})


def test_timeouts_are_bounded_and_utc_is_forced():
    args = build_connect_args(make_settings())
    assert args["connect_timeout"] <= 10 and args["read_timeout"] <= 30 and args["write_timeout"] <= 30
    assert "+00:00" in args["init_command"]


def test_production_requires_tls_ca():
    with pytest.raises(DatabaseNotConfigured, match="DB_SSL_CA"):
        build_connect_args(make_settings(app_env="production"))
    # development without a CA stays allowed (local MySQL)
    assert "ssl" not in build_connect_args(make_settings(app_env="development"))


def test_ca_bundle_must_exist_and_enables_verification(tmp_path):
    with pytest.raises(DatabaseNotConfigured):
        build_connect_args(make_settings(db_ssl_ca=str(tmp_path / "missing.pem")))
    ca = tmp_path / "ca.pem"
    ca.write_text("dummy", encoding="utf-8")
    args = build_connect_args(make_settings(app_env="production", db_ssl_ca=str(ca)))
    assert args["ssl"] == {"ca": str(ca)}  # PyMySQL then verifies certificate + hostname by default


def test_pool_settings_have_sane_defaults():
    s = make_settings()
    assert (s.db_pool_size, s.db_max_overflow, s.db_pool_timeout) == (5, 5, 10)


def test_url_and_settings_never_expose_password():
    s = make_settings()
    assert SECRET not in repr(s) and SECRET not in str(s)
    assert SECRET not in build_url(s).render_as_string(hide_password=True)


def test_database_error_is_503_and_leaks_nothing_to_client_or_logs(monkeypatch, caplog):
    def boom(db):
        raise OperationalError("SELECT 1", {}, Exception(f"Access denied for user 'svc'@'10.0.0.5' (password: {SECRET})"))

    def no_db():
        yield object()

    app.dependency_overrides[get_db] = no_db
    monkeypatch.setattr(bin_service, "list_bins", boom)
    try:
        with caplog.at_level(logging.DEBUG):
            r = TestClient(app).get("/api/v1/bins")
    finally:
        app.dependency_overrides.clear()
    assert r.status_code == 503 and r.json() == {"detail": "Database unavailable"}
    for leaked in (SECRET, "svc", "10.0.0.5", "Access denied"):
        assert leaked not in r.text and leaked not in caplog.text
