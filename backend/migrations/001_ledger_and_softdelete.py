"""
Migration 001 — ledger backfill + use_by_date normalization.

Run once per environment (dev first) AFTER the ledger table exists. Idempotent:
re-running makes no further changes. It:

1. Normalizes every item's ``use_by_date`` to date-only ``YYYY-MM-DD`` (only
   rewrites values that still carry a time component).
2. Backfills the ledger with a current-state snapshot: one ``item_created`` event
   per active item and one ``task_completed`` event per task that has a
   ``last_completed_at`` — but only when the entity has no ledger events yet, so
   re-runs don't duplicate.

Soft delete needs no backfill: an absent ``deleted_at`` already means "active".
The old ``item_tags`` table (if still present) is left untouched; Terraform
removes it in the analytics/infra phase.

Table names come from the same ``*_TABLE_NAME`` environment variables the Lambda
uses, so point the env at the target environment before running:

    ITEMS_TABLE_NAME=prod-use1-pantry-table-items \\
    TASKS_TABLE_NAME=prod-use1-pantry-table-tasks \\
    LEDGER_TABLE_NAME=prod-use1-pantry-table-ledger \\
    python -I migrations/001_ledger_and_softdelete.py [--endpoint-url URL] [--dry-run]
"""

import argparse
import os
import sys

import boto3
from boto3.dynamodb.conditions import Key

# Allow running from the backend/ dir (so ``import models`` resolves).
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from models import (  # noqa: E402
    LedgerEvent, now_iso,
    ENTITY_ITEM, ENTITY_TASK, EVENT_ITEM_CREATED, EVENT_TASK_COMPLETED,
)


def _paginate(operation, **kwargs):
    items = []
    resp = operation(**kwargs)
    items.extend(resp.get("Items", []))
    while "LastEvaluatedKey" in resp:
        resp = operation(**kwargs, ExclusiveStartKey=resp["LastEvaluatedKey"])
        items.extend(resp.get("Items", []))
    return items


def _date_only(value):
    """Return the date component of an ISO value, or None if already date-only."""
    if not value or ("T" not in value and len(value) == 10):
        return None
    # Take the date portion before any time separator.
    return value.split("T", 1)[0]


def _has_ledger_events(ledger_table, user_id, entity_type, entity_id):
    resp = ledger_table.query(
        IndexName="EntityIndex",
        KeyConditionExpression=Key("user_id").eq(user_id)
        & Key("entity_sk").begins_with(f"{entity_type}#{entity_id}#"),
        Limit=1,
    )
    return bool(resp.get("Items"))


def migrate(dynamodb, dry_run=False):
    items_table = dynamodb.Table(os.environ["ITEMS_TABLE_NAME"])
    tasks_table = dynamodb.Table(os.environ["TASKS_TABLE_NAME"])
    ledger_table = dynamodb.Table(os.environ["LEDGER_TABLE_NAME"])

    stats = {"dates_normalized": 0, "item_events": 0, "task_events": 0}

    # --- Items: normalize use_by_date + backfill item_created ----------------
    for item in _paginate(items_table.scan):
        user_id = item["user_id"]
        item_id = item["item_id"]

        new_date = _date_only(item.get("use_by_date"))
        if new_date is not None:
            stats["dates_normalized"] += 1
            if not dry_run:
                items_table.update_item(
                    Key={"user_id": user_id, "item_id": item_id},
                    UpdateExpression="SET use_by_date = :d",
                    ExpressionAttributeValues={":d": new_date},
                )

        # Backfill only active items, and only once.
        if item.get("deleted_at"):
            continue
        if _has_ledger_events(ledger_table, user_id, ENTITY_ITEM, item_id):
            continue
        stats["item_events"] += 1
        if not dry_run:
            event = LedgerEvent.create(
                user_id, ENTITY_ITEM, item_id, EVENT_ITEM_CREATED,
                payload={
                    "name": item.get("name"),
                    "location_id": item.get("location_id"),
                    "category_id": item.get("category_id"),
                    "dimensions": item.get("dimensions", []),
                    "backfill": True,
                },
                occurred_at=item.get("created_at") or now_iso(),
            )
            ledger_table.put_item(Item=event.to_dict())

    # --- Tasks: backfill a completion event for already-completed tasks ------
    for task in _paginate(tasks_table.scan):
        if not task.get("last_completed_at") or task.get("deleted_at"):
            continue
        user_id = task["user_id"]
        task_id = task["task_id"]
        if _has_ledger_events(ledger_table, user_id, ENTITY_TASK, task_id):
            continue
        stats["task_events"] += 1
        if not dry_run:
            event = LedgerEvent.create(
                user_id, ENTITY_TASK, task_id, EVENT_TASK_COMPLETED,
                payload={
                    "name": task.get("name"),
                    "tags": task.get("tags", []),
                    "recurrence_type": task.get("recurrence_type", "none"),
                    "answer_mode": task.get("answer_mode", "checkbox"),
                    "decision": task.get("last_decision"),
                    "window": task.get("last_completed_window"),
                    "backfill": True,
                },
                occurred_at=task["last_completed_at"],
            )
            ledger_table.put_item(Item=event.to_dict())

    return stats


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--endpoint-url", help="DynamoDB endpoint (local dev)")
    parser.add_argument("--dry-run", action="store_true", help="Report without writing")
    args = parser.parse_args()

    kwargs = {}
    if args.endpoint_url:
        kwargs["endpoint_url"] = args.endpoint_url
    dynamodb = boto3.resource("dynamodb", **kwargs)

    stats = migrate(dynamodb, dry_run=args.dry_run)
    prefix = "[dry-run] would apply" if args.dry_run else "applied"
    print(
        f"Migration 001 {prefix}: "
        f"{stats['dates_normalized']} use_by_date normalized, "
        f"{stats['item_events']} item_created, "
        f"{stats['task_events']} task_completed backfilled."
    )


if __name__ == "__main__":
    main()
