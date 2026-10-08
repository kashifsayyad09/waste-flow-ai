"""Guards for the Phase 2 rules: schema.sql owns the schema; no migrations; no secrets."""
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
BACKEND = ROOT / "backend"


def _py_sources():
    return [p for p in (BACKEND / "app").rglob("*.py")]


def test_app_never_creates_tables():
    for p in _py_sources():
        text = p.read_text()
        assert "create_all" not in text, p
        assert not re.search(r"\b(CREATE|ALTER|DROP)\s+TABLE\b", text, re.I), p


def test_no_migration_framework():
    reqs = (BACKEND / "requirements.txt").read_text().lower()
    for name in ("alembic", "flask-migrate", "flyway", "liquibase"):
        assert name not in reqs
    assert not (BACKEND / "alembic").exists() and not (BACKEND / "migrations").exists()


def test_no_frontend_env_file():
    assert not list((ROOT / "frontend").glob(".env*"))


def test_env_is_gitignored_and_example_has_placeholders_only():
    assert "backend/.env" in (ROOT / ".gitignore").read_text()
    example = (BACKEND / ".env.example").read_text()
    assert "DB_PASSWORD=<RDS_PASSWORD>" in example and "DB_HOST=<RDS_ENDPOINT>" in example


def test_schema_sql_has_no_credentials_and_both_tables():
    sql = (ROOT / "schema.sql").read_text().lower()
    assert "create table if not exists bins" in sql and "create table if not exists collection_records" in sql
    assert "password" not in sql.replace("-- ", "") or "identified by" not in sql
    assert "engine=innodb" in sql and "utf8mb4" in sql
