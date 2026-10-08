# WasteFlow AI

*From waste data to the next collection decision.*

## Problem

Collection teams have more bins than trucks. Bins overflow when they are collected in the wrong order, and a plain "full / not full" dashboard does not say which bin to empty first or why.

## Solution

WasteFlow AI turns bin readings (fill level, waste type, temperature, time since collection, predicted overflow) into a 0–100 priority score, a priority level, and a ranked collection order, with the reasons for each.

## Core Feature

A **deterministic, explainable priority engine** (`backend/app/services/priority_engine.py`). The same bin always gets the same score. No LLM, no randomness.

| Factor | Max points | Behaviour |
|---|---|---|
| Fill level | 45 | Rises through bands: 0–50% low, 50–75% moderate, 75–90% high, 90–100% critical |
| Estimated overflow | 20 | ≤2h 20, ≤6h 16, ≤12h 9, ≤24h 4, otherwise 0 |
| Days since collection | 15 | 0 → 0, 1 → 6, 2 → 12, 3+ → 15 |
| Waste type | 10 | Organic 10, mixed 5, plastic/paper 3, glass 2 |
| Temperature | 10 | Heat adds more for organic waste (≥35°C: 10 vs 4; ≥30°C: 6 vs 2) |

Levels: 0–39 LOW · 40–69 MEDIUM · 70–84 HIGH · 85–100 CRITICAL.
Every result lists its `reasons` (strongest first) and a per-factor `breakdown`.

## Phase 1

React, Vite, TypeScript, FastAPI, Nginx (reverse proxy), mock/in-memory data, the priority engine, and REST APIs.

**MySQL, AI, AWS and production deployment are intentionally excluded from Phase 1.**

The collection plan is a priority order only. Real route optimization comes later.

## Architecture

```
          Browser
             |
             v
      React + Vite
             |
             | HTTP /api/*
             v
        Nginx :80
             |
             v
       FastAPI :8000
             |
             v
      Priority Engine
             |
             v
        Mock Bin Data
```

The browser only talks to `http://localhost` (Nginx). The frontend calls `/api/v1/...`; Nginx forwards it to FastAPI, which listens on `127.0.0.1:8000`. See [`nginx/README.md`](nginx/README.md).

## Local Setup

Run three processes, each in its own terminal.

**1. FastAPI**

```
cd backend
python -m venv venv
venv\Scripts\activate          # Windows
source venv/bin/activate       # macOS / Linux
pip install -r requirements.txt
uvicorn app.main:app --host 127.0.0.1 --port 8000
```

`backend/.env` is already set up for local use; to recreate it, copy `backend/.env.example`. It is the only `.env` file in the project.

**2. React / Vite**

```
cd frontend
npm install
npm run dev
```

**3. Nginx** (from the repo root; port 80 needs admin rights on macOS/Linux)

```
sudo nginx -p "$PWD/nginx/" -c nginx.conf       # macOS / Linux
nginx -p "$PWD/nginx/" -c nginx.conf            # Windows PowerShell
```

URLs:

- App (via Nginx): http://localhost
- Health (via Nginx): http://localhost/health
- Swagger (direct to FastAPI, local only): http://127.0.0.1:8000/docs

The frontend API path lives in one constant, `API_BASE_PATH` in `frontend/src/services/api.ts`. There is no frontend `.env`.

Tests: `cd backend && pytest`

## API

| Endpoint | Returns |
|---|---|
| `GET /health` | service status |
| `GET /api/v1/bins` | all bins |
| `GET /api/v1/bins/{bin_id}` | one bin (404 if unknown) |
| `GET /api/v1/priorities` | score, level, reasons per bin, highest first |
| `GET /api/v1/collection-plan` | ranked collection order with reasons |

## Design

The UI follows `design.md` (dark canvas, Jersey 10 + Roboto, orange accent, sharp corners, hard offset shadows).
