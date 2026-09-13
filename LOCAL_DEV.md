>
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

## Reports & notifications locally

The notifications engine runs fully in this tier — `seed_local.py` creates the
`reports` and `messages` tables and seeds sample reports (plus one generated
message each). In the web app: **Reports** (create/edit/run) and the toolbar
**bell** → **Messages** log all work against the local shim.

Table creation is idempotent per table, so on a volume seeded before this feature
existed, re-running `python backend/seed_local.py` just adds the two new tables
and sample reports (existing inventory/tasks are left untouched).

**The scheduled sweep has no local equivalent.** In AWS an EventBridge rule fires
the sweep on a cadence; locally there is no EventBridge, so reports never
auto-generate. Two ways to exercise generation locally:

- **Run one report now** — the `Run` action on the Reports page, or
  `POST /reports/<id>/run` (also the manual trigger in prod).
- **Simulate the periodic sweep** — invoke the sweep entry point directly against
  DynamoDB Local:

  ```bash
  cd backend
  python -c "
  import os, boto3
  os.environ.setdefault('AWS_DEFAULT_REGION','us-east-1')
  os.environ.setdefault('AWS_ACCESS_KEY_ID','local'); os.environ.setdefault('AWS_SECRET_ACCESS_KEY','local')
  os.environ.setdefault('AWS_ENDPOINT_URL_DYNAMODB','http://localhost:8001')
  os.environ['POWERTOOLS_TRACE_DISABLED']='1'
  from local_schema import TABLE_NAMES
  for k,v in TABLE_NAMES.items(): os.environ.setdefault(k,v)
  import app
  print(app.run_report_sweep())   # generates every report whose next_run is due
  "
  ```

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
