# Phase 3: AI (Groq + MCP)

Two AI features, both server-side. The browser never talks to Groq or MCP and never sees a key.

1. **AI Collection Assistant**: answers questions about collection priorities, grounded in live database data.
2. **Waste photo classifier**: suggests a waste category for an uploaded photo.

The deterministic priority engine is unchanged and remains the only source of scores, levels and ranking. The AI explains; it does not decide. (A regression test pins the exact Phase 1-2 scores.)

## Architecture

```
Browser
  → React (AI assistant / Waste photo pages)
  → Nginx  (/api/v1/ai/* : 5 MB upload limit, 90 s timeout)
  → FastAPI (/api/v1/ai/chat, /api/v1/ai/classify-waste)
        ├─→ Groq API (text model for chat, vision model for photos)      [HTTPS, API key stays here]
        └─→ MCP client ──HTTP + bearer token──▶ MCP server (read-only tools)
                                                   → shared service layer → AWS RDS MySQL
                                                   → deterministic priority engine
```

### Assistant request flow

1. The browser POSTs `{ "message": "..." }` (1-500 characters) to `/api/v1/ai/chat`.
2. FastAPI connects to the MCP server, lists its tools, and gives them to the Groq text model as function tools.
3. The model decides which tool(s) to call. Each call goes to the MCP server, which validates the arguments, reads RDS through the existing data layer, and returns scores computed by the priority engine.
4. The model writes an explanation from those tool results (up to 4 tool rounds).
5. FastAPI **validates the answer before returning it**: any bin ID the model wrote that did not come from a tool result (or from the user's own question) causes the answer to be discarded and replaced by a plain list of the verified data.
6. The response lists `referenced_bins` with scores taken from the tool data, never from the model's text.

Response fields: `status` (`ok` or `unavailable`), `answer`, `referenced_bins[{bin_id, priority_score, priority_level}]`, `tools_used`, `data_status`, `warnings`, `model`.

| `data_status` | Meaning |
|---|---|
| `verified` | Tools were called, none failed, no unverified IDs |
| `partial` | A tool failed, or a bin ID in the written answer could not be verified |
| `no_data_used` | A general question; no bin data was involved |
| `unavailable` | The MCP service could not be reached; Groq was not called and nothing was guessed |

## Groq account and configuration

1. Create an account at https://console.groq.com and create an API key (API Keys page).
2. Choose model IDs **available to your account**. Model availability changes, so none are hardcoded.
   - `GROQ_TEXT_MODEL` must support **tool calling**.
   - `GROQ_VISION_MODEL` must accept **image input**.
3. Put the values in `backend/.env` (local) or `/etc/wasteflow/backend.env` (EC2). Never commit them.
4. Verify your account and models:

```
cd backend
python scripts/check_groq.py          # key accepted? do the configured model IDs exist on your account?
python scripts/check_groq.py --live   # also 2 tiny real requests: tool calling + image input (uses a few tokens)
```

If a feature's model is not configured, its endpoint returns `503` with code `ai_not_configured` and the UI says so. Nothing is faked.

### Environment variables (backend)

| Variable | Purpose |
|---|---|
| `GROQ_API_KEY` | Groq key (server only) |
| `GROQ_TEXT_MODEL` | Model for the assistant (must support tool calling) |
| `GROQ_VISION_MODEL` | Model for photo classification (must support images) |
| `MCP_SERVER_URL` | e.g. `http://127.0.0.1:8001/mcp` (MCP runs on the same host) |
| `MCP_API_TOKEN` | Bearer token shared with the MCP server (32+ random characters) |
| `GROQ_TIMEOUT_SECONDS`, `GROQ_MAX_RETRIES` | Optional (defaults 30 / 1) |
| `AI_RATE_LIMIT_PER_MINUTE` | Optional per-client limit on AI endpoints (default 20) |
| `GROQ_BASE_URL` | Leave empty. Only for tests against a local fake provider |

MCP server (`mcp-server/.env` locally, `/etc/wasteflow/mcp.env` on EC2): `MCP_API_TOKEN`, `MCP_HOST` (default `127.0.0.1`), `MCP_PORT` (default `8001`), optional `MCP_ALLOWED_HOSTS`, plus the `DB_*` variables. There is no frontend `.env`.

## MCP server (`mcp-server/`)

Built on the official MCP Python SDK **2.x** (`mcp>=2.3,<3`; `MCPServer` and the streamable-HTTP transport). It reuses the backend's service layer (`app.services.ai_data`, bins, priority engine, collection plan), so no logic is duplicated and there is no separate database or mock data.

**Tools (all read-only):**

| Tool | Arguments | Returns |
|---|---|---|
| `get_bin_details` | `bin_id` | Readings + deterministic score, level, reasons |
| `list_bins_by_priority` | `limit` 1-20, optional `waste_type`, `min_level` | Bins in engine order with fill, temperature, overflow hours |
| `get_critical_bins` | none | Bins whose level is CRITICAL |
| `get_collection_plan` | `limit` 1-20 | The engine's priority order with reasons (not a driving route) |
| `get_bin_priority_explanation` | `bin_id` | Score, level, reasons, per-factor points, inputs |

Safety properties: arguments are validated from their type annotations (ID pattern `^[A-Za-z0-9_-]{1,20}$`, ranges, enums); undeclared extra arguments are ignored by the SDK and cannot reach anything; no tool accepts SQL or any query text; missing bins and database outages return explicit errors, never invented data; unexpected exceptions return a generic message without details. The server has no write path (a test checks the source and the database state).

**Transport and authentication:** streamable HTTP, because the backend and MCP server are separate processes. Every request needs `Authorization: Bearer <MCP_API_TOKEN>` (constant-time comparison), the server refuses to start with a missing, placeholder or <32-character token, and Host-header (DNS-rebinding) protection is on. It listens on `127.0.0.1` by default. Stdio or in-memory servers cannot be reached by URL, so they are not used for the backend-to-MCP link.

**Run it:**

```
cd mcp-server
cp .env.example .env            # set MCP_API_TOKEN (python -c "import secrets; print(secrets.token_urlsafe(48))") and DB_*
python -m wasteflow_mcp         # run with the backend's virtualenv active; listens on 127.0.0.1:8001/mcp
```

## Waste photo classification

`POST /api/v1/ai/classify-waste` (multipart field `image`).

- Accepts JPEG, PNG or WebP only, up to **3 MB**; the real format is checked by decoding (a renamed file is rejected), plus minimum size and a decompression-bomb limit.
- The image is decoded, rotated, **stripped of all metadata (EXIF/GPS)**, resized to at most 1024 px and re-encoded as JPEG in memory, then sent to Groq as a data URL. **Nothing is written to disk or stored.** Note that the photo is processed by Groq, a third party.
- Categories: organic, plastic, paper/cardboard, metal, glass, electronic, hazardous, mixed, unknown. An unrecognised model answer becomes `unknown`; an unparseable answer is an error, not a fake result.
- `confidence` is always `null`: the provider returns no calibrated confidence, so none is shown.
- Handling guidance comes from a fixed, reviewed table, not from free-form model text. Hazardous and electronic results carry an extra warning that this is a visual guess, not a laboratory test.
- The result never changes a bin record.

## Running everything locally

```
# 1. MCP server        (terminal 1, from mcp-server/, backend venv active)
python -m wasteflow_mcp
# 2. FastAPI           (terminal 2, from backend/)
uvicorn app.main:app --host 127.0.0.1 --port 8000
# 3. Frontend          (terminal 3, from frontend/)
npm run dev
# 4. Nginx (optional locally; production uses deploy/nginx/)
```

Install dependencies once with `pip install -r backend/requirements.txt` (the MCP server shares it).

## Tests

```
cd backend    && pytest -m "not integration"   # unit tests: no database, no network, no paid calls
cd backend    && pytest                         # + integration tests when MySQL is configured (skipped otherwise)
cd mcp-server && pytest
cd frontend   && npm test
```

Groq is mocked in two ways: scripted fakes for unit tests, and a **local fake Groq HTTP server** (`backend/tests/helpers/fake_groq_server.py`) so the *real* Groq SDK runs end to end (auth header, model, tools, image payload, 429/401/400/500/timeout mapping) with no network. The integration suite additionally runs the real MCP server over HTTP against real MySQL. Live Groq checks are optional: `python scripts/check_groq.py --live`.

## Troubleshooting

| Symptom (`detail.code`) | Cause and fix |
|---|---|
| `ai_not_configured` (503) | Missing `GROQ_API_KEY`, model ID or MCP settings. Run `GET /api/v1/ai/status` and `scripts/check_groq.py` |
| `ai_rate_limited` (429) | Groq's limit (or ours, `AI_RATE_LIMIT_PER_MINUTE`). Wait for `Retry-After`; use a smaller model or a higher Groq tier |
| `ai_auth_failed` (502) | Groq rejected the key. Rotate it in the console and update `backend.env`, then restart |
| `ai_model_unsupported` (502) | The model ID doesn't exist for your account or lacks tool/vision support. Run `check_groq.py --live` |
| `ai_timeout` (504) / `ai_provider_unavailable` (502) | Provider slow or down. Retry; raise `GROQ_TIMEOUT_SECONDS` if needed |
| Assistant says it "couldn't verify" (`unavailable`) | MCP not running, wrong token, or wrong `MCP_SERVER_URL`. `systemctl status wasteflow-mcp`, compare tokens |
| `image_too_large` (413) | Over 3 MB. Resize the photo (Nginx itself allows up to 5 MB) |
| `unsupported_image_type` (415) / `invalid_image` (400) | Not a real JPEG/PNG/WebP |

## AWS networking

MCP runs **on the backend EC2** as a second systemd service, bound to loopback, so `MCP_SERVER_URL=http://127.0.0.1:8001/mcp` is correct and **port 8001 needs no security-group rule at all**. (If you ever move it to another instance, set `MCP_HOST` to its private address, allow TCP 8001 from the backend security group only, and set `MCP_ALLOWED_HOSTS`; the token is then sent over plain HTTP inside the VPC, so add TLS first.)

| Security group | New requirement for Phase 3 |
|---|---|
| Frontend | none |
| Backend | outbound TCP **443** to Groq (`api.groq.com`): needs a NAT gateway or a public subnet; the existing 8000-from-frontend rule is unchanged |
| RDS | none (the MCP service also connects from the backend EC2, so the existing rule covers it) |

Setup steps are in [`deploy/README.md`](../deploy/README.md).

## Security notes and known limitations

- The Groq key and MCP token exist only in root-owned env files on the backend EC2 (mode 0640). Give the MCP service a **SELECT-only** database user.
- Prompt injection: tool results are labelled as data in the system prompt, and the code-level grounding check blocks invented bin IDs regardless of what the model says.
- **Numbers inside the model's prose are not machine-verified** (only bin IDs are). The `referenced_bins` scores come straight from the engine; if wording and data ever disagree, trust the data panel. Answers are single-turn (no conversation memory).
- The per-client rate limiter is in-memory per process (the production service runs 2 workers), so the effective limit is roughly doubled; it is a cost guard, not a security boundary.
- There is no user authentication in the application (unchanged from earlier phases), so anyone who can reach the site can use the AI features and spend your Groq quota. Add authentication before exposing it publicly.
- Image classification is an estimate from one photo and can be wrong; it must not be used to identify hazardous materials.
- Not verified by me: live Groq calls (the sandbox I built this in cannot reach `api.groq.com`). Use `scripts/check_groq.py --live` on your machine.
