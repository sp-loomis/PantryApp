"""E2E tests for the cross-cutting auth contract.

Every route resolves the effective user via ``auth.get_effective_user_id``:
- an unauthenticated request (no ``sub`` claim) -> 403
- a non-admin requesting another user's ``user_id`` -> 403
- an Admin may act on another user's data via ``?user_id=`` -> allowed

These are exercised through representative routes; the behavior is shared by
every endpoint because they all call the same resolver.
"""


# ---------------------------------------------------------------------------
# Unauthenticated -> 403 (across a few route families)
# ---------------------------------------------------------------------------

def test_unauthenticated_get_items_returns_403(api):
    resp = api.call("GET", "/items", user=None)

    assert resp.status_code == 403
    assert "not authenticated" in resp.body["error"].lower()


def test_unauthenticated_create_location_returns_403(api):
    resp = api.call("POST", "/locations", body={"name": "Pantry"}, user=None)

    assert resp.status_code == 403


def test_unauthenticated_aggregate_returns_403(api):
    resp = api.call("GET", "/aggregate", user=None)

    assert resp.status_code == 403


# ---------------------------------------------------------------------------
# Cross-user access
# ---------------------------------------------------------------------------

def test_non_admin_cross_user_returns_403(api):
    # user-1 tries to read user-2's data.
    resp = api.call("GET", "/items", query={"user_id": "user-2"}, user="user-1")

    assert resp.status_code == 403
    assert "not authorized" in resp.body["error"].lower()


def test_admin_can_override_user_id(api):
    # Admin seeds an item for user-2, then reads it back via ?user_id=.
    admin = {"user": "admin-1", "groups": ["Admin"]}
    api.call("POST", "/items", body={"name": "Milk", "location_id": "fridge"},
             query={"user_id": "user-2"}, **admin)

    resp = api.call("GET", "/items", query={"user_id": "user-2"}, **admin)

    assert resp.status_code == 200
    assert [i["name"] for i in resp.body["items"]] == ["Milk"]


def test_user_can_pass_own_user_id(api):
    # Passing your own user_id is always allowed (not an admin action).
    api.call("POST", "/items", body={"name": "Milk", "location_id": "fridge"},
             user="user-1")

    resp = api.call("GET", "/items", query={"user_id": "user-1"}, user="user-1")

    assert resp.status_code == 200
    assert [i["name"] for i in resp.body["items"]] == ["Milk"]
