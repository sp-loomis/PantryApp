# Slack Integration — Design & Implementation Plan

**Status:** Proposed
**Scope:** Connecting a user's own Slack workspace to Homestead Manager and posting a
message to a channel on their behalf.
**Out of scope (separate doc):** the scheduled-report / notification system —
report config storage, section rules, schedule evaluation, and the delivery engine.
This document ends at the boundary `post_message(user_id, channel_id, blocks)`; the
report system is a *consumer* of that primitive and is designed elsewhere.

---

## 1. Goal

Multi-tenant, bring-your-own-Slack. Each customer connects **their own** Slack
workspace via OAuth; the app stores a per-workspace bot token and can post to
channels the user selects. No shared workspace, no shared token — one user's
connection can never post into another user's Slack.

This mirrors the app's existing posture: Cognito user pool, every resource scoped
by `user_id`.

---

## 2. Slack app model

One Slack app (owned by us), **distributed unlisted** — customers install it into
their own workspaces via an OAuth install link. Unlisted distribution needs **no
Slack review**; App Directory listing (later, optional) does.

### Bot scopes (minimum)

| Scope | Why |
|---|---|
| `chat:write` | post report messages |
| `channels:read` | list public channels for the channel picker |
| `groups:read` | list private channels the bot is a member of |
| `chat:write.public` | post to public channels without explicit invite (optional; convenience) |

Keep scopes minimal — every added scope is a bigger consent screen and a bigger
blast radius. Start with the four above; add only on demand.

### Redirect URL

Slack requires an HTTPS OAuth redirect URL registered on the app. It points at our
API Gateway: `https://<api-domain>/slack/oauth/callback`. One per environment
(dev/prod) — register both on the Slack app.

---

## 3. OAuth flow

Standard Slack OAuth v2 authorization-code flow.

```
User (web SPA)                Our API                     Slack
     |  click "Connect Slack"    |                           |
     |-------------------------->|  GET /slack/oauth/start    |
     |                           |  - mint signed `state`     |
     |                           |    (user_id + nonce + exp) |
     |   302 to slack authorize  |                           |
     |<--------------------------|                           |
     |----------------------------------------------------->|  consent screen
     |                           |                           |
     |   302 back with code+state|                           |
     |------------------------------------------------------|
     |                           |  GET /slack/oauth/callback |
     |                           |  - verify `state`          |
     |                           |  - oauth.v2.access(code)   |
     |                           |-------------------------->|
     |                           |  {access_token, team, ...} |
     |                           |<--------------------------|
     |                           |  - encrypt + store token   |
     |   302 to SPA success page |                           |
     |<--------------------------|                           |
```

### Endpoints (new)

| Endpoint | Purpose | Auth |
|---|---|---|
| `GET /slack/oauth/start` | Build Slack authorize URL, set signed `state`, 302 to Slack | Cognito (user must be logged in) |
| `GET /slack/oauth/callback` | Exchange `code` → token via `oauth.v2.access`, store encrypted, 302 to SPA | **not** Cognito-guarded (Slack calls it); trust comes from the signed `state` |

### The `state` parameter — CSRF + identity binding

The callback is hit by Slack's redirect, not an authenticated app request, so it
cannot read the Cognito identity directly. Bind identity into `state`:

- `state` = signed/encrypted blob of `{ user_id, nonce, expires_at }`.
- Signed with a server-side secret (reuse the KMS key or a dedicated HMAC secret).
- Verified on callback: signature valid, not expired, nonce single-use.
- **Never** trust a plaintext `user_id` in the query string.

`client_secret` for `oauth.v2.access` lives in Secrets Manager (single app-level
secret, not per-user) — see §5.

---

## 4. Token storage

Per-user, per-workspace bot token. Two candidate stores:

### Rejected: Secrets Manager per user
Clean (rotation, audit built in) but **$0.40 / secret / month** — scales linearly
with users (~$400/mo at 1,000 users). Overhead too high for the value.

### Chosen: encrypted attribute in DynamoDB + one KMS key
- One KMS customer-managed key, flat **~$1/month** regardless of user count.
- Token encrypted (KMS `Encrypt` on write / `Decrypt` on read, or envelope
  encryption) and stored as a **ciphertext** attribute on a connection row.
- Slack bot tokens are long-lived; rotation is not a hard requirement (re-install
  re-issues), so Secrets Manager's rotation edge isn't needed.

### New table: `*-table-slack-connections`

User-scoped, matches existing table conventions (`hash_key=user_id`).

```
user_id            (S)  hash key   — Cognito sub
connection_id      (S)  range key  — uuid (allows >1 workspace per user later)
team_id            (S)             — Slack workspace id
team_name          (S)             — display
bot_token_cipher   (B/S)           — KMS-encrypted bot token  ← never plaintext
bot_user_id        (S)
scopes             (S)
authed_user_id     (S)             — Slack user who installed
created_at         (S)
updated_at         (S)
```

Add the table module in `terraform/modules/main/main.tf` and its ARN to the Lambda
IAM policy resource list, same as the tasks table.

---

## 5. Secrets & IAM

| Secret / key | Scope | Store |
|---|---|---|
| Slack `client_id` | app-level | Terraform var / Lambda env (public-ish) |
| Slack `client_secret` | app-level | **Secrets Manager**, single secret |
| Slack `signing_secret` (if we later add interactivity) | app-level | Secrets Manager |
| `state` HMAC secret | app-level | Secrets Manager or reuse KMS |
| Per-user bot token | per user | DynamoDB ciphertext (this KMS key) |

