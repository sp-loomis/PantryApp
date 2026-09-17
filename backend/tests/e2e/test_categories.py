"""E2E route tests for categories, category-aware items, and report triggers.

Each test drives whole HTTP requests through ``app.lambda_handler`` via the
``api`` fixture; the trigger-sweep tests reach into the reloaded ``app`` module
to invoke the (non-HTTP) report sweep.
"""

from datetime import datetime, timedelta, timezone


# ---------------------------------------------------------------------------
# Category CRUD
# ---------------------------------------------------------------------------

def test_create_weight_category(api):
    resp = api.call("POST", "/categories",
                    body={"name": "Beef", "measure_type": "weight", "preferred_unit": "lb"})
    assert resp.status_code == 201
    cat = resp.body["category"]
    assert cat["measure_type"] == "weight"
    assert cat["preferred_unit"] == "lb"
    assert "category_id" in cat


def test_create_count_category_rejects_preferred_unit(api):
    resp = api.call("POST", "/categories",
                    body={"name": "Eggs", "measure_type": "count", "preferred_unit": "lb"})
    assert resp.status_code == 400


def test_create_weight_category_requires_unit(api):
    resp = api.call("POST", "/categories",
                    body={"name": "Beef", "measure_type": "weight"})
    assert resp.status_code == 400


def test_units_catalog(api):
    resp = api.call("GET", "/categories/units")
    assert resp.status_code == 200
    units = resp.body["units"]
    assert "lb" in units["weight"]
    assert "gallon" in units["volume"]
    assert units["count"] == []


def test_delete_category_clears_it_off_items(api):
    cat = api.call("POST", "/categories",
                   body={"name": "Beef", "measure_type": "weight", "preferred_unit": "lb"}).body["category"]
    item = api.call("POST", "/items", body={
        "name": "Ribeye", "location_id": "fridge", "category_id": cat["category_id"],
        "dimensions": [{"dimension_type": "weight", "value": 2, "unit": "lb"}],
    }).body["item"]

    assert api.call("DELETE", f"/categories/{cat['category_id']}").status_code == 200

    refreshed = api.call("GET", f"/items/{item['item_id']}").body["item"]
    assert refreshed["category_id"] is None


# ---------------------------------------------------------------------------
# Item ↔ category assignment enforcement
# ---------------------------------------------------------------------------

def _beef(api):
    return api.call("POST", "/categories",
                    body={"name": "Beef", "measure_type": "weight", "preferred_unit": "lb"}).body["category"]


def test_item_with_matching_dimension_accepts_category(api):
    cat = _beef(api)
    resp = api.call("POST", "/items", body={
        "name": "Ribeye", "location_id": "fridge", "category_id": cat["category_id"],
        "dimensions": [{"dimension_type": "weight", "value": 2, "unit": "lb"}],
    })
    assert resp.status_code == 201
    assert resp.body["item"]["category_id"] == cat["category_id"]


def test_item_without_matching_dimension_rejected(api):
    cat = _beef(api)
    resp = api.call("POST", "/items", body={
        "name": "Ribeye", "location_id": "fridge", "category_id": cat["category_id"],
        "dimensions": [{"dimension_type": "count", "value": 1, "unit": "units"}],
    })
    assert resp.status_code == 400
    assert "weight" in resp.body["error"]


def test_count_category_accepts_item_without_count_dimension(api):
    # A count category counts items, so it needs no matching dimension. Web items
    # only ever carry weight/volume, so this must succeed.
    cat = api.call("POST", "/categories",
                   body={"name": "Eggs", "measure_type": "count"}).body["category"]
    resp = api.call("POST", "/items", body={
        "name": "Dozen", "location_id": "fridge", "category_id": cat["category_id"],
    })
    assert resp.status_code == 201


def test_update_clearing_dimension_on_categorized_item_rejected(api):
    cat = _beef(api)
    item = api.call("POST", "/items", body={
        "name": "Ribeye", "location_id": "fridge", "category_id": cat["category_id"],
        "dimensions": [{"dimension_type": "weight", "value": 2, "unit": "lb"}],
    }).body["item"]
    resp = api.call("PUT", f"/items/{item['item_id']}", body={
        "dimensions": [{"dimension_type": "count", "value": 1, "unit": "units"}],
    })
    assert resp.status_code == 400


def test_clear_category_on_item(api):
    cat = _beef(api)
    item = api.call("POST", "/items", body={
        "name": "Ribeye", "location_id": "fridge", "category_id": cat["category_id"],
        "dimensions": [{"dimension_type": "weight", "value": 2, "unit": "lb"}],
    }).body["item"]
    resp = api.call("PUT", f"/items/{item['item_id']}", body={"category_id": None})
    assert resp.status_code == 200
    assert resp.body["item"]["category_id"] is None


# ---------------------------------------------------------------------------
# Aggregate by category
# ---------------------------------------------------------------------------

def test_aggregate_includes_by_category(api):
    cat = _beef(api)
    for lb in (2, 3):
        api.call("POST", "/items", body={
            "name": "cut", "location_id": "fridge", "category_id": cat["category_id"],
            "dimensions": [{"dimension_type": "weight", "value": lb, "unit": "lb"}],
        })
    stats = api.call("GET", "/aggregate").body["stats"]
    by_cat = {c["category_id"]: c for c in stats["by_category"]}
    assert by_cat[cat["category_id"]]["value"] == 5.0
    assert by_cat[cat["category_id"]]["unit"] == "lb"


# ---------------------------------------------------------------------------
# Report trigger gating (via the sweep)
# ---------------------------------------------------------------------------

def _future_now():
    return datetime.now(timezone.utc) + timedelta(days=2)


def _beef_report(api, operator, threshold):
    cat = _beef(api)
    api.call("POST", "/items", body={
        "name": "Ribeye", "location_id": "fridge", "category_id": cat["category_id"],
        "dimensions": [{"dimension_type": "weight", "value": 5, "unit": "lb"}],
    })
    report = api.call("POST", "/reports", body={
        "name": "Low beef",
        "schedule": {"frequency": "daily", "time_of_day": "09:00", "tz": "UTC"},
        "sections": [{"type": "item_query", "heading": "Beef", "config": {}}],
        "trigger": {"match": "all", "conditions": [{
            "query": {}, "match": "all",
            "inequalities": [{"category_id": cat["category_id"], "operator": operator, "threshold": threshold}],
        }]},
    }).body["report"]
    return report


def test_sweep_generates_when_trigger_met(api):
    _beef_report(api, "below", 10)  # 5 lb < 10 -> fire
    result = api._app.run_report_sweep(now=_future_now())
    assert result["generated"] == 1
    assert result["skipped"] == 0
    assert api.call("GET", "/messages").body["messages"]


def test_sweep_skips_when_trigger_not_met(api):
    _beef_report(api, "above", 10)  # 5 lb is not > 10 -> skip
    result = api._app.run_report_sweep(now=_future_now())
    assert result["generated"] == 0
    assert result["skipped"] == 1
    # No message written, but the report's next_run advanced past the due time.
    assert api.call("GET", "/messages").body["messages"] == []


def test_report_trigger_rejects_unknown_category(api):
    resp = api.call("POST", "/reports", body={
        "name": "Bad",
        "schedule": {"frequency": "daily", "time_of_day": "09:00", "tz": "UTC"},
        "trigger": {"conditions": [{
            "inequalities": [{"category_id": "ghost", "operator": "below", "threshold": 1}],
        }]},
    })
    assert resp.status_code == 400
