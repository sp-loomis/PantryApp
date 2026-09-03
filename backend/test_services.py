"""
Service-layer and routing tests for the Pantry App backend.

Uses moto to mock DynamoDB. Covers the behavior changed in the backend
cleanup: the expiring-items bug fixes, Decimal/float response consistency,
tag denormalization, aggregate stats without legacy fields, and the new
tag endpoints.
"""

import json
import os
import importlib
from decimal import Decimal

import boto3
import pytest
from moto import mock_aws

ITEMS_TABLE = "test-items"
LOCATIONS_TABLE = "test-locations"
ITEM_TAGS_TABLE = "test-item-tags"

USER = "user-1"


class _FakeLambdaContext:
    """Minimal stand-in for the Lambda context object (used by Powertools logging)."""
    function_name = "test-fn"
    memory_limit_in_mb = 128
    invoked_function_arn = "arn:aws:lambda:us-east-1:123456789012:function:test-fn"
    aws_request_id = "test-request-id"


def _create_tables(dynamodb):
    """Create the three tables with the same key schema/GSIs as production."""
    dynamodb.create_table(
        TableName=ITEMS_TABLE,
        BillingMode="PAY_PER_REQUEST",
        KeySchema=[
            {"AttributeName": "user_id", "KeyType": "HASH"},
            {"AttributeName": "item_id", "KeyType": "RANGE"},
        ],
        AttributeDefinitions=[
            {"AttributeName": "user_id", "AttributeType": "S"},
            {"AttributeName": "item_id", "AttributeType": "S"},
            {"AttributeName": "location_id", "AttributeType": "S"},
            {"AttributeName": "use_by_date", "AttributeType": "S"},
            {"AttributeName": "item_name", "AttributeType": "S"},
        ],
        GlobalSecondaryIndexes=[
            _gsi("LocationIndex", "user_id", "location_id"),
            _gsi("UseByDateIndex", "user_id", "use_by_date"),
            _gsi("ItemNameIndex", "user_id", "item_name"),
        ],
    )
    dynamodb.create_table(
        TableName=LOCATIONS_TABLE,
        BillingMode="PAY_PER_REQUEST",
        KeySchema=[
            {"AttributeName": "user_id", "KeyType": "HASH"},
            {"AttributeName": "location_id", "KeyType": "RANGE"},
        ],
        AttributeDefinitions=[
            {"AttributeName": "user_id", "AttributeType": "S"},
            {"AttributeName": "location_id", "AttributeType": "S"},
        ],
    )
    dynamodb.create_table(
        TableName=ITEM_TAGS_TABLE,
        BillingMode="PAY_PER_REQUEST",
        KeySchema=[
            {"AttributeName": "user_id", "KeyType": "HASH"},
            {"AttributeName": "tag_item_composite", "KeyType": "RANGE"},
        ],
        AttributeDefinitions=[
            {"AttributeName": "user_id", "AttributeType": "S"},
            {"AttributeName": "tag_item_composite", "AttributeType": "S"},
            {"AttributeName": "tag_name", "AttributeType": "S"},
        ],
        GlobalSecondaryIndexes=[_gsi("TagIndex", "user_id", "tag_name")],
    )


def _gsi(name, hash_key, range_key):
    return {
        "IndexName": name,
        "KeySchema": [
            {"AttributeName": hash_key, "KeyType": "HASH"},
            {"AttributeName": range_key, "KeyType": "RANGE"},
        ],
        "Projection": {"ProjectionType": "ALL"},
    }


@pytest.fixture
def services():
    """Provide ItemService + LocationService backed by mocked DynamoDB."""
    with mock_aws():
        dynamodb = boto3.resource("dynamodb", region_name="us-east-1")
        _create_tables(dynamodb)

        # Import here so `dimensions`/`models`/`services` resolve normally.
        from services import ItemService, LocationService

        item_service = ItemService(
            dynamodb.Table(ITEMS_TABLE), dynamodb.Table(ITEM_TAGS_TABLE)
        )
        location_service = LocationService(dynamodb.Table(LOCATIONS_TABLE))
        yield item_service, location_service, dynamodb


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


# ---------------------------------------------------------------------------
# Bug #1: /items/expiring route is reachable (not shadowed by /items/<id>)
# ---------------------------------------------------------------------------

def test_expiring_route_not_shadowed():
    with mock_aws():
        dynamodb = boto3.resource("dynamodb", region_name="us-east-1")
        _create_tables(dynamodb)

        os.environ["ITEMS_TABLE_NAME"] = ITEMS_TABLE
        os.environ["LOCATIONS_TABLE_NAME"] = LOCATIONS_TABLE
        os.environ["ITEM_TAGS_TABLE_NAME"] = ITEM_TAGS_TABLE

        import app
        importlib.reload(app)

        event = {
            "httpMethod": "GET",
            "path": "/items/expiring",
            "queryStringParameters": {"days": "7"},
            "headers": {},
            "requestContext": {"authorizer": {"claims": {"sub": USER}}},
            "body": None,
            "isBase64Encoded": False,
        }
        result = app.lambda_handler(event, _FakeLambdaContext())

        assert result["statusCode"] == 200
        body = json.loads(result["body"])
        # If the route were shadowed by /items/<item_id>, we'd get a 404
        # "Item not found" instead of an items list.
        assert "items" in body


if __name__ == "__main__":
    import sys
    sys.exit(pytest.main([__file__, "-v"]))
