"""E2E route tests for the per-item tag endpoints."""


def _make_item(api, **overrides):
    body = {"name": "Milk", "location_id": "fridge"}
    body.update(overrides)
    return api.call("POST", "/items", body=body).body["item"]


# ---------------------------------------------------------------------------
# GET /items/<id>/tags
# ---------------------------------------------------------------------------

def test_get_item_tags_happy(api):
    item = _make_item(api, tags=["dairy", "fresh"])

    resp = api.call("GET", f"/items/{item['item_id']}/tags")

    assert resp.status_code == 200
    assert resp.body["tags"] == ["dairy", "fresh"]


def test_get_item_tags_item_not_found_returns_404(api):
    resp = api.call("GET", "/items/does-not-exist/tags")

    assert resp.status_code == 404
    assert resp.body["error"] == "Item not found"


# ---------------------------------------------------------------------------
# POST /items/<id>/tags
# ---------------------------------------------------------------------------

def test_add_item_tags_happy(api):
    item = _make_item(api, tags=["dairy"])

    resp = api.call("POST", f"/items/{item['item_id']}/tags",
                    body={"tags": ["Fresh", "COLD"]})

    assert resp.status_code == 200
    # Merged, lowercased, sorted.
    assert resp.body["tags"] == ["cold", "dairy", "fresh"]


def test_add_item_tags_missing_tags_returns_400(api):
    item = _make_item(api)

    resp = api.call("POST", f"/items/{item['item_id']}/tags", body={})

    assert resp.status_code == 400
    assert "tags" in resp.body["error"]


def test_add_item_tags_item_not_found_returns_404(api):
    resp = api.call("POST", "/items/does-not-exist/tags", body={"tags": ["x"]})

    assert resp.status_code == 404
    assert resp.body["error"] == "Item not found"


# ---------------------------------------------------------------------------
# DELETE /items/<id>/tags/<tag>
# ---------------------------------------------------------------------------

def test_remove_item_tag_happy(api):
    item = _make_item(api, tags=["dairy", "fresh"])

    resp = api.call("DELETE", f"/items/{item['item_id']}/tags/dairy")

    assert resp.status_code == 200
    assert resp.body["tags"] == ["fresh"]


def test_remove_item_tag_item_not_found_returns_404(api):
    resp = api.call("DELETE", "/items/does-not-exist/tags/dairy")

    assert resp.status_code == 404
    assert resp.body["error"] == "Item not found"
