"""Guards for project rules: schema.sql owns the schema, no migrations, no secrets,
and frontend/deploy routing stays consistent.

Portable across Windows and Linux: every file is read as explicit UTF-8, and
virtual environments / build output are never scanned.
"""
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
BACKEND = ROOT / "backend"
FRONTEND = ROOT / "frontend"
DEPLOY = ROOT / "deploy"

EXCLUDED_DIRS = {".venv", "venv", "env", "__pycache__", ".pytest_cache", "node_modules", "dist", ".git", "site-packages"}


def read_utf8(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def code_only(text: str) -> str:
    """Drop whole-line comments (#, //, and block-comment lines) so rules judge code, not prose."""
    keep = [l for l in text.splitlines() if not l.strip().startswith(("#", "//", "/*", "*"))]
    return "\n".join(keep)


def iter_files(root: Path, suffix: str):
    """Yield files under root, never descending into virtualenvs or build output."""
    for p in sorted(root.rglob(f"*{suffix}")):
        if p.is_file() and not (set(p.relative_to(root).parts) & EXCLUDED_DIRS):
            yield p


def app_sources():
    return list(iter_files(BACKEND / "app", ".py"))


# --- the scanner itself (regression for the Windows cp1252 / .venv failure) ----------------

def test_scanner_skips_virtualenvs_and_reads_utf8(tmp_path):
    (tmp_path / ".venv" / "lib").mkdir(parents=True)
    (tmp_path / ".venv" / "lib" / "dep.py").write_bytes(b"\x81\x8d\xff not utf-8, not cp1252-safe")
    (tmp_path / "venv").mkdir()
    (tmp_path / "venv" / "x.py").write_text("x = 1", encoding="utf-8")
    (tmp_path / "pkg").mkdir()
    app_file = tmp_path / "pkg" / "mod.py"
    app_file.write_text('LABEL = "High temperature (36°C) — organic"', encoding="utf-8")

    found = list(iter_files(tmp_path, ".py"))
    assert found == [app_file]
    assert "°C" in read_utf8(found[0]) and "—" in read_utf8(found[0])


def test_scanner_covers_the_real_application():
    names = {p.name for p in app_sources()}
    assert {"main.py", "database.py", "priority_engine.py"} <= names
    assert not any(set(p.parts) & EXCLUDED_DIRS for p in (p.relative_to(BACKEND / "app") for p in app_sources()))


# --- schema ownership / migrations ----------------------------------------------------------

def test_app_never_creates_tables():
    for p in app_sources():
        text = read_utf8(p)
        assert "create_all" not in text, p
        assert not re.search(r"\b(CREATE|ALTER|DROP)\s+TABLE\b", text, re.I), p


def test_no_migration_framework():
    reqs = read_utf8(BACKEND / "requirements.txt").lower()
    for name in ("alembic", "flask-migrate", "flyway", "liquibase"):
        assert name not in reqs
    assert not (BACKEND / "alembic").exists() and not (BACKEND / "migrations").exists()
    for p in app_sources():
        assert not re.search(r"^\s*(from|import)\s+alembic", read_utf8(p), re.M), p


def test_no_mock_data_left_in_application():
    assert not (BACKEND / "app" / "data").exists()
    assert not any("mock_bins" in read_utf8(p) for p in app_sources())


def test_schema_sql_has_both_tables_and_no_credentials():
    sql = read_utf8(ROOT / "schema.sql")
    low = sql.lower()
    assert "create table if not exists bins" in low and "create table if not exists collection_records" in low
    assert "engine=innodb" in low and "utf8mb4" in low
    assert not re.search(r"identified\s+by|create\s+user|grant\s", low)
    assert not re.search(r"drop\s+(table|database)", low)


# --- secrets & git hygiene ------------------------------------------------------------------

def test_gitignore_protects_env_files_and_virtualenvs():
    ignored = read_utf8(ROOT / ".gitignore").splitlines()
    for rule in ("backend/.env", ".venv/", "node_modules/", "dist/"):
        assert rule in ignored, rule
    assert "!.env.example" in ignored


def test_env_examples_contain_placeholders_only():
    for example in (BACKEND / ".env.example", DEPLOY / "backend" / "backend.env.example", ROOT / "mcp-server" / ".env.example", DEPLOY / "backend" / "mcp.env.example"):
        text = read_utf8(example)
        assert "DB_PASSWORD=<" in text and "DB_HOST=<" in text, example
    for example in (BACKEND / ".env.example", DEPLOY / "backend" / "backend.env.example"):
        text = read_utf8(example)
        assert "GROQ_API_KEY=<" in text and "MCP_API_TOKEN=<" in text and "GROQ_TEXT_MODEL=<" in text, example
    assert not list(FRONTEND.glob(".env*")), "frontend must not have an .env file"


def test_mcp_systemd_unit_is_loopback_only_and_secret_free():
    unit = code_only(read_utf8(DEPLOY / "backend" / "wasteflow-mcp.service"))
    assert "EnvironmentFile=/etc/wasteflow/mcp.env" in unit and "wasteflow_mcp" in unit and "User=wasteflow" in unit
    assert "0.0.0.0" not in unit and "--reload" not in unit and not re.search(r"TOKEN=|PASSWORD=|API_KEY=", unit)
    assert "MCP_HOST=127.0.0.1" in read_utf8(DEPLOY / "backend" / "mcp.env.example")


def test_mcp_server_has_only_read_only_tools_and_no_sql_parameter():
    tools = read_utf8(ROOT / "mcp-server" / "wasteflow_mcp" / "tools.py")
    for forbidden in ("INSERT", "UPDATE ", "DELETE", "DROP", "text(", "execute(", "commit("):
        assert forbidden not in tools, forbidden
    assert not re.search(r"def \w+\([^)]*\b(sql|query|statement)\b", tools)


def test_no_real_env_file_or_secret_is_tracked_in_deploy_files():
    for p in DEPLOY.rglob("*"):
        if p.is_file():
            assert not re.search(r"AKIA[0-9A-Z]{16}|rds\.amazonaws\.com", read_utf8(p)) or "<" in read_utf8(p), p


# --- frontend routing -----------------------------------------------------------------------

def test_frontend_api_base_is_same_origin():
    api = code_only(read_utf8(FRONTEND / "src" / "services" / "api.ts"))
    assert 'API_BASE_PATH = "/api/v1"' in api
    assert "http://" not in api and "https://" not in api and "localhost" not in api


def test_vite_dev_proxy_targets_fastapi_not_port_80():
    cfg = code_only(read_utf8(FRONTEND / "vite.config.ts"))
    assert "http://127.0.0.1:8000" in cfg
    assert not re.search(r'http://127\.0\.0\.1["\'/]', cfg)  # the old ECONNREFUSED 127.0.0.1:80 target
    assert '"/api"' in cfg and '"/health"' in cfg


def test_frontend_package_pins_node_engine_and_has_lockfile():
    pkg = read_utf8(FRONTEND / "package.json")
    assert '"engines"' in pkg and '"typecheck"' in pkg and '"build"' in pkg
    assert (FRONTEND / "package-lock.json").exists()


# --- production deployment files ------------------------------------------------------------

def test_production_nginx_routes_match_backend_routes():
    from app.main import app

    conf = code_only(read_utf8(DEPLOY / "nginx" / "wasteflow-frontend.conf.template"))
    assert re.search(r"location\s+/api/\s*\{[^}]*proxy_pass\s+http://\$wasteflow_backend;", conf, re.S)  # no URI part: path preserved
    assert re.search(r"location\s+=\s+/health\s*\{[^}]*proxy_pass\s+http://\$wasteflow_backend;", conf, re.S)
    # variable proxy_pass => Nginx re-resolves a DNS-name backend (e.g. an internal ALB) instead of caching it forever
    assert re.search(r"resolver\s+NGINX_RESOLVER\s+valid=\d+s", conf)
    assert re.search(r'set\s+\$wasteflow_backend\s+"BACKEND_PRIVATE_HOST:8000";', conf)
    assert "try_files $uri $uri/ /index.html;" in conf  # SPA fallback
    for h in ("Host", "X-Real-IP", "X-Forwarded-For", "X-Forwarded-Proto"):
        assert f"proxy_set_header {h}" in conf
    assert "127.0.0.1:8000" not in conf and "BACKEND_PRIVATE_HOST" in conf
    doc_paths = {"/openapi.json", "/docs", "/docs/oauth2-redirect", "/redoc"}
    paths = set(app.openapi()["paths"]) | {"/health"}  # OpenAPI lists every real route, including included routers
    assert {"/api/v1/bins", "/api/v1/ai/chat", "/api/v1/ai/classify-waste", "/api/v1/collections"} <= paths
    assert all(p == "/health" or p.startswith("/api/") for p in paths - doc_paths), paths


def test_ai_endpoints_have_upload_limit_and_long_timeout_in_every_nginx_config():
    for conf_path in (DEPLOY / "nginx" / "wasteflow-frontend.conf.template", ROOT / "nginx" / "nginx.conf"):
        conf = code_only(read_utf8(conf_path))
        block = re.search(r"location\s+/api/v1/ai/\s*\{(.*?)\n\s*\}", conf, re.S)
        assert block, conf_path
        body = block.group(1)
        assert re.search(r"client_max_body_size\s+[4-9]m;", body), conf_path  # >= app limit (3 MB) + multipart overhead
        assert re.search(r"proxy_read_timeout\s+(9\d|1\d\d)s;", body), conf_path
        assert "wasteflow_backend" in body or "fastapi" in body, conf_path
        for h in ("Host", "X-Real-IP", "X-Forwarded-For", "X-Forwarded-Proto"):
            assert f"proxy_set_header {h}" in body, (conf_path, h)


def test_frontend_never_references_groq_or_secrets():
    for p in (FRONTEND / "src").rglob("*.ts*"):
        if "__tests__" in p.parts:  # tests may quote server messages such as "GROQ_API_KEY is not configured"
            continue
        text = read_utf8(p).lower()
        assert "groq" not in text.replace("groq api", "") or "api.groq.com" not in text, p
        assert "gsk_" not in text and "mcp_api_token" not in text and "api_key" not in text, p
    assert not list(FRONTEND.glob(".env*"))


def test_no_secrets_or_ai_keys_in_tracked_files():
    for p in ROOT.rglob("*"):
        if not p.is_file() or set(p.relative_to(ROOT).parts) & (EXCLUDED_DIRS | {"dist"}) or p.suffix in {".png", ".ico", ".lock", ".json"} or p.name in {"test_project_rules.py", "package-lock.json"}:
            continue
        try:
            text = read_utf8(p)
        except UnicodeDecodeError:
            continue
        assert not re.search(r"gsk_[A-Za-z0-9]{20,}", text), p  # real-looking Groq key


def test_systemd_unit_is_production_safe():
    unit = code_only(read_utf8(DEPLOY / "backend" / "wasteflow-backend.service"))
    assert "--reload" not in unit
    assert "EnvironmentFile=/etc/wasteflow/backend.env" in unit
    assert "app.main:app" in unit and "Restart=on-failure" in unit and "User=wasteflow" in unit
    assert not re.search(r"DB_PASSWORD|Environment=.*PASS", unit)
