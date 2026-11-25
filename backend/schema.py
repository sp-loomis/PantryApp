"""
Single source of truth for the DynamoDB table schema.

The key schema / GSIs for every app table are declared here ONCE, as data, and
consumed by:

- ``local_schema.py`` — the fully-local dev harness (``pantry-local-*`` names).
- ``tests/conftest.py`` — the moto-backed test harness (``test-*`` names).

Production table names come from Terraform (``terraform/modules/main``) and are
injected into the Lambda via the ``*_TABLE_NAME`` environment variables named in
each spec's ``env`` field. Terraform is HCL and cannot import this module, so the
HCL table definitions are kept in sync by hand; ``tests/unit/test_schema_parity.py``
asserts this module matches a committed snapshot so drift is caught in CI.

This is a runtime module (no test-only dependencies) so the local server can bind
to it without importing test code.
"""

from typing import Any, Dict, List, Optional, Tuple


def gsi(name: str, hash_key: str, range_key: Optional[str] = None) -> Dict[str, Any]:
    """Build an all-projection GSI definition (optionally with a range key)."""
    key_schema = [{"AttributeName": hash_key, "KeyType": "HASH"}]
    if range_key:
        key_schema.append({"AttributeName": range_key, "KeyType": "RANGE"})
    return {
        "IndexName": name,
        "KeySchema": key_schema,
        "Projection": {"ProjectionType": "ALL"},
    }


class TableSpec:
    """A prefix-agnostic description of one DynamoDB table.

    ``suffix`` is appended to a harness prefix (``pantry-local-`` / ``test-``) to
    form the concrete table name. ``env`` is the ``*_TABLE_NAME`` variable the
    Lambda binds to. ``stream`` (when set) is the ``StreamViewType`` for an
    append-only table whose changes feed the analytics tier.
    """

    def __init__(
        self,
        suffix: str,
        env: str,
        hash_key: str,
        range_key: Optional[str] = None,
        attributes: Optional[List[Tuple[str, str]]] = None,
        gsis: Optional[List[Dict[str, Any]]] = None,
        ttl_attribute: Optional[str] = None,
        stream: Optional[str] = None,
    ):
        self.suffix = suffix
        self.env = env
        self.hash_key = hash_key
        self.range_key = range_key
        self.attributes = attributes or []
        self.gsis = gsis or []
        self.ttl_attribute = ttl_attribute
        self.stream = stream

    def name(self, prefix: str) -> str:
        return f"{prefix}{self.suffix}"

    def create_table_kwargs(self, table_name: str) -> Dict[str, Any]:
        """Build the boto3 ``create_table`` kwargs for this spec under a name."""
        key_schema = [{"AttributeName": self.hash_key, "KeyType": "HASH"}]
        if self.range_key:
            key_schema.append({"AttributeName": self.range_key, "KeyType": "RANGE"})

        kwargs: Dict[str, Any] = {
            "TableName": table_name,
            "BillingMode": "PAY_PER_REQUEST",
            "KeySchema": key_schema,
            "AttributeDefinitions": [
                {"AttributeName": n, "AttributeType": t} for n, t in self.attributes
            ],
        }
        if self.gsis:
            kwargs["GlobalSecondaryIndexes"] = self.gsis
        if self.stream:
            kwargs["StreamSpecification"] = {
                "StreamEnabled": True,
                "StreamViewType": self.stream,
            }
        return kwargs


# Ordered logical-name -> spec. Order is the table-creation order.
TABLES: Dict[str, TableSpec] = {
    "items": TableSpec(
        suffix="items",
        env="ITEMS_TABLE_NAME",
        hash_key="user_id",
        range_key="item_id",
        attributes=[
            ("user_id", "S"),
            ("item_id", "S"),
            ("location_id", "S"),
            ("use_by_date", "S"),
            ("category_id", "S"),
        ],
        gsis=[
            gsi("LocationIndex", "user_id", "location_id"),
            gsi("UseByDateIndex", "user_id", "use_by_date"),
            gsi("CategoryIndex", "user_id", "category_id"),
        ],
    ),
    "categories": TableSpec(
        suffix="categories",
        env="CATEGORIES_TABLE_NAME",
        hash_key="user_id",
        range_key="category_id",
        attributes=[("user_id", "S"), ("category_id", "S")],
    ),
    "locations": TableSpec(
        suffix="locations",
        env="LOCATIONS_TABLE_NAME",
        hash_key="user_id",
        range_key="location_id",
        attributes=[("user_id", "S"), ("location_id", "S")],
    ),
    "item_tags": TableSpec(
        suffix="item-tags",
        env="ITEM_TAGS_TABLE_NAME",
        hash_key="user_id",
        range_key="tag_item_composite",
        attributes=[
            ("user_id", "S"),
            ("tag_item_composite", "S"),
            ("tag_name", "S"),
        ],
        gsis=[gsi("TagIndex", "user_id", "tag_name")],
    ),
    "tasks": TableSpec(
        suffix="tasks",
        env="TASKS_TABLE_NAME",
        hash_key="user_id",
        range_key="task_id",
        attributes=[("user_id", "S"), ("task_id", "S")],
    ),
    "reports": TableSpec(
        suffix="reports",
        env="REPORTS_TABLE_NAME",
        hash_key="user_id",
        range_key="report_id",
        attributes=[("user_id", "S"), ("report_id", "S")],
    ),
    "messages": TableSpec(
        suffix="messages",
        env="MESSAGES_TABLE_NAME",
        hash_key="user_id",
        range_key="message_id",
        attributes=[
            ("user_id", "S"),
            ("message_id", "S"),
            ("unread_sort", "S"),
        ],
        # UnreadIndex is sparse: only unread messages carry unread_sort.
        gsis=[gsi("UnreadIndex", "user_id", "unread_sort")],
    ),
    "slack_connections": TableSpec(
        suffix="slack-connections",
        env="SLACK_CONNECTIONS_TABLE_NAME",
        hash_key="user_id",
        range_key="connection_id",
        attributes=[("user_id", "S"), ("connection_id", "S")],
    ),
    "slack_nonces": TableSpec(
        suffix="slack-nonces",
        env="SLACK_NONCES_TABLE_NAME",
        hash_key="nonce",
        attributes=[("nonce", "S")],
        ttl_attribute="expires_at",
    ),
}


def table_names(prefix: str) -> Dict[str, str]:
    """Map every ``*_TABLE_NAME`` env var to its concrete name under ``prefix``."""
    return {spec.env: spec.name(prefix) for spec in TABLES.values()}


def create_all(dynamodb, prefix: str, idempotent: bool = False) -> None:
    """Create every app table under ``prefix``.

    When ``idempotent`` is set, an already-existing table is tolerated (so adding
    a NEW table creates it on a volume where the older tables already exist).
    """
    from botocore.exceptions import ClientError

    for spec in TABLES.values():
        kwargs = spec.create_table_kwargs(spec.name(prefix))
        try:
            dynamodb.create_table(**kwargs)
        except ClientError as err:
            if not idempotent or err.response["Error"]["Code"] != "ResourceInUseException":
                raise
