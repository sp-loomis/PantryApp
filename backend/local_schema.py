"""
Local dev DynamoDB schema for the Tier-1 (fully-local) harness.

The table key schema / GSIs here MUST mirror production (terraform/modules/main)
and the test schema in ``tests/conftest.py::create_tables``. It is duplicated
(rather than imported from the test package) so the runtime local server does not
depend on test-only code; keep the three in sync if the schema changes.

Used by ``local_server.py`` and ``seed_local.py``.
"""

from typing import Any, Dict

# Table names for the local harness. These are exported into the environment
# (``*_TABLE_NAME``) before ``app`` is imported so the Lambda code binds to them.
ITEMS_TABLE = "pantry-local-items"
LOCATIONS_TABLE = "pantry-local-locations"
ITEM_TAGS_TABLE = "pantry-local-item-tags"

TABLE_NAMES = {
    "ITEMS_TABLE_NAME": ITEMS_TABLE,
    "LOCATIONS_TABLE_NAME": LOCATIONS_TABLE,
    "ITEM_TAGS_TABLE_NAME": ITEM_TAGS_TABLE,
}


def _gsi(name: str, hash_key: str, range_key: str) -> Dict[str, Any]:
    return {
        "IndexName": name,
        "KeySchema": [
            {"AttributeName": hash_key, "KeyType": "HASH"},
            {"AttributeName": range_key, "KeyType": "RANGE"},
        ],
        "Projection": {"ProjectionType": "ALL"},
    }


def create_tables(dynamodb) -> None:
    """Create the three app tables (idempotent-safe caller should catch existing)."""
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
        ],
        GlobalSecondaryIndexes=[
            _gsi("LocationIndex", "user_id", "location_id"),
            _gsi("UseByDateIndex", "user_id", "use_by_date"),
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
