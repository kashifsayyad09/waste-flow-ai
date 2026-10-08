# WasteFlow AI — backend

FastAPI service backed by AWS RDS MySQL. Run from this folder:
`uvicorn app.main:app --host 127.0.0.1 --port 8000` (add `--reload` for development; Nginx fronts it on port 80).
Tests: `pytest` (see the root README for unit vs integration).

- `app/database.py` — SQLAlchemy engine, session factory, `get_db` dependency, `check_database`
- `app/models/` — ORM models mirroring `schema.sql` (mapping only; tables are never created by the app)
- `app/api/routes.py` — REST routes
- `app/schemas/` — Pydantic request/response models
- `app/services/priority_engine.py` — the scoring rules (edit the tables at the top to tune)
- `app/services/collection_plan.py` — ordered plan built from priorities
- `app/services/bin_service.py` / `collection_service.py` — database access
- `.env` (not committed) — copy from `.env.example`; holds the only database credentials
