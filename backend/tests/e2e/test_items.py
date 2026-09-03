"""E2E route tests for the item endpoints (CRUD, listing, expiring)."""


def _make_item(api, **overrides):
    """Seed one item through the API and return its response body."""
    body = {"name": "Milk", "location_id": "fridge"}
    body.update(overrides)
    return api.call("POST", "/items", body=body)


# ---------------------------------------------------------------------------
# POST /items
# ---------------------------------------------------------------------------

def test_create_item_happy(api):
    resp = _make_item(api)

    assert resp.status_code == 201
    item = resp.body["item"]
    assert item["name"] == "Milk"
    assert item["location_id"] == "fridge"
    assert item["tags"] == []
    assert item["use_by_date"] is None
    # dimensions key is always present, even when the item has none.
    assert item["dimensions"] == []
    assert "item_id" in item


def test_create_item_full_payload(api):
    resp = _make_item(
        api,
        dimensions=[{"dimension_type": "count", "value": 12, "unit": "units"}],
        use_by_date="2030-01-01T00:00:00+00:00",
        tags=["Dairy", "Fresh"],
        notes="two cartons",
    )

    assert resp.status_code == 201
    item = resp.body["item"]
    # Dimension value comes back as a plain float, tags lowercased.
    assert isinstance(item["dimensions"][0]["value"], float)
    assert item["dimensions"][0]["value"] == 12.0
    assert item["tags"] == ["dairy", "fresh"]
    assert item["use_by_date"] == "2030-01-01T00:00:00+00:00"
    assert item["notes"] == "two cartons"


def test_create_item_missing_name_returns_400(api):
    resp = api.call("POST", "/items", body={"location_id": "fridge"})

    assert resp.status_code == 400
    assert "name" in resp.body["error"]


def test_create_item_missing_both_fields_returns_400(api):
    resp = api.call("POST", "/items", body={})

    assert resp.status_code == 400
    assert "name" in resp.body["error"]
    assert "location_id" in resp.body["error"]


def test_create_item_invalid_dimension_unit_returns_400(api):
    resp = _make_item(
        api, dimensions=[{"dimension_type": "weight", "value": 1, "unit": "furlong"}]
    )

    assert resp.status_code == 400
    assert "dimension" in resp.body["error"].lower()


def test_create_item_duplicate_dimension_type_returns_400(api):
    resp = _make_item(
        api,
        dimensions=[
            {"dimension_type": "weight", "value": 1, "unit": "kg"},
            {"dimension_type": "weight", "value": 2, "unit": "lb"},
        ],
    )

    assert resp.status_code == 400
    assert "duplicate" in resp.body["error"].lower()


def test_create_item_non_numeric_dimension_value_returns_400(api):
    # A non-numeric value must be a clean 400, not a 500 from Decimal() blowing up.
    resp = _make_item(
        api, dimensions=[{"dimension_type": "weight", "value": "heavy", "unit": "kg"}]
    )

    assert resp.status_code == 400
    assert "dimension value" in resp.body["error"].lower()


def test_create_item_non_list_tags_returns_400(api):
    # A bare string would otherwise be iterated char-by-char into bogus tags.
    resp = _make_item(api, tags="dairy")

    assert resp.status_code == 400
    assert "tags" in resp.body["error"].lower()


# ---------------------------------------------------------------------------
# GET /items (with filters)
# ---------------------------------------------------------------------------

def test_list_items_all(api):
    _make_item(api, name="Milk", location_id="fridge")
    _make_item(api, name="Bread", location_id="pantry")

    resp = api.call("GET", "/items")

    assert resp.status_code == 200
    assert {i["name"] for i in resp.body["items"]} == {"Milk", "Bread"}


def test_list_items_by_location(api):
    _make_item(api, name="Milk", location_id="fridge")
    _make_item(api, name="Bread", location_id="pantry")

    resp = api.call("GET", "/items", query={"location_id": "fridge"})

    assert resp.status_code == 200
    assert [i["name"] for i in resp.body["items"]] == ["Milk"]


def test_list_items_by_tag(api):
    _make_item(api, name="Milk", tags=["dairy"])
    _make_item(api, name="Bread", tags=["bakery"])

    resp = api.call("GET", "/items", query={"tag": "dairy"})

    assert resp.status_code == 200
    assert [i["name"] for i in resp.body["items"]] == ["Milk"]


