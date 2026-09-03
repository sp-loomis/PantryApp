"""E2E route tests for GET /aggregate (inventory statistics)."""


def _make_item(api, **overrides):
    body = {"name": "Item", "location_id": "fridge"}
    body.update(overrides)
    return api.call("POST", "/items", body=body).body["item"]


def _seed(api):
    _make_item(api, name="Milk", location_id="fridge", tags=["dairy"],
               dimensions=[{"dimension_type": "volume", "value": 1, "unit": "gallon"}],
               use_by_date="2030-01-01T00:00:00+00:00")
    _make_item(api, name="Flour", location_id="pantry", tags=["baking"],
               dimensions=[{"dimension_type": "weight", "value": 2, "unit": "lb"}])


def test_aggregate_no_filter(api):
    _seed(api)

    resp = api.call("GET", "/aggregate")

    assert resp.status_code == 200
    stats = resp.body["stats"]
    assert stats["total_items"] == 2
    assert stats["items_with_expiry"] == 1
    assert "weight" in stats["aggregated_dimensions"]
    assert "volume" in stats["aggregated_dimensions"]


def test_aggregate_by_location(api):
    _seed(api)

    resp = api.call("GET", "/aggregate", query={"location_id": "pantry"})

    assert resp.status_code == 200
    stats = resp.body["stats"]
    assert stats["total_items"] == 1
    assert "weight" in stats["aggregated_dimensions"]
    assert "volume" not in stats["aggregated_dimensions"]


def test_aggregate_by_tag(api):
    _seed(api)

    resp = api.call("GET", "/aggregate", query={"tag": "dairy"})

    assert resp.status_code == 200
    assert resp.body["stats"]["total_items"] == 1


def test_aggregate_location_and_tag_stacks(api):
    # location_id AND tag narrow together (intersection), matching /items and /search.
    _make_item(api, name="Milk", location_id="fridge", tags=["dairy"])
    _make_item(api, name="Cheese", location_id="fridge", tags=["snack"])   # right loc, wrong tag
    _make_item(api, name="Yogurt", location_id="pantry", tags=["dairy"])   # right tag, wrong loc

    resp = api.call("GET", "/aggregate", query={"location_id": "fridge", "tag": "dairy"})

    assert resp.status_code == 200
    assert resp.body["stats"]["total_items"] == 1


def test_aggregate_unit_conversion(api):
    _seed(api)

    resp = api.call("GET", "/aggregate", query={"weight_unit": "kg"})

    assert resp.status_code == 200
    weight = resp.body["stats"]["aggregated_dimensions"]["weight"]
    assert weight["unit"] == "kg"


def test_aggregate_invalid_unit_returns_400(api):
    _seed(api)

    resp = api.call("GET", "/aggregate", query={"weight_unit": "furlong"})

    assert resp.status_code == 400
    assert "unit" in resp.body["error"].lower()
