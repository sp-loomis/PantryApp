"""
Local dev DynamoDB schema for the Tier-1 (fully-local) harness.

Thin wrapper over the single schema source in ``schema.py`` (the key schema / GSIs
live there once and are shared with the test harness). This module only pins the
local name prefix (``pantry-local-``) and re-exports the names the local server and
seed script import.

Used by ``local_server.py`` and ``seed_local.py``.
"""

import schema

LOCAL_PREFIX = "pantry-local-"

# Concrete local table names, derived from the shared specs.
ITEMS_TABLE = schema.TABLES["items"].name(LOCAL_PREFIX)
LOCATIONS_TABLE = schema.TABLES["locations"].name(LOCAL_PREFIX)
CATEGORIES_TABLE = schema.TABLES["categories"].name(LOCAL_PREFIX)
ITEM_TAGS_TABLE = schema.TABLES["item_tags"].name(LOCAL_PREFIX)
TASKS_TABLE = schema.TABLES["tasks"].name(LOCAL_PREFIX)
REPORTS_TABLE = schema.TABLES["reports"].name(LOCAL_PREFIX)
MESSAGES_TABLE = schema.TABLES["messages"].name(LOCAL_PREFIX)
SLACK_CONNECTIONS_TABLE = schema.TABLES["slack_connections"].name(LOCAL_PREFIX)
SLACK_NONCES_TABLE = schema.TABLES["slack_nonces"].name(LOCAL_PREFIX)

# ``*_TABLE_NAME`` env map, exported into the environment before ``app`` is
# imported so the Lambda code binds to the local tables.
TABLE_NAMES = schema.table_names(LOCAL_PREFIX)


def create_tables(dynamodb) -> None:
    """Create all app tables; existing ones are left as-is (idempotent per table)."""
    schema.create_all(dynamodb, LOCAL_PREFIX, idempotent=True)
