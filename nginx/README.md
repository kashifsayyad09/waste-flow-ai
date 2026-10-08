# Nginx reverse proxy (Phase 1)

Nginx is the single entry point on **port 80**. The browser only ever talks to `http://localhost`.

```
Browser → http://localhost
            │
          Nginx :80
            ├── /api/*   → FastAPI 127.0.0.1:8000
            ├── /health  → FastAPI 127.0.0.1:8000
            └── /        → Vite dev server 127.0.0.1:5173 (incl. HMR WebSocket)
```

FastAPI listens on `127.0.0.1` only, so it is not exposed to the frontend or the network directly.

## What the config does

- Preserves `Host`, `X-Real-IP`, `X-Forwarded-For`, `X-Forwarded-Proto`.
- Proxy timeouts: 60s connect/send/read for `/api/`; short ones for `/health`.
- If FastAPI is down, `/api/*` and `/health` return `502` with a JSON body instead of an HTML error page; the dashboard shows a readable message.
- Proxies `/` to Vite with WebSocket upgrade, so hot reload works through port 80.
- Keepalive connections to FastAPI.

## CORS

Nginx adds **no** CORS headers. The browser sees one origin (`http://localhost`), so requests are same-origin. FastAPI's `CORSMiddleware` (origins from `backend/.env` → `CORS_ORIGINS`) is the only place CORS is configured, so headers are never duplicated. Defaults: `http://localhost,http://localhost:5173`.

## Run it locally

Start the three pieces in separate terminals, from the repo root.

**1. FastAPI**
```
cd backend
venv\Scripts\activate          # Windows  (macOS/Linux: source venv/bin/activate)
uvicorn app.main:app --host 127.0.0.1 --port 8000
```

**2. Vite**
```
cd frontend
npm install
npm run dev
```

**3. Nginx** (uses this folder as its prefix, so logs stay in `nginx/logs/`)

macOS / Linux (port 80 needs root):
```
sudo nginx -p "$PWD/nginx/" -c nginx.conf
```
Windows (PowerShell, nginx.exe on PATH or in its own folder):
```
nginx -p "$PWD/nginx/" -c nginx.conf
```
Check the config first with `-t` added, reload with `-s reload`, stop with `-s stop` (same `-p` and `-c` flags).

Then open **http://localhost**.

| URL | What |
|---|---|
| http://localhost | App, via Nginx |
| http://localhost/health | FastAPI health, via Nginx |
| http://localhost/api/v1/bins | API, via Nginx |
| http://localhost/docs | Swagger UI *(not proxied by default)* |
| http://127.0.0.1:8000/docs | Swagger UI, direct to FastAPI |

`http://localhost:5173` also works: Vite forwards `/api` and `/health` to Nginx (`frontend/vite.config.ts`), never straight to FastAPI.

## Troubleshooting

- **"Address already in use" on port 80:** another web server (IIS, Apache, a system Nginx) holds it. Stop it, or temporarily change `listen 80;` and browse to that port.
- **Page loads but shows "Cannot reach the API":** FastAPI is not running on `127.0.0.1:8000`.
- **Blank page / 502 on `/`:** Vite is not running on port 5173.
- **Windows:** use forward slashes in `-p`, and keep the path free of spaces if possible.
