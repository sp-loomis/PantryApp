# Backend test suite

Tests are organized by kind. Shared machinery lives in `conftest.py` and is
available to every test via fixtures.

```
tests/
  conftest.py        # table schema, fixtures (dynamodb_tables, services, api), ApiClient
  unit/              # service-layer / module logic, called directly
    test_dimensions.py
    test_services.py
  e2e/               # whole HTTP request through app.lambda_handler
    test_locations.py
    test_items.py
    test_item_tags.py
    test_tags.py
    test_search.py
    test_aggregate.py
    test_auth.py      # cross-cutting auth contract
```

## Running

```bash
cd backend
pip install -r ../requirements-dev.txt   # first time only
pytest                                    # everything
pytest tests/e2e                          # just the E2E suite
pytest tests/e2e/test_items.py -q         # one file
```

`pytest.ini` sets `pythonpath = .`, so `import app` / `import services` resolve
no matter which directory a test lives in. DynamoDB is mocked with `moto`; no
AWS credentials or network are needed.

## Layers

- **`unit/`** — exercises a service or module in isolation (e.g. `ItemService`,
  `dimensions`). Use the `services` fixture, which yields
  `(item_service, location_service, dynamodb)` backed by mocked tables.
- **`e2e/`** — drives the real Lambda handler exactly as API Gateway would,
  asserting the HTTP contract: **status code** and **response body shape**. This
  is where routing, request parsing, and error-to-status mapping are verified.

## Writing an E2E test

Use the `api` fixture. It reloads `app` against freshly-created mocked tables and
returns an `ApiClient`:

```python
def test_create_item_happy(api):
    resp = api.call("POST", "/items", body={"name": "Milk", "location_id": "fridge"})
    assert resp.status_code == 201
    assert resp.body["item"]["name"] == "Milk"
```

`api.call(method, path, *, body=None, query=None, user="user-1", groups=None)`
builds an API Gateway REST event (Cognito claims included) and returns a
`Response(status_code, body)` where `body` is the parsed JSON.

**Seed through the API**, not the service layer, so each test traces a whole
request:

```python
item = api.call("POST", "/items", body={...}).body["item"]
```

## The standard: what every route must cover

For each route, add **one E2E test per distinct happy path** and **one per
distinct client-error (4xx) path**. Concretely:

- **Happy paths** — each meaningfully different success. e.g. `GET /items` needs
  cases for no filter, `location_id`, `tag`, and `name`; a create needs the
  minimal payload and the full payload.
- **4xx paths** — each predictable client error the route can return:
  - `400` — missing required field, malformed value (e.g. non-integer `days`),
    invalid domain input (bad/duplicate dimension, unknown unit).
  - `404` — resource not found (get/update/delete of a missing id).
  - `403` — authorization failures (see below).
- **Do not** test generic `5xx` failures. Those come from unexpected/internal
  errors (DynamoDB outages, bugs) and aren't a stable contract. If a client
  error is currently surfacing as `5xx`, that's a **bug** — fix the route to
  return the right 4xx and assert the fixed behavior (red → green).

Assert **both** the status code and the relevant body keys/values, not just one.

## Auth contract (applies to every route)

Every route resolves the caller via `auth.get_effective_user_id`, so the same
three behaviors hold everywhere and are covered in `test_auth.py`:

- **Unauthenticated** (no `sub` claim) → `401`. Simulate with `user=None`. The
  resolver raises `auth.AuthenticationError` (a `PermissionError` subclass), which
  every route maps to `401` — distinct from an authenticated-but-forbidden `403`.
- **Cross-user, non-admin** (`?user_id=` for someone else) → `403`.
- **Admin override** — a caller in the `Admin` Cognito group may act on another
  user's data via `?user_id=`. Simulate with `groups=["Admin"]` +
  `query={"user_id": "..."}`.

When adding a route, you don't need to re-test all three on it — the shared
resolver is already covered — but do add a case if the route handles auth in any
non-standard way.

## Adding a new route

Per the project's CLI/API alignment rule (`.claude/CLAUDE.md`), a new API
endpoint also needs a matching CLI command. On the test side:

1. Add the endpoint in `backend/app.py` (and service method in `services.py`).
2. Add an E2E file (or cases) covering every happy path and 4xx path above.
3. Add unit tests for any non-trivial new service logic.
4. If the route introduces genuinely new business logic, cover its edge cases at
   the unit layer and its contract at the E2E layer.
