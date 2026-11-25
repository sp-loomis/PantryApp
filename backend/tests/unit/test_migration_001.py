"""Tests for migration 001 (ledger backfill + use_by_date normalization)."""

import importlib.util
import os

from conftest import ITEMS_TABLE, TASKS_TABLE, LEDGER_TABLE, USER

# Load the numeric-named migration module by path.
_SPEC = importlib.util.spec_from_file_location(
    "migration_001",
    os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
                 "migrations", "001_ledger_and_softdelete.py"),
)
migration_001 = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(migration_001)


def _env(monkeypatch):
    monkeypatch.setenv("ITEMS_TABLE_NAME", ITEMS_TABLE)
    monkeypatch.setenv("TASKS_TABLE_NAME", TASKS_TABLE)
    monkeypatch.setenv("LEDGER_TABLE_NAME", LEDGER_TABLE)


def test_normalizes_dates_and_backfills(dynamodb_tables, monkeypatch):
    _env(monkeypatch)
    items = dynamodb_tables.Table(ITEMS_TABLE)
    tasks = dynamodb_tables.Table(TASKS_TABLE)
    ledger = dynamodb_tables.Table(LEDGER_TABLE)

    # An active item with a full-timestamp use_by_date.
    items.put_item(Item={
        "user_id": USER, "item_id": "i1", "name": "Milk", "location_id": "fridge",
        "use_by_date": "2030-01-01T00:00:00+00:00", "tags": [],
    })
    # A soft-deleted item: skipped for ledger backfill.
    items.put_item(Item={
        "user_id": USER, "item_id": "i2", "name": "Gone", "location_id": "fridge",
        "deleted_at": "2026-01-01T00:00:00+00:00", "tags": [],
    })
    # A completed task (gets a backfill event) and an incomplete one (skipped).
    tasks.put_item(Item={
        "user_id": USER, "task_id": "t1", "name": "Done once",
        "last_completed_at": "2026-05-01T00:00:00+00:00",
    })
    tasks.put_item(Item={"user_id": USER, "task_id": "t2", "name": "Never done"})

    stats = migration_001.migrate(dynamodb_tables)

    assert stats == {"dates_normalized": 1, "item_events": 1, "task_events": 1}
    # Date normalized to date-only.
    assert items.get_item(Key={"user_id": USER, "item_id": "i1"})["Item"]["use_by_date"] == "2030-01-01"
    # Exactly the active item + completed task got events.
    rows = ledger.scan()["Items"]
    assert {(r["entity_type"], r["entity_id"]) for r in rows} == {
        ("item", "i1"), ("task", "t1")
    }


def test_idempotent(dynamodb_tables, monkeypatch):
    _env(monkeypatch)
    items = dynamodb_tables.Table(ITEMS_TABLE)
    items.put_item(Item={
        "user_id": USER, "item_id": "i1", "name": "Milk", "location_id": "fridge",
        "use_by_date": "2030-01-01T00:00:00+00:00", "tags": [],
    })

    first = migration_001.migrate(dynamodb_tables)
    second = migration_001.migrate(dynamodb_tables)

    assert first["item_events"] == 1
    # Re-run makes no further changes.
    assert second == {"dates_normalized": 0, "item_events": 0, "task_events": 0}
    assert len(dynamodb_tables.Table(LEDGER_TABLE).scan()["Items"]) == 1


def test_backfills_baseline_even_when_adjusted_event_exists(dynamodb_tables, monkeypatch):
    """An item touched in the deploy->migrate window (has an item_adjusted but no
    item_created) still gets its item_created baseline backfilled."""
    _env(monkeypatch)
    items = dynamodb_tables.Table(ITEMS_TABLE)
    ledger = dynamodb_tables.Table(LEDGER_TABLE)

    from models import LedgerEvent, ENTITY_ITEM, EVENT_ITEM_ADJUSTED, EVENT_ITEM_CREATED

    items.put_item(Item={
        "user_id": USER, "item_id": "i1", "name": "Milk", "location_id": "fridge", "tags": [],
    })
    # Simulate a post-deploy edit: only an adjusted event exists, no baseline.
    ledger.put_item(Item=LedgerEvent.create(USER, ENTITY_ITEM, "i1", EVENT_ITEM_ADJUSTED).to_dict())

    stats = migration_001.migrate(dynamodb_tables)

    assert stats["item_events"] == 1
    types = {
        e["event_type"]
        for e in ledger.scan()["Items"]
        if e["entity_id"] == "i1"
    }
    assert types == {EVENT_ITEM_ADJUSTED, EVENT_ITEM_CREATED}
    # And a re-run now finds the baseline and skips.
    assert migration_001.migrate(dynamodb_tables)["item_events"] == 0


def test_dry_run_writes_nothing(dynamodb_tables, monkeypatch):
    _env(monkeypatch)
    items = dynamodb_tables.Table(ITEMS_TABLE)
    items.put_item(Item={
        "user_id": USER, "item_id": "i1", "name": "Milk", "location_id": "fridge",
        "use_by_date": "2030-01-01T00:00:00+00:00", "tags": [],
    })

    stats = migration_001.migrate(dynamodb_tables, dry_run=True)

    assert stats["item_events"] == 1  # reported
    assert dynamodb_tables.Table(LEDGER_TABLE).scan()["Items"] == []  # but not written
    assert items.get_item(Key={"user_id": USER, "item_id": "i1"})["Item"]["use_by_date"] == \
        "2030-01-01T00:00:00+00:00"  # unchanged
