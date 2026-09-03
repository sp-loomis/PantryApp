"""
Service-layer tests for the Pantry App backend.

Uses moto to mock DynamoDB (shared table schema and the ``services`` fixture
live in ``tests/conftest.py``). Covers the behavior changed in the backend
cleanup: the expiring-items bug fixes, Decimal/float response consistency,
tag denormalization, aggregate stats without legacy fields, and the new
tag endpoints.

Route-level (HTTP) behavior is covered separately by the E2E suite in
``tests/e2e/``.
"""

import pytest

USER = "user-1"


# ---------------------------------------------------------------------------
# Bug #3: create response is float-typed and consistent with reads
# ---------------------------------------------------------------------------

def test_create_item_returns_floats_and_no_legacy_fields(services):
    item_service, _, _ = services
    created = item_service.create_item(
        user_id=USER,
        name="Milk",
        location_id="loc-1",
        dimensions=[{"dimension_type": "count", "value": 12, "unit": "units"}],
        tags=["Dairy"],
    )

    # No legacy fields.
    assert "quantity" not in created
    assert "unit" not in created

    # Dimension value is a plain float, not Decimal.
    value = created["dimensions"][0]["value"]
    assert isinstance(value, float)
    assert value == 12.0

    # Tags are denormalized, lowercased, and present.
    assert created["tags"] == ["dairy"]

    # Read path matches the create response shape/types.
    fetched = item_service.get_item(USER, created["item_id"])
    assert isinstance(fetched["dimensions"][0]["value"], float)
    assert fetched["tags"] == ["dairy"]


# ---------------------------------------------------------------------------
# Adding many copies at once (copies parameter)
# ---------------------------------------------------------------------------

def test_create_item_copies_creates_distinct_entries(services):
    item_service, _, _ = services
    created = item_service.create_item(
        user_id=USER,
        name="Canned Beans",
        location_id="pantry",
        tags=["Staple"],
        copies=3,
    )

    # copies>1 returns a list of that many items.
    assert isinstance(created, list)
    assert len(created) == 3

    # Each copy is a distinct entry with identical shared fields.
    ids = {item["item_id"] for item in created}
    assert len(ids) == 3
    for item in created:
        assert item["name"] == "Canned Beans"
        assert item["location_id"] == "pantry"
        assert item["tags"] == ["staple"]

    # Every copy is independently retrievable from storage.
    for item in created:
        assert item_service.get_item(USER, item["item_id"]) is not None


def test_create_item_copies_denormalizes_tags_for_each_copy(services):
    item_service, _, _ = services
    created = item_service.create_item(
        user_id=USER,
        name="Yogurt",
        location_id="fridge",
        tags=["Dairy"],
        copies=2,
    )

    # A reverse-index tag row exists for each new item id.
    tagged_ids = set(item_service.tag_service.get_items_by_tag(USER, "dairy"))
    for item in created:
        assert item["item_id"] in tagged_ids


def test_create_item_copies_default_returns_single_dict(services):
    item_service, _, _ = services
    created = item_service.create_item(
        user_id=USER, name="Milk", location_id="fridge"
    )
    # Default (copies omitted) preserves the single-dict contract.
    assert isinstance(created, dict)
    assert created["name"] == "Milk"

    created_one = item_service.create_item(
        user_id=USER, name="Milk", location_id="fridge", copies=1
    )
    assert isinstance(created_one, dict)


@pytest.mark.parametrize("bad_copies", [0, -1, 1.5, "3", True, None])
def test_create_item_invalid_copies_raises(services, bad_copies):
    item_service, _, _ = services
    with pytest.raises(ValueError):
        item_service.create_item(
            user_id=USER, name="Milk", location_id="fridge", copies=bad_copies
        )


def test_create_item_copies_over_cap_raises(services):
    from services import COPIES_MAX

    item_service, _, _ = services
    with pytest.raises(ValueError):
        item_service.create_item(
            user_id=USER, name="Milk", location_id="fridge", copies=COPIES_MAX + 1
        )


# ---------------------------------------------------------------------------
# Bug #2: expiring honors the location filter
# ---------------------------------------------------------------------------

