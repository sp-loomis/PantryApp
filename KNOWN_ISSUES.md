# Known Issues / Backlog

Tracking for bugs and inconsistencies found during exploration. The backend-hardening
pass on `feat/fuzzy-name-search` resolved most of the original list (see **Resolved**);
what remains is either an intentional product decision or deferred architectural work.
Line numbers reflect the state at discovery and may drift.

## Deferred (out of scope for the backend-hardening pass)

- **Reverse tag-index writes are non-atomic with no rollback** — in `update_item`, the
  reverse-index rows are mutated *before* the item write; if the item write throws, the
  index and the item's denormalized `tags` diverge permanently. `TagService`'s per-tag
  `put_item`/`delete_item` loops and `delete_item`'s "remove index rows then delete item"
  sequence have the same partial-failure exposure. Fixing properly needs DynamoDB
  `TransactWriteItems` or a reconciliation path, and isn't meaningfully testable under
  `moto`. **Deferred.**
- **No pagination anywhere** — every `query`/index read in `services.py`
  (`list_all_items`, `list_locations`, `get_items_by_location`, `list_all_tags`, …)
  ignores `LastEvaluatedKey`, so results silently truncate at DynamoDB's 1 MB page. Name
  search and aggregate, which load a whole partition in memory, operate on partial data
  for large inventories. Cross-cutting; **deferred** to a dedicated effort.
- **Raw exception strings leak in `5xx` bodies** — every route's `except Exception`
  returns `{"error": str(e)}, 500`, exposing internal messages to clients. Security /
  hardening pass; **deferred.**
- **`/items/expiring` compares dates as strings server-side** — the `UseByDateIndex`
  query uses DynamoDB's `.lte(cutoff)`, a lexicographic string comparison. Date-only vs.
  full-timestamp `use_by_date` values sort by prefix. The `/search` in-memory date filter
  was fixed to parse datetimes (see Resolved), but a robust fix here requires normalizing
  the stored `use_by_date` format on write. **Deferred.**

## Open product decisions

- (none currently — the expiring-window scope and multi-tag OR/AND questions were
  resolved in this pass; see Resolved.)

## CLI (frontend — out of scope for the backend pass)

- **Cannot clear a text field with an empty string** — `item update --notes ""` and
  `location update --description ""` are gated by `if <opt>:` truthiness, so an empty
  string is silently dropped and the field can't be cleared. Use `is not None` sentinels
  (as the numeric options already do). To be addressed with the frontend work.

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
