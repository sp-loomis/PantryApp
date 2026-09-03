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


def test_search_by_name_is_fuzzy_substring(api):
    _seed(api)

    resp = api.call("POST", "/search", body={"name": "mil"})

    assert resp.status_code == 200
    assert [i["name"] for i in resp.body["items"]] == ["Milk"]


def test_search_by_name_tolerates_typos(api):
    _make_item(api, name="Cheese", location_id="fridge")

    resp = api.call("POST", "/search", body={"name": "chese"})

    assert resp.status_code == 200
    assert [i["name"] for i in resp.body["items"]] == ["Cheese"]


def test_search_multiword_is_order_independent(api):
    _make_item(api, name="Whole Milk", location_id="fridge")
    _make_item(api, name="Milk", location_id="fridge")

    resp = api.call("POST", "/search", body={"name": "milk whole"})

    assert resp.status_code == 200
    # Only "Whole Milk" satisfies both terms (AND).
    assert [i["name"] for i in resp.body["items"]] == ["Whole Milk"]


def test_search_returns_match_metadata_with_spans(api):
    _make_item(api, name="Whole Milk", location_id="fridge")

    resp = api.call("POST", "/search", body={"name": "milk whole"})

    match = resp.body["items"][0]["match"]
    assert match["score"] == 1.0
    assert match["spans"] == [{"start": 0, "end": 5}, {"start": 6, "end": 10}]


def test_search_name_and_location_filters_by_both(api):
    # Regression: location must still constrain results when a name is present.
    _make_item(api, name="Milk", location_id="fridge")
    _make_item(api, name="Milk", location_id="pantry")

    resp = api.call("POST", "/search", body={"name": "milk", "location_id": "fridge"})

    assert resp.status_code == 200
    assert {i["location_id"] for i in resp.body["items"]} == {"fridge"}


def test_search_min_score_tightens_results(api):
    _make_item(api, name="Cheese", location_id="fridge")

    # The typo matches at the default threshold but not a strict one.
    assert api.call("POST", "/search", body={"name": "chese"}).body["items"]
    resp = api.call("POST", "/search", body={"name": "chese", "min_score": 0.99})
    assert resp.body["items"] == []


def test_search_invalid_min_score_returns_400(api):
    resp = api.call("POST", "/search", body={"name": "milk", "min_score": 5})

    assert resp.status_code == 400
    assert "min_score" in resp.body["error"]


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


def test_search_multi_tag_requires_all(api):
    # AND semantics: an item must carry EVERY requested tag.
    _make_item(api, name="Greek Yogurt", tags=["dairy", "organic"])
    _make_item(api, name="Milk", tags=["dairy"])           # missing "organic"
    _make_item(api, name="Kale", tags=["organic"])         # missing "dairy"

    resp = api.call("POST", "/search", body={"tags": ["dairy", "organic"]})

    assert resp.status_code == 200
    assert [i["name"] for i in resp.body["items"]] == ["Greek Yogurt"]


def test_search_non_list_tags_returns_400(api):
    resp = api.call("POST", "/search", body={"tags": "dairy"})

    assert resp.status_code == 400
    assert "tags" in resp.body["error"].lower()


def test_search_malformed_date_returns_400(api):
    resp = api.call("POST", "/search", body={"use_by_date_start": "not-a-date"})

    assert resp.status_code == 400
    assert "use_by_date_start" in resp.body["error"]


def test_search_non_numeric_min_score_returns_400(api):
    resp = api.call("POST", "/search", body={"name": "milk", "min_score": "high"})

    assert resp.status_code == 400
    assert "min_score" in resp.body["error"]


def test_search_by_date_range(api):
    _seed(api)

    resp = api.call("POST", "/search", body={
        "use_by_date_start": "2030-05-01T00:00:00+00:00",
        "use_by_date_end": "2030-07-01T00:00:00+00:00",
    })

    assert resp.status_code == 200
    assert [i["name"] for i in resp.body["items"]] == ["Bread"]
