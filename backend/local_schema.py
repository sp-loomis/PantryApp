"""
Local dev DynamoDB schema for the Tier-1 (fully-local) harness.

The table key schema / GSIs here MUST mirror production (terraform/modules/main)
and the test schema in ``tests/conftest.py::create_tables``. It is duplicated
(rather than imported from the test package) so the runtime local server does not
depend on test-only code; keep the three in sync if the schema changes.

Used by ``local_server.py`` and ``seed_local.py``.
"""

from typing import Any, Dict

from botocore.exceptions import ClientError

# Table names for the local harness. These are exported into the environment
# (``*_TABLE_NAME``) before ``app`` is imported so the Lambda code binds to them.
ITEMS_TABLE = "pantry-local-items"
LOCATIONS_TABLE = "pantry-local-locations"
ITEM_TAGS_TABLE = "pantry-local-item-tags"
TASKS_TABLE = "pantry-local-tasks"
REPORTS_TABLE = "pantry-local-reports"
MESSAGES_TABLE = "pantry-local-messages"

TABLE_NAMES = {
    "ITEMS_TABLE_NAME": ITEMS_TABLE,
    "LOCATIONS_TABLE_NAME": LOCATIONS_TABLE,
    "ITEM_TAGS_TABLE_NAME": ITEM_TAGS_TABLE,
    "TASKS_TABLE_NAME": TASKS_TABLE,
    "REPORTS_TABLE_NAME": REPORTS_TABLE,
    "MESSAGES_TABLE_NAME": MESSAGES_TABLE,
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


def _create(dynamodb, **kwargs) -> None:
    """Create one table, tolerating an already-existing one.

    Idempotent per table so adding a NEW table (e.g. reports/messages) creates it
    on a volume where the older tables already exist, instead of aborting on the
    first conflict.
    """
    try:
        dynamodb.create_table(**kwargs)
    except ClientError as err:
        if err.response["Error"]["Code"] != "ResourceInUseException":
            raise


def create_tables(dynamodb) -> None:
    """Create all app tables; existing ones are left as-is (idempotent per table)."""
    _create(
        dynamodb,
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
    _create(
        dynamodb,
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
    _create(
        dynamodb,
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
    _create(
        dynamodb,
        TableName=TASKS_TABLE,
        BillingMode="PAY_PER_REQUEST",
        KeySchema=[
            {"AttributeName": "user_id", "KeyType": "HASH"},
            {"AttributeName": "task_id", "KeyType": "RANGE"},
        ],
        AttributeDefinitions=[
            {"AttributeName": "user_id", "AttributeType": "S"},
            {"AttributeName": "task_id", "AttributeType": "S"},
            {"AttributeName": "due_date", "AttributeType": "S"},
        ],
        GlobalSecondaryIndexes=[_gsi("DueDateIndex", "user_id", "due_date")],
    )
    _create(
        dynamodb,
        TableName=REPORTS_TABLE,
        BillingMode="PAY_PER_REQUEST",
        KeySchema=[
            {"AttributeName": "user_id", "KeyType": "HASH"},
            {"AttributeName": "report_id", "KeyType": "RANGE"},
        ],
        AttributeDefinitions=[
            {"AttributeName": "user_id", "AttributeType": "S"},
            {"AttributeName": "report_id", "AttributeType": "S"},
        ],
    )
    _create(
        dynamodb,
        TableName=MESSAGES_TABLE,
        BillingMode="PAY_PER_REQUEST",
        KeySchema=[
            {"AttributeName": "user_id", "KeyType": "HASH"},
            {"AttributeName": "message_id", "KeyType": "RANGE"},
        ],
        AttributeDefinitions=[
            {"AttributeName": "user_id", "AttributeType": "S"},
            {"AttributeName": "message_id", "AttributeType": "S"},
            {"AttributeName": "unread_sort", "AttributeType": "S"},
        ],
        # UnreadIndex is sparse: only unread messages carry unread_sort, so only
        # they appear here. Marking read removes the attribute (and the row).
        GlobalSecondaryIndexes=[_gsi("UnreadIndex", "user_id", "unread_sort")],
    )
