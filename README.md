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

## Phase 2

Bin data now lives in **AWS RDS for MySQL** instead of in-memory mock data. The priority engine, API contracts, Nginx and the React UI are unchanged.

- Database structure is defined **only** by [`schema.sql`](schema.sql), imported manually. No migrations, and the app never creates or alters tables.
- SQLAlchemy 2.x + PyMySQL for application-level access.
- New: `GET/POST /api/v1/collections` to record a collection (updates the bin in one transaction).
- `/health` now checks database connectivity.

Still excluded: AI, route optimization, Docker, CI/CD, authentication, and any AWS service other than RDS.

## Architecture

```
Browser
   ↓
React (Vite)
   ↓  /api/*
Nginx :80
   ↓
FastAPI :8000
   ↓  SQLAlchemy + PyMySQL (port 3306)
AWS RDS MySQL
   ↓
Deterministic Priority Engine
```

Only FastAPI talks to the database. The browser and React never see database credentials, and database traffic never goes through Nginx.

## AWS RDS Setup

You create the RDS instance manually in the AWS console (no Terraform/CloudFormation/CDK).

1. Open **AWS Console → RDS → Create database**.
2. Choose **Standard create** and engine **MySQL** (8.0 or 8.4). Not MariaDB or Aurora.
3. Template: **Free tier** (if offered) or **Dev/Test**.
4. **DB instance identifier:** e.g. `wasteflow-db`.
5. **Credentials:** pick a master username (e.g. `admin`) and a strong password. Store the password in a password manager, not in the repo.
6. Instance class: a small burstable one (e.g. `db.t3.micro` / `db.t4g.micro`). Storage: 20 GiB gp3 is plenty.
7. **Connectivity:**
   - VPC: default is fine for development.
   - **Public access:** *Yes* only for local development from your laptop; *No* for anything else (see Production below).
   - **VPC security group:** create new, e.g. `wasteflow-rds-sg`.
8. Expand **Additional configuration** and set **Initial database name** to `wasteflow`. This creates the database for you.
9. Click **Create database** and wait until the status is **Available**.
10. Open the instance → **Connectivity & security** and copy the **Endpoint** (like `wasteflow-db.xxxxxxxx.<region>.rds.amazonaws.com`).

### Network access (security group)

The machine running FastAPI must be able to reach the endpoint on **TCP 3306**.

**Local development (public access = Yes):**
1. EC2 → **Security Groups** → select `wasteflow-rds-sg` → **Inbound rules → Edit**.
2. Add rule: Type **MySQL/Aurora** (TCP 3306), Source **My IP**. AWS fills in your current public IP as `x.x.x.x/32`.
3. If your IP changes (home/office/VPN), update the rule. Remove it when you stop working.

**Never open 3306 to `0.0.0.0/0`.** Always use a specific IP or another security group as the source.

**Production (not implemented in Phase 2):** set Public access to **No**, run the backend inside the same VPC, and allow 3306 only from the backend's security group.

### Encrypted connection (recommended)

Download the AWS RDS CA bundle (`https://truststore.pki.rds.amazonaws.com/global/global-bundle.pem`), save it somewhere on your machine and set `DB_SSL_CA` to its path in `backend/.env`.

## Schema Setup

You need the `mysql` command-line client (or MySQL Workbench) on your machine.

If you set **Initial database name** to `wasteflow` in step 8, the database already exists. **Skip the CREATE DATABASE step.** Otherwise connect and run:

```sql
CREATE DATABASE wasteflow
CHARACTER SET utf8mb4
COLLATE utf8mb4_unicode_ci;
```

Then import the schema and demo data from the repo root (the command prompts for the password, so it never appears in your shell history):

```
mysql -h <RDS_ENDPOINT> -P 3306 -u <USERNAME> -p wasteflow < schema.sql
```

PowerShell does not support `<` redirection; use `cmd /c "mysql -h <RDS_ENDPOINT> -P 3306 -u <USERNAME> -p wasteflow < schema.sql"`.

`schema.sql` is safe to re-import: it uses `CREATE TABLE IF NOT EXISTS` and `INSERT IGNORE`, never drops anything, and does not overwrite existing rows. It creates two tables:

