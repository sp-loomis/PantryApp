# Notifications & Reports — Design & Implementation

**Status:** Implemented (in-app; Slack delivery deferred)
**Scope:** User-defined scheduled reports rendered into an in-app message log, with a
toolbar notifications dropdown. This is the report system that
[`slack-integration-plan.md`](./slack-integration-plan.md) explicitly leaves "designed
elsewhere" — Slack becomes an additional delivery sink on top of this engine.

---

## 1. Model

Two user-scoped DynamoDB tables (`user_id` HASH), mirroring existing table conventions.

### `*-table-reports` — report config
`report_id` (RANGE), `name`, `enabled`, `schedule`, `sections`, `next_run`, `last_run_at`.

- **schedule** (cron-ish): `{ frequency: daily|weekly|monthly, time_of_day: "HH:MM",
  weekday: 0-6 (weekly), day_of_month: 1-28 (monthly), tz: IANA }`.
- **sections**: ordered rule list `{ type, heading, config }`.
- **next_run**: UTC ISO timestamp; computed from `schedule` on write, advanced after each
  run. Backs the sweep's due filter.

### `*-table-messages` — generated log entries
`message_id` (RANGE), `report_id` (nullable), `title`, `sections` (rendered snapshot),
`created_at`, `read_at`.

- **UnreadIndex** GSI (`user_id` / `unread_sort`) is **sparse**: an unread message carries
  an `unread_sort` attribute (= `created_at`), so only unread messages appear in the index.
  Marking read REMOVEs the attribute (and the row) from the index and stamps `read_at`.
  This gives the toolbar an unread count/list without scanning the table. `unread_sort` is
  storage-only and stripped from API responses.

---

## 2. Section rule engine — `backend/report_sections.py`

A **section rule** (on the report) is `{ type, heading, config }`; a **rendered section**
(on the message) is `{ type, heading, content }`. Renderers are a registry keyed by type;
each resolves against live data **at generation time** and the result is snapshotted into
the message — the log shows what was true when the report ran, not a live re-query.

| type | config | content |
|---|---|---|
| `custom_message` | `{ text }` | `{ text }` |
| `task_query` | `{ status, tags[], name }` (→ `TaskService.list_tasks`) | `{ items, count }` |
| `item_query` | `{ location_id, tags[], name }` (→ `ItemService.search_items`) | `{ items, count }` |

`name` is a partial, fuzzy match (`search.match_name`, substring + difflib);
`tags` is an AND filter. `item_query` routes through the same `search_items` engine
as `POST /search`; `task_query` applies `match_name` over `list_tasks` results. A
legacy scalar `tag` in stored configs is still honored. The web form renders these
as a location dropdown, a tag multiselect, and a name field (no UUID entry).

Adding a type = write a renderer + register it. A future Slack block renderer consumes the
same rendered snapshot.

---

## 3. Scheduling — periodic sweep

A single EventBridge cron rule (`rate(1 hour)` by default, `var.report_sweep_schedule`)
invokes the API Lambda. `app.lambda_handler` detects the EventBridge event
(`source == "aws.events"`) and calls `run_report_sweep()`, which:

1. Scans reports for `enabled = true AND next_run <= now` (`ReportService.list_due_reports`).
2. Renders each via `ReportGenerator.generate` (best-effort; one failure doesn't abort the rest).
3. Advances each report's `next_run` / `last_run_at`.

One rule scales to any number of reports. If report counts grow, back the due-filter with a
GSI (constant partition keyed by `next_run`) instead of a Scan.

`POST /reports/<id>/run` runs a report immediately through the same generator — the manual
trigger and the local-dev path (local tier has no EventBridge).

---

## 4. Delivery seam (Slack later)

`ReportGenerator.generate` today writes the rendered message to the messages table (the
in-app sink). Slack integration (see the Slack plan's `post_message` boundary) adds a
second sink consuming the same rendered `Message` — additive, no change to the engine.

---

## 5. API

All Cognito-guarded, user-scoped, single-key JSON envelope. Route order registers specific
paths before parametric ones (`/reports/<id>/run` before `/reports/<id>`; `/messages/unread`
before `/messages/<id>`).

| Method + path | Purpose |
|---|---|
| `POST /reports` | create |
| `GET /reports` | list |
| `GET /reports/<id>` | get |
| `PUT /reports/<id>` | update (recomputes next_run on schedule change) |
| `DELETE /reports/<id>` | delete |
| `POST /reports/<id>/run` | generate now → returns message |
| `GET /messages` | log (newest first) |
| `GET /messages/unread` | unread list + `unread_count` (toolbar badge) |
| `GET /messages/<id>` | get |
| `POST /messages/<id>/read` | mark read |
| `POST /messages/<id>/unread` | mark unread |
| `DELETE /messages/<id>` | delete |

**CLI:** intentionally not mirrored — the CLI is a legacy dev tool and the one-to-one rule
in `.claude/CLAUDE.md` has been relaxed accordingly (see PR notification to @sp-loomis).

---

## 6. Frontend (React SPA)

- Shared services: `reportService.js`, `messageService.js` (+ exports in `shared/src/index.js`).
- `MessageLogPage` (`/messages`): renders each message's section snapshots; deep-links via
  `/messages#<message_id>` — scrolls to, highlights, and marks the target read.
- `ReportsPage` (`/reports`) + `ReportFormPage` (`/reports/new`, `/reports/:id/edit`): report
  CRUD with a schedule sub-form and an ordered section-rule builder.
- `NotificationsMenu`: toolbar bell + unread badge, wired into `AppShell`'s top bar; lists
  recent unread, each linking into the log.

---

## 7. Local dev / testing

- Tables mirrored in `backend/local_schema.py` and `backend/tests/conftest.py`; sample
  reports + messages seeded by `backend/seed_local.py`.
- Backend: pytest + moto — `test_schedules`, `test_report_sections`, `test_report_service`,
  `test_report_generator` (unit); `test_reports`, `test_messages` (e2e, incl. the sweep).
- Frontend: Vitest — `reportService.test.js`, `messageService.test.js`.
