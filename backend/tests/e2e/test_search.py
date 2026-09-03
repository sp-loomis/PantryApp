"""E2E route tests for POST /search (advanced multi-criteria search)."""


def _make_item(api, **overrides):
    body = {"name": "Milk", "location_id": "fridge"}
    body.update(overrides)
    return api.call("POST", "/items", body=body).body["item"]


def _seed(api):
    _make_item(api, name="Milk", location_id="fridge", tags=["dairy"],
               use_by_date="2030-01-01T00:00:00+00:00")
    _make_item(api, name="Bread", location_id="pantry", tags=["bakery"],
               use_by_date="2030-06-01T00:00:00+00:00")
    _make_item(api, name="Cheese", location_id="fridge", tags=["dairy"],
               use_by_date="2030-12-01T00:00:00+00:00")


def test_search_no_criteria_returns_all(api):
    _seed(api)

    resp = api.call("POST", "/search", body={})

    assert resp.status_code == 200
    assert len(resp.body["items"]) == 3


def test_search_by_name(api):
    _seed(api)

    resp = api.call("POST", "/search", body={"name": "Milk"})

    assert resp.status_code == 200
    assert [i["name"] for i in resp.body["items"]] == ["Milk"]


def test_search_by_location(api):
    _seed(api)

    resp = api.call("POST", "/search", body={"location_id": "fridge"})

    assert resp.status_code == 200
    assert {i["name"] for i in resp.body["items"]} == {"Milk", "Cheese"}


def test_search_by_tags(api):
    _seed(api)

    resp = api.call("POST", "/search", body={"tags": ["bakery"]})

    assert resp.status_code == 200
    assert [i["name"] for i in resp.body["items"]] == ["Bread"]


def test_search_by_date_range(api):
    _seed(api)

    resp = api.call("POST", "/search", body={
        "use_by_date_start": "2030-05-01T00:00:00+00:00",
        "use_by_date_end": "2030-07-01T00:00:00+00:00",
    })

    assert resp.status_code == 200
    assert [i["name"] for i in resp.body["items"]] == ["Bread"]
