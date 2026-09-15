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

## Slack integration locally

Real Slack OAuth needs a public HTTPS callback (`/slack/oauth/callback`), which
the local shim on `:8000` cannot receive. So the local tier uses a **dev-stub
connect** instead of real OAuth: the shim sets `ENVIRONMENT=local`, which flips
`SlackService` into a no-network mode — passthrough token "encryption" (no KMS),
a stubbed app secret, and canned Slack API responses (fake channels, ok posts).

Create a fake connection (no real Slack) and exercise the whole flow:

```bash
# via the CLI (invokes the Lambda directly)
cd frontend/cli
python pantry_cli.py slack connections list        # []
# dev-stub has no CLI command; use the web app button or curl the shim:
curl -X POST http://localhost:8000/slack/connections/dev-stub \
  -H 'Content-Type: application/json' -d '{"team_name":"Local Dev Workspace"}'
python pantry_cli.py slack channels list <connection_id>   # canned: general, random
python pantry_cli.py slack test <connection_id> --channel C_LOCAL_GENERAL
python pantry_cli.py slack disconnect <connection_id>
```

In the web app: **Settings → Integrations** shows an **Add dev stub** button (only
in local auth mode) beside **Connect Slack**. Use it to create a fake workspace,
then try the channel picker, **Send test**, and **Disconnect**. `seed_local.py`
creates the `slack-connections` table alongside the others (idempotent).

To test **real** OAuth end to end you need a public HTTPS tunnel to `:8000`
(e.g. `ngrok http 8000`) registered as the redirect URL on a Slack app, plus the
`SLACK_CLIENT_ID` / `SLACK_REDIRECT_URI` env vars and the app secret — out of
scope for the everyday local loop.

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
