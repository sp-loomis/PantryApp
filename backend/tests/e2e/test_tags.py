"""E2E route tests for GET /tags (distinct tags across the inventory)."""


def _make_item(api, **overrides):
    body = {"name": "Milk", "location_id": "fridge"}
    body.update(overrides)
    return api.call("POST", "/items", body=body).body["item"]


def test_list_tags_empty(api):
    resp = api.call("GET", "/tags")

    assert resp.status_code == 200
    assert resp.body["tags"] == []


def test_list_tags_populated_sorted_and_lowercased(api):
    _make_item(api, name="Milk", tags=["Dairy", "Fresh"])
    _make_item(api, name="Bread", tags=["Bakery"])

    resp = api.call("GET", "/tags")

    assert resp.status_code == 200
    assert resp.body["tags"] == ["bakery", "dairy", "fresh"]