| Table | Purpose |
|---|---|
| `bins` | One row per bin: location, fill level, waste type, temperature, timing, status. Primary key `id`. |
| `collection_records` | Collection history. `bin_id` → `bins.id` (foreign key, `ON DELETE RESTRICT`). |

It also seeds 10 Hyderabad bins that produce 2 CRITICAL, 1 HIGH, 2 MEDIUM and 5 LOW priorities, so the dashboard has data immediately.

Optional but recommended: give the app its own least-privilege user instead of the master user.

```sql
CREATE USER 'wasteflow_app'@'%' IDENTIFIED BY '<STRONG_PASSWORD>';
GRANT SELECT, UPDATE ON wasteflow.bins TO 'wasteflow_app'@'%';
GRANT SELECT, INSERT ON wasteflow.collection_records TO 'wasteflow_app'@'%';
```

## Backend Configuration

Copy `backend/.env.example` to `backend/.env` and fill in your values. `backend/.env` is the **only** `.env` file in the project and is git-ignored.

```
APP_ENV=development
HOST=127.0.0.1
PORT=8000
CORS_ORIGINS=http://localhost,http://localhost:5173

DB_HOST=<RDS_ENDPOINT>
DB_PORT=3306
DB_NAME=wasteflow
DB_USER=<USERNAME>
DB_PASSWORD=<PASSWORD>
# DB_SSL_CA=/path/to/global-bundle.pem
```

While `DB_HOST`/`DB_USER` are still placeholders, the API answers `503 Database unavailable` and `/health` reports `unhealthy`.

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

(`--reload` is fine while developing.)

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

Nginx keeps proxying `/api/*` and `/health` to FastAPI and `/` to Vite, exactly as in Phase 1. Details: [`nginx/README.md`](nginx/README.md).

- App (via Nginx): http://localhost
- Health: http://localhost/health → `{"status":"ok","database":"connected",...}`
- Swagger (direct to FastAPI, local only): http://127.0.0.1:8000/docs

The frontend API path lives in one constant, `API_BASE_PATH` in `frontend/src/services/api.ts`. There is no frontend `.env`.

## API

| Endpoint | Returns |
|---|---|
| `GET /health` | `200` with `database: connected`, or `503` with `status: unhealthy` (never any connection details) |
| `GET /api/v1/bins` | all bins from MySQL |
| `GET /api/v1/bins/{bin_id}` | one bin (`404` if unknown) |
| `GET /api/v1/priorities` | score, level, reasons per bin, highest first |
| `GET /api/v1/collection-plan` | ranked collection order with reasons |
| `GET /api/v1/collections?bin_id=&limit=` | collection history, newest first |
| `POST /api/v1/collections` | record a collection (`201`) |

`POST /api/v1/collections` body: `{"bin_id": "BIN-004", "collected_at": "optional ISO time (UTC)", "collection_status": "completed|skipped|failed", "notes": "optional"}`.
In a single transaction it inserts the record and, for `completed`, sets the bin's `last_collected`, `days_since_collection = 0`, `fill_level = 0`, `estimated_overflow_time = 72` and `status = normal`. `skipped`/`failed` are recorded without touching the bin. A back-dated entry never moves `last_collected` backwards.

The collection plan is a priority order only; GPS route optimization is a later phase.

## Tests

```
cd backend
pytest                       # everything; integration tests skip if no database is reachable
pytest -m "not integration"  # unit tests only, no database needed
pytest -m integration        # database tests only
```

- `tests/unit/`: priority engine, API behaviour with sample data, health responses, URL/secret handling, and project rules (no `create_all`, no migration framework, no frontend `.env`).
- `tests/integration/`: run against the MySQL in `backend/.env`. Checks the connection, that the SQLAlchemy models match the real tables and foreign key, bins/priorities/plan from database rows, and collection creation. Every test runs inside a transaction that is rolled back, so your data is never changed and the database never needs recreating.

## Security

- Never commit the RDS password or any credential. `backend/.env` is in `.gitignore`; `backend/.env.example` holds placeholders only.
- Credentials exist only in `backend/.env`: not in the frontend, `schema.sql`, `nginx.conf`, this README, or source code.
- API error responses and `/health` never include usernames, passwords, hostnames or connection strings.
- Do not expose RDS to `0.0.0.0/0`.

## Design

The UI follows `design.md` (dark canvas, Jersey 10 + Roboto, orange accent, sharp corners, hard offset shadows).
