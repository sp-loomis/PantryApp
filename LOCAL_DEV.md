# Local Development (Tier 1 — fully local)

Run the whole app on your machine with **no AWS account**: a local HTTP server
wraps the backend Lambda, DynamoDB Local stores data, and auth is a dev-bypass
stub (every request is the `dev-user`). See `frontend/react/DESIGN.md` for the
full 3-tier environment model.

## Prerequisites

- Python 3.10+ and the backend dev deps: `pip install -r backend/requirements-dev.txt`
- Node 18+ and frontend deps: `npm install` (from repo root — npm workspaces)
- A container runtime for DynamoDB Local (Docker Desktop, or `podman machine start`)

## Start the stack

```bash
# 1. DynamoDB Local on :8001
docker compose up -d

# 2. Create tables + sample data (idempotent)
python backend/seed_local.py

# 3. Backend HTTP shim on :8000  (Ctrl-C to stop)
python backend/local_server.py

# 4. Frontend dev server on :5173 (separate terminal)
npm run dev
```

Open http://localhost:5173. Vite runs with `host: true`, so the printed LAN URL
(e.g. `http://192.168.x.x:5173`) works from a phone on the same network for
real mobile testing.

## How it works

- `backend/local_server.py` — Flask app; turns each HTTP request into an API
  Gateway REST-proxy event (same shape the real Lambda gets), injects a fixed
  Cognito `sub` claim, and calls `app.lambda_handler`. **No backend app code
  changes** — it's the same handler that runs in AWS.
- `backend/local_schema.py` — table key schema/GSIs (mirrors prod + test schema).
- `backend/seed_local.py` — creates tables and seeds sample locations/items via
  the real service layer.
- Frontend reads two env vars (`frontend/react/web/.env.local`):
  `VITE_API_GATEWAY_URL=http://localhost:8000` and `VITE_AUTH_MODE=local`.

## Config knobs (backend shim)

| Env var | Default | Purpose |
|---|---|---|
| `DEV_USER_ID` | `dev-user` | The authenticated user's `sub` |
| `DEV_USER_GROUPS` | _(none)_ | Cognito groups, e.g. `Admin`, for admin-override testing |
| `PORT` | `8000` | Shim HTTP port |
| `DYNAMODB_ENDPOINT` | `http://localhost:8001` | DynamoDB Local URL |
| `CORS_ORIGIN` | `http://localhost:5173` | Allowed browser origin |

To act as a different user, set `DEV_USER_ID` before starting the shim (and seed
that user's data). To reset all data: `docker compose down -v` then re-seed.
