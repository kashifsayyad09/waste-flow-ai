# WasteFlow AI — backend

FastAPI service. Run from this folder: `uvicorn app.main:app --host 127.0.0.1 --port 8000` (add `--reload` for development; Nginx fronts it on port 80). Tests: `pytest`.

- `app/api/routes.py` — REST routes
- `app/schemas/` — Pydantic response models
- `app/services/priority_engine.py` — the scoring rules (edit the tables at the top to tune)
- `app/services/collection_plan.py` — ordered plan built from priorities
- `app/services/bin_service.py` — data access seam (mock data now, database in Phase 2)
- `app/data/mock_bins.py` — in-memory demo bins
- `.env` (not committed) — copy from `.env.example`
