# Known Issues / Backlog

Tracking for bugs and inconsistencies found during exploration. The backend-hardening
pass on `feat/fuzzy-name-search` resolved most of the original list (see **Resolved**);
what remains is either an intentional product decision or deferred architectural work.
Line numbers reflect the state at discovery and may drift.

## Deferred (out of scope for the backend-hardening pass)

- (All of the originally-deferred items below were resolved in the data-model
  redesign — see **Resolved (data-model redesign)**.)

## Open product decisions

- (none currently — the expiring-window scope and multi-tag OR/AND questions were
  resolved in this pass; see Resolved.)

## CLI (retired)

- The `frontend/cli` tool was removed in the data-model redesign (the React SPA is the
  sole client), so its backlog items (e.g. the empty-string field-clear bug) no longer
  apply.

## Resolved (data-model redesign)

- **Reverse tag-index removed** — the `item_tags` table + `TagService` are gone; tags are
  the denormalized array on each item, and items-by-tag / list-tags derive from the
  partition. This eliminates the non-atomic dual-write hazard entirely (no index to
  diverge). (Terraform drops the prod table in the analytics/infra phase.)
- **Pagination added** — `services._paginate` follows `LastEvaluatedKey`; every list/query
  path uses it, so large partitions no longer truncate at 1 MB.
- **5xx bodies no longer leak internals** — routes return a generic
  `{"error": "Internal server error"}` via `app._server_error()`; the real exception is
  logged, not returned.
- **`use_by_date` normalized to date-only on write** — `create`/`update` store
  `YYYY-MM-DD` and `/items/expiring` compares a date-only cutoff, so the lexicographic
  `UseByDateIndex` range is correct.

## Resolved (on `feat/fuzzy-name-search`)

- **Unauthenticated requests now return `401`** (were `403`) — `auth.AuthenticationError`
  distinguishes "no identity" (401) from cross-user "forbidden" (403).
- **`/items/expiring` rejects negative `days`** with `400`. Already-expired items are
  intentionally still included (product decision: they're the most urgent in a pantry).
- **`GET /items` and `GET /aggregate` now stack `location_id` + `tag` (AND)** instead of
  silently dropping the second filter — consistent with `/search`.
- **Multi-tag `/search` uses AND** (item must carry every requested tag), consistent with
  multi-word name matching.
- **Malformed dimension `value` returns `400`** (was a `500` from `Decimal()`).
- **`/search` validates input** — non-list `tags` and malformed ISO dates return `400`;
  the route now has a `ValueError` handler; the date-range filter compares parsed,
  timezone-normalized datetimes instead of raw strings.
- **`create`/`update` item reject a non-list `tags`** with `400`.
- **`delete_item` / `delete_location` no longer mask real failures as `404`** — the
  not-found check happens before the delete, and genuine failures now surface as `500`.
- **`update_item` returns `None` (→ `404`) on an empty `Attributes`** result instead of a
  valid-looking empty stub.
- **`_deserialize_item` always includes `dimensions`** (defaults to `[]`), so every item
  response has a stable shape.