def test_expiring_items_filters_by_location(services):
    item_service, _, _ = services
    item_service.create_item(
        USER, "Yogurt", "fridge", use_by_date="2020-01-01T00:00:00+00:00"
    )
    item_service.create_item(
        USER, "Bread", "pantry", use_by_date="2020-01-01T00:00:00+00:00"
    )

    # Wide window so both are "expiring"; location filter must still apply.
    all_expiring = item_service.get_expiring_items(USER, days=1_000_000)
    assert len(all_expiring) == 2

    fridge_only = item_service.get_expiring_items(USER, location_id="fridge", days=1_000_000)
    assert [i["name"] for i in fridge_only] == ["Yogurt"]


def test_expiring_items_excludes_items_without_use_by_date(services):
    item_service, _, _ = services
    item_service.create_item(USER, "Salt", "pantry")  # no use_by_date
    assert item_service.get_expiring_items(USER, days=1_000_000) == []


# ---------------------------------------------------------------------------
# Tag denormalization + reverse index
# ---------------------------------------------------------------------------

def test_tags_denormalized_and_reverse_index(services):
    item_service, _, _ = services
    a = item_service.create_item(USER, "Apple", "loc", tags=["fruit", "fresh"])
    item_service.create_item(USER, "Bread", "loc", tags=["bakery"])

    # Reverse lookup by tag works via TagIndex.
    fruit_items = item_service.get_items_by_tag(USER, "fruit")
    assert [i["item_id"] for i in fruit_items] == [a["item_id"]]

    # list_all_tags returns the distinct, sorted set.
    assert item_service.list_all_tags(USER) == ["bakery", "fresh", "fruit"]


def test_update_item_reconciles_tags(services):
    item_service, _, _ = services
    created = item_service.create_item(USER, "Apple", "loc", tags=["fruit", "old"])
    item_id = created["item_id"]

    updated = item_service.update_item(USER, item_id, {"tags": ["fruit", "new"]})
    assert updated["tags"] == ["fruit", "new"]

    # Reverse index reflects the removal of "old" and addition of "new".
    assert item_service.get_items_by_tag(USER, "old") == []
    assert [i["item_id"] for i in item_service.get_items_by_tag(USER, "new")] == [item_id]


def test_add_and_remove_item_tags(services):
    item_service, _, _ = services
    created = item_service.create_item(USER, "Apple", "loc", tags=["fruit"])
    item_id = created["item_id"]

    tags = item_service.add_item_tags(USER, item_id, ["Fresh", "GREEN"])
    assert tags == ["fresh", "fruit", "green"]

    tags = item_service.remove_item_tag(USER, item_id, "fruit")
    assert tags == ["fresh", "green"]

    assert item_service.get_item_tags(USER, item_id) == ["fresh", "green"]
    assert item_service.get_item_tags(USER, "missing") is None


def test_delete_item_clears_reverse_index(services):
    item_service, _, _ = services
    created = item_service.create_item(USER, "Apple", "loc", tags=["fruit"])
    assert item_service.delete_item(USER, created["item_id"]) is True
    assert item_service.get_items_by_tag(USER, "fruit") == []


# ---------------------------------------------------------------------------
# Aggregate stats: no legacy fields, dimensions aggregated
# ---------------------------------------------------------------------------

def test_aggregate_stats_shape(services):
    item_service, _, _ = services
    item_service.create_item(
        USER, "Milk", "loc",
        dimensions=[{"dimension_type": "volume", "value": 1, "unit": "gallon"}],
        use_by_date="2030-01-01T00:00:00+00:00",
    )
    item_service.create_item(
        USER, "Flour", "loc",
        dimensions=[{"dimension_type": "weight", "value": 2, "unit": "lb"}],
    )

    stats = item_service.get_aggregate_stats(USER)
    assert stats["total_items"] == 2
    assert stats["items_with_expiry"] == 1
    assert "total_quantity" not in stats
    assert "quantities_by_unit" not in stats
    assert "weight" in stats["aggregated_dimensions"]
    assert "volume" in stats["aggregated_dimensions"]


if __name__ == "__main__":
    import sys
    sys.exit(pytest.main([__file__, "-v"]))