def test_list_items_location_and_tag_stacks(api):
    # location_id AND tag: only items matching BOTH are returned.
    _make_item(api, name="Milk", location_id="fridge", tags=["dairy"])
    _make_item(api, name="Cheese", location_id="fridge", tags=["snack"])   # right loc, wrong tag
    _make_item(api, name="Yogurt", location_id="pantry", tags=["dairy"])   # right tag, wrong loc

    resp = api.call("GET", "/items", query={"location_id": "fridge", "tag": "dairy"})

    assert resp.status_code == 200
    assert [i["name"] for i in resp.body["items"]] == ["Milk"]


# Name search lives on POST /search (fuzzy, ranked) — see tests/e2e/test_search.py.
# GET /items only exposes structural location/tag filters.


# ---------------------------------------------------------------------------
# GET /items/expiring
#
# NOTE: this path must be matched before /items/<item_id>. If it were shadowed
# we'd get a 404 "Item not found" instead of an items list.
# ---------------------------------------------------------------------------

def test_expiring_route_reachable_and_lists(api):
    _make_item(api, name="Yogurt", use_by_date="2020-01-01T00:00:00+00:00")

    resp = api.call("GET", "/items/expiring", query={"days": "1000000"})

    assert resp.status_code == 200
    assert [i["name"] for i in resp.body["items"]] == ["Yogurt"]


def test_expiring_filters_by_location(api):
    _make_item(api, name="Yogurt", location_id="fridge",
               use_by_date="2020-01-01T00:00:00+00:00")
    _make_item(api, name="Bread", location_id="pantry",
               use_by_date="2020-01-01T00:00:00+00:00")

    resp = api.call("GET", "/items/expiring",
                    query={"days": "1000000", "location_id": "fridge"})

    assert resp.status_code == 200
    assert [i["name"] for i in resp.body["items"]] == ["Yogurt"]


def test_expiring_invalid_days_returns_400(api):
    resp = api.call("GET", "/items/expiring", query={"days": "soon"})

    assert resp.status_code == 400
    assert "days" in resp.body["error"].lower()


def test_expiring_negative_days_returns_400(api):
    resp = api.call("GET", "/items/expiring", query={"days": "-5"})

    assert resp.status_code == 400
    assert "days" in resp.body["error"].lower()


# ---------------------------------------------------------------------------
# GET /items/<id>
# ---------------------------------------------------------------------------

def test_get_item_happy(api):
    created = _make_item(api).body["item"]

    resp = api.call("GET", f"/items/{created['item_id']}")

    assert resp.status_code == 200
    assert resp.body["item"]["item_id"] == created["item_id"]


def test_get_item_not_found_returns_404(api):
    resp = api.call("GET", "/items/does-not-exist")

    assert resp.status_code == 404
    assert resp.body["error"] == "Item not found"


# ---------------------------------------------------------------------------
# PUT /items/<id>
# ---------------------------------------------------------------------------

def test_update_item_happy(api):
    created = _make_item(api).body["item"]

    resp = api.call("PUT", f"/items/{created['item_id']}",
                    body={"name": "Whole Milk", "notes": "updated"})

    assert resp.status_code == 200
    assert resp.body["item"]["name"] == "Whole Milk"
    assert resp.body["item"]["notes"] == "updated"


def test_update_item_not_found_returns_404(api):
    resp = api.call("PUT", "/items/does-not-exist", body={"name": "x"})

    assert resp.status_code == 404
    assert resp.body["error"] == "Item not found"


def test_update_item_invalid_dimension_returns_400(api):
    created = _make_item(api).body["item"]

    resp = api.call(
        "PUT", f"/items/{created['item_id']}",
        body={"dimensions": [{"dimension_type": "weight", "value": 1, "unit": "furlong"}]},
    )

    assert resp.status_code == 400
    assert "dimension" in resp.body["error"].lower()


# ---------------------------------------------------------------------------
# DELETE /items/<id>
# ---------------------------------------------------------------------------

def test_delete_item_happy(api):
    created = _make_item(api).body["item"]

    resp = api.call("DELETE", f"/items/{created['item_id']}")

    assert resp.status_code == 200
    assert "deleted" in resp.body["message"].lower()
    assert api.call("GET", f"/items/{created['item_id']}").status_code == 404


def test_delete_item_not_found_returns_404(api):
    resp = api.call("DELETE", "/items/does-not-exist")

    assert resp.status_code == 404
    assert resp.body["error"] == "Item not found"
