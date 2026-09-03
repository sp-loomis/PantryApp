"""E2E route tests for the storage-location endpoints.

Each test drives a whole HTTP request through ``app.lambda_handler`` via the
``api`` fixture and asserts both the status code and the response body shape.
"""


# ---------------------------------------------------------------------------
# POST /locations
# ---------------------------------------------------------------------------

def test_create_location_happy(api):
    resp = api.call("POST", "/locations", body={"name": "Pantry"})

    assert resp.status_code == 201
    location = resp.body["location"]
    assert location["name"] == "Pantry"
    assert location["description"] == ""
    assert location["user_id"] == "user-1"
    assert "location_id" in location


def test_create_location_with_description(api):
    resp = api.call(
        "POST", "/locations",
        body={"name": "Garage Freezer", "description": "chest freezer"},
    )

    assert resp.status_code == 201
    assert resp.body["location"]["description"] == "chest freezer"


def test_create_location_missing_name_returns_400(api):
    resp = api.call("POST", "/locations", body={"description": "no name"})

    assert resp.status_code == 400
    assert "name" in resp.body["error"]


# ---------------------------------------------------------------------------
# GET /locations
# ---------------------------------------------------------------------------

def test_list_locations_empty(api):
    resp = api.call("GET", "/locations")

    assert resp.status_code == 200
    assert resp.body["locations"] == []


def test_list_locations_populated(api):
    api.call("POST", "/locations", body={"name": "Pantry"})
    api.call("POST", "/locations", body={"name": "Fridge"})

    resp = api.call("GET", "/locations")

    assert resp.status_code == 200
    names = {loc["name"] for loc in resp.body["locations"]}
    assert names == {"Pantry", "Fridge"}


# ---------------------------------------------------------------------------
# GET /locations/<id>
# ---------------------------------------------------------------------------

def test_get_location_happy(api):
    created = api.call("POST", "/locations", body={"name": "Pantry"}).body["location"]

    resp = api.call("GET", f"/locations/{created['location_id']}")

    assert resp.status_code == 200
    assert resp.body["location"]["location_id"] == created["location_id"]


def test_get_location_not_found_returns_404(api):
    resp = api.call("GET", "/locations/does-not-exist")

    assert resp.status_code == 404
    assert resp.body["error"] == "Location not found"


# ---------------------------------------------------------------------------
# PUT /locations/<id>
# ---------------------------------------------------------------------------

def test_update_location_happy(api):
    created = api.call("POST", "/locations", body={"name": "Pantry"}).body["location"]

    resp = api.call(
        "PUT", f"/locations/{created['location_id']}",
        body={"name": "Main Pantry", "description": "downstairs"},
    )

    assert resp.status_code == 200
    assert resp.body["location"]["name"] == "Main Pantry"
    assert resp.body["location"]["description"] == "downstairs"


def test_update_location_not_found_returns_404(api):
    resp = api.call("PUT", "/locations/does-not-exist", body={"name": "x"})

    assert resp.status_code == 404
    assert resp.body["error"] == "Location not found"


# ---------------------------------------------------------------------------
# DELETE /locations/<id>
# ---------------------------------------------------------------------------

def test_delete_location_happy(api):
    created = api.call("POST", "/locations", body={"name": "Pantry"}).body["location"]

    resp = api.call("DELETE", f"/locations/{created['location_id']}")

    assert resp.status_code == 200
    assert "deleted" in resp.body["message"].lower()

    # Confirm it's gone.
    assert api.call("GET", f"/locations/{created['location_id']}").status_code == 404


def test_delete_location_not_found_returns_404(api):
    resp = api.call("DELETE", "/locations/does-not-exist")

    assert resp.status_code == 404
    assert resp.body["error"] == "Location not found"
