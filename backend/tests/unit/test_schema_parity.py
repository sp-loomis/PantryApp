"""
Guard against DynamoDB schema drift.

``schema.py`` is the single source for the local and test harnesses, but the
production tables are defined independently in Terraform
(``terraform/modules/main/main.tf``), which cannot import Python. This test pins a
canonical snapshot of ``schema.TABLES`` so any change to the key schema / GSIs /
streams is a conscious edit here AND a reminder to mirror it into the Terraform
HCL (and to run a migration if needed).

If this test fails because you intentionally changed the schema: update
``EXPECTED`` below, then make the matching change in
``terraform/modules/main/main.tf`` (and the IAM policy + Lambda env map).
"""

import schema


def _canonical(spec: "schema.TableSpec") -> dict:
    return {
        "suffix": spec.suffix,
        "env": spec.env,
        "hash_key": spec.hash_key,
        "range_key": spec.range_key,
        "attributes": sorted(spec.attributes),
        "gsis": sorted(
            (
                g["IndexName"],
                tuple(k["AttributeName"] for k in g["KeySchema"]),
            )
            for g in spec.gsis
        ),
        "ttl_attribute": spec.ttl_attribute,
        "stream": spec.stream,
    }


EXPECTED = {
    "items": {
        "suffix": "items",
        "env": "ITEMS_TABLE_NAME",
        "hash_key": "user_id",
        "range_key": "item_id",
        "attributes": [
            ("category_id", "S"),
            ("item_id", "S"),
            ("location_id", "S"),
            ("use_by_date", "S"),
            ("user_id", "S"),
        ],
        "gsis": [
            ("CategoryIndex", ("user_id", "category_id")),
            ("LocationIndex", ("user_id", "location_id")),
            ("UseByDateIndex", ("user_id", "use_by_date")),
        ],
        "ttl_attribute": None,
        "stream": None,
    },
    "categories": {
        "suffix": "categories",
        "env": "CATEGORIES_TABLE_NAME",
        "hash_key": "user_id",
        "range_key": "category_id",
        "attributes": [("category_id", "S"), ("user_id", "S")],
        "gsis": [],
        "ttl_attribute": None,
        "stream": None,
    },
    "locations": {
        "suffix": "locations",
        "env": "LOCATIONS_TABLE_NAME",
        "hash_key": "user_id",
        "range_key": "location_id",
        "attributes": [("location_id", "S"), ("user_id", "S")],
        "gsis": [],
        "ttl_attribute": None,
        "stream": None,
    },
    "item_tags": {
        "suffix": "item-tags",
        "env": "ITEM_TAGS_TABLE_NAME",
        "hash_key": "user_id",
        "range_key": "tag_item_composite",
        "attributes": [
            ("tag_item_composite", "S"),
            ("tag_name", "S"),
            ("user_id", "S"),
        ],
        "gsis": [("TagIndex", ("user_id", "tag_name"))],
        "ttl_attribute": None,
        "stream": None,
    },
    "tasks": {
        "suffix": "tasks",
        "env": "TASKS_TABLE_NAME",
        "hash_key": "user_id",
        "range_key": "task_id",
        "attributes": [("task_id", "S"), ("user_id", "S")],
        "gsis": [],
        "ttl_attribute": None,
        "stream": None,
    },
    "reports": {
        "suffix": "reports",
        "env": "REPORTS_TABLE_NAME",
        "hash_key": "user_id",
        "range_key": "report_id",
        "attributes": [("report_id", "S"), ("user_id", "S")],
        "gsis": [],
        "ttl_attribute": None,
        "stream": None,
    },
    "messages": {
        "suffix": "messages",
        "env": "MESSAGES_TABLE_NAME",
        "hash_key": "user_id",
        "range_key": "message_id",
        "attributes": [
            ("message_id", "S"),
            ("unread_sort", "S"),
            ("user_id", "S"),
        ],
        "gsis": [("UnreadIndex", ("user_id", "unread_sort"))],
        "ttl_attribute": None,
        "stream": None,
    },
    "slack_connections": {
        "suffix": "slack-connections",
        "env": "SLACK_CONNECTIONS_TABLE_NAME",
        "hash_key": "user_id",
        "range_key": "connection_id",
        "attributes": [("connection_id", "S"), ("user_id", "S")],
        "gsis": [],
        "ttl_attribute": None,
        "stream": None,
    },
    "slack_nonces": {
        "suffix": "slack-nonces",
        "env": "SLACK_NONCES_TABLE_NAME",
        "hash_key": "nonce",
        "range_key": None,
        "attributes": [("nonce", "S")],
        "gsis": [],
        "ttl_attribute": "expires_at",
        "stream": None,
    },
}


def test_schema_matches_snapshot():
    actual = {name: _canonical(spec) for name, spec in schema.TABLES.items()}
    assert actual == EXPECTED


def test_table_names_apply_prefix():
    names = schema.table_names("test-")
    assert names["ITEMS_TABLE_NAME"] == "test-items"
    assert names["ITEM_TAGS_TABLE_NAME"] == "test-item-tags"
    assert names["SLACK_NONCES_TABLE_NAME"] == "test-slack-nonces"
    # One env var per table, no collisions.
    assert len(names) == len(schema.TABLES)