New IAM grants for the Lambda role:
- `secretsmanager:GetSecretValue` on the app-level Slack secret ARN.
- `kms:Encrypt` / `kms:Decrypt` on the connections KMS key ARN.
- read/write on the new connections table + index.

---

## 6. Connections API + CLI

Per `.claude/CLAUDE.md`, every API endpoint gets a matching CLI command with
identical params and pretty-printed JSON output.

| API | CLI | Purpose |
|---|---|---|
| `GET /slack/oauth/start` | _(web-only; browser redirect)_ | begin OAuth — no CLI mirror (interactive redirect) |
| `GET /slack/oauth/callback` | _(web-only; Slack redirect)_ | finish OAuth — no CLI mirror |
| `GET /slack/connections` | `slack connections list` | list this user's connected workspaces (no token in response) |
| `GET /slack/connections/<id>/channels` | `slack channels list <id>` | `conversations.list` for the channel picker |
| `DELETE /slack/connections/<id>` | `slack disconnect <id>` | revoke (`auth.revoke`) + delete row |
| `POST /slack/connections/<id>/test` | `slack test <id>` | post a "connection works ✅" message to a chosen channel |

Notes:
- OAuth start/callback are **browser redirect** flows, not JSON APIs — they are the
  documented exception to the one-to-one CLI rule. Note this in the PR.
- **No endpoint ever returns the bot token.** Connection responses expose
  `team_name`, `connection_id`, `scopes`, timestamps only.
- `test` endpoint is the seam the report engine will build on — it exercises
  `post_message(user_id, channel_id, blocks)` end to end.

### Service layer

New `SlackService` in `backend/services.py`:

```python
class SlackService:
    def __init__(self, connections_table, kms_client, secrets):
        ...
    def build_authorize_url(self, user_id) -> str: ...
    def complete_oauth(self, code, state) -> dict: ...      # verify state, exchange, store
    def list_connections(self, user_id) -> list: ...        # token stripped
    def list_channels(self, user_id, connection_id) -> list: ...
    def disconnect(self, user_id, connection_id) -> bool: ...
    def post_message(self, user_id, connection_id, channel_id, blocks) -> dict: ...
    def _get_token(self, user_id, connection_id) -> str: ...  # KMS decrypt; internal only
```

`post_message` / `_get_token` are the primitives the report engine consumes.

---

## 7. Frontend (React SPA)

- **Settings → Integrations** page: "Connect Slack" button → `GET /slack/oauth/start`
  (full-page redirect, not fetch — it 302s to Slack).
- Post-callback success page reads connection list, shows connected workspace(s).
- **Channel picker** component: calls `GET .../channels`, dropdown by name.
- **Disconnect** button per connection.
- Local-dev note: Slack OAuth needs a public HTTPS callback. Local tier (Flask shim
  on `:8000`) can't receive Slack's redirect directly — plan for an `ngrok`/tunnel
  step or a **dev-stub connect** that inserts a fake connection row for UI work
  without real Slack. Document in `LOCAL_DEV.md`.

---

## 8. Terraform additions

1. `slack-connections` DynamoDB table module (+ Lambda IAM resource entry).
2. KMS customer-managed key + alias for token encryption (+ IAM Encrypt/Decrypt).
3. Secrets Manager secret for Slack `client_secret` / `signing_secret` / state HMAC
   (+ IAM GetSecretValue).
4. Lambda env vars: `SLACK_CLIENT_ID`, `SLACK_CONNECTIONS_TABLE_NAME`,
   `SLACK_KMS_KEY_ID`, `SLACK_SECRET_ARN`, `SLACK_REDIRECT_URI`.
5. API Gateway routes for the new endpoints; OAuth callback route must **not** sit
   behind the Cognito authorizer.

---

## 9. Security checklist

- [ ] Bot token stored only as KMS ciphertext; never logged, never in an API response.
- [ ] `state` signed, expiring, single-use nonce — CSRF + identity binding.
- [ ] `client_secret` in Secrets Manager, never in code/env-in-repo.
- [ ] Callback validates `state` before calling `oauth.v2.access`.
- [ ] `disconnect` calls Slack `auth.revoke`, then deletes the row (revoke even if
      row delete fails, and vice-versa — best effort both).
- [ ] Minimal scopes; document each.
- [ ] Rate-limit `oauth/start` per user (mint-storm protection).
- [ ] Redirect URI allowlisted on the Slack app; reject mismatches.

---

## 10. Cost

- Slack: **$0** (API and unlisted distribution are free; works on customers' free plans).
- Customer: **$0**.
- Us: token store **~$1–2/month flat** (one KMS key) + negligible Secrets Manager
  and API-Gateway/Lambda usage. Cost is engineering time, not infra.

---

## 11. Suggested breakdown (issues / PRs)

Small, reviewable PRs targeting `dev`:

1. **Terraform:** connections table + KMS key + Slack secret + IAM (no app code).
2. **SlackService core:** token encrypt/decrypt + connection storage + unit tests.
3. **OAuth endpoints:** `/slack/oauth/start` + `/callback` + `state` signing + e2e.
4. **Connections API + CLI:** list / channels / disconnect / test + CLI mirror + tests.
5. **Frontend:** Integrations settings page, channel picker, disconnect.
6. **Docs:** `LOCAL_DEV.md` tunnel/dev-stub note; README integrations section.

The report/notification system builds on top of #2–#4 and is planned separately.

---

## Affected code owners

None of the protected files (`.github/workflows/*`, `.claude/*`, `CODEOWNERS`,
`GEMINI.md`) are touched by this plan. Implementation PRs will touch
`backend/`, `frontend/`, and `terraform/` — no current CODEOWNERS entries cover
those, so no owner notification is required unless ownership rules change.
