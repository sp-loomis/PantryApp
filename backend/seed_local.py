"""
Seed the Tier-1 local DynamoDB with sample locations and items.

Creates the three tables in DynamoDB Local (if absent) and populates them with a
realistic starter inventory owned by the dev user, through the real service layer
so tags/dimensions are denormalized exactly as the API would.

Run (after ``docker compose up -d``):
    python backend/seed_local.py
"""

import os
from datetime import datetime, timedelta, timezone

import boto3
from botocore.exceptions import ClientError

from local_schema import (
    ITEMS_TABLE,
    ITEM_TAGS_TABLE,
    LOCATIONS_TABLE,
    TASKS_TABLE,
    REPORTS_TABLE,
    MESSAGES_TABLE,
    TABLE_NAMES,
    create_tables,
)

DYNAMODB_ENDPOINT = os.environ.get("DYNAMODB_ENDPOINT", "http://localhost:8001")
DEV_USER_ID = os.environ.get("DEV_USER_ID", "dev-user")

os.environ.setdefault("AWS_DEFAULT_REGION", "us-east-1")
os.environ.setdefault("AWS_ACCESS_KEY_ID", "local")
os.environ.setdefault("AWS_SECRET_ACCESS_KEY", "local")
for env_name, table_name in TABLE_NAMES.items():
    os.environ.setdefault(env_name, table_name)


def _iso_in_days(days: int) -> str:
    return (datetime.now(timezone.utc) + timedelta(days=days)).isoformat()


def main() -> None:
    dynamodb = boto3.resource("dynamodb", endpoint_url=DYNAMODB_ENDPOINT)

    try:
        create_tables(dynamodb)
        print("Created tables.")
    except ClientError as err:
        if err.response["Error"]["Code"] == "ResourceInUseException":
            print("Tables already exist — reusing.")
        else:
            raise

    # Import services AFTER env/tables are ready.
    from services import (
        ItemService, LocationService, TaskService,
        ReportService, MessageService, ReportGenerator,
    )

    location_service = LocationService(dynamodb.Table(LOCATIONS_TABLE))
    item_service = ItemService(
        dynamodb.Table(ITEMS_TABLE), dynamodb.Table(ITEM_TAGS_TABLE)
    )
    task_service = TaskService(dynamodb.Table(TASKS_TABLE))
    report_service = ReportService(dynamodb.Table(REPORTS_TABLE))
    message_service = MessageService(dynamodb.Table(MESSAGES_TABLE))
    report_generator = ReportGenerator(
        report_service, message_service, task_service, item_service
    )

    # Idempotency: seeding creates fresh (uuid-keyed) rows each run, so re-running
    # would duplicate. Inventory/tasks and reports have independent guards so a
    # volume seeded before the reports feature still gets sample reports added.
    # To fully reset: `docker compose down -v` then re-run this script.
    if location_service.list_locations(DEV_USER_ID):
        print(f"User '{DEV_USER_ID}' already has inventory — skipping locations/items/tasks.")
    else:
        _seed_inventory(location_service, item_service, task_service)

    _seed_reports(report_service, report_generator)


def _seed_inventory(location_service, item_service, task_service) -> None:
    pantry = location_service.create_location(
        DEV_USER_ID, "Kitchen Pantry", "Dry goods and canned food"
    )
    fridge = location_service.create_location(
        DEV_USER_ID, "Fridge", "Cold storage"
    )
    print(f"Created locations: {pantry['location_id']}, {fridge['location_id']}")

    samples = [
        # name, location_id, dimensions, use_by_date, tags, notes
        ("All-Purpose Flour", pantry["location_id"],
         [{"dimension_type": "weight", "value": 2, "unit": "kg"}], None, ["baking", "staple"], ""),
        ("Olive Oil", pantry["location_id"],
         [{"dimension_type": "volume", "value": 750, "unit": "ml"}], None, ["oil", "staple"], "Extra virgin"),
        ("Canned Tomatoes", pantry["location_id"],
         [{"dimension_type": "weight", "value": 400, "unit": "g"}], _iso_in_days(400), ["canned"], ""),
        ("Pasta", pantry["location_id"], [], None, ["staple", "dinner"], "A box of penne"),
        ("Milk", fridge["location_id"],
         [{"dimension_type": "volume", "value": 1, "unit": "l"}], _iso_in_days(5), ["dairy"], ""),
        ("Cheddar Cheese", fridge["location_id"],
         [{"dimension_type": "weight", "value": 250, "unit": "g"}], _iso_in_days(20), ["dairy"], ""),
        ("Leftover Soup", fridge["location_id"], [], _iso_in_days(2), ["leftovers"], "Eat soon!"),
    ]

    for name, location_id, dimensions, use_by, tags, notes in samples:
        created = item_service.create_item(
            DEV_USER_ID, name, location_id,
            dimensions=dimensions, use_by_date=use_by, tags=tags, notes=notes,
        )
        print(f"  + {created['name']} ({created['item_id']})")

    print(f"\nSeeded {len(samples)} items for user '{DEV_USER_ID}'.")

    # Sample tasks: a mix of recurring chores and one-shot deadlines.
    task_samples = [
        # name, notes, tags, recurrence_type, interval, anchor, due, graceful
        ("Water the garden", "", ["garden"], "daily", None, None, None, True),
        ("Feed the chickens", "Morning and evening", ["animals"], "daily", None, None, None, True),
        ("Take out compost", "", ["kitchen"], "weekly", None, None, None, True),
        ("Deep clean the coop", "", ["animals"], "interval", 14, None, None, True),
        ("Renew tool insurance", "", ["admin"], "none", None, None, _iso_in_days(5), True),
        ("Return library books", "", [], "none", None, None, _iso_in_days(-2), True),
    ]

    for name, notes, tags, rtype, interval, anchor, due, graceful in task_samples:
        created = task_service.create_task(
            DEV_USER_ID, name, notes=notes, tags=tags,
            recurrence_type=rtype, recurrence_interval=interval,
            anchor_date=anchor, due_date=due, graceful=graceful, tz="UTC",
        )
        print(f"  * {created['name']} ({created['task_id']})")

    print(f"Seeded {len(task_samples)} tasks for user '{DEV_USER_ID}'.")


def _seed_reports(report_service, report_generator) -> None:
    if report_service.list_reports(DEV_USER_ID):
        print(f"User '{DEV_USER_ID}' already has reports — skipping reports/messages.")
        return

    # Sample reports: a daily task digest and a weekly inventory review.
    report_samples = [
        {
            "name": "Daily chore digest",
            "schedule": {"frequency": "daily", "time_of_day": "07:00", "tz": "UTC"},
            "sections": [
                {"type": "custom_message", "heading": "Good morning",
                 "config": {"text": "Here's what needs doing today."}},
                {"type": "task_query", "heading": "Active chores",
                 "config": {"status": "active"}},
            ],
        },
        {
            "name": "Weekly pantry review",
            "schedule": {"frequency": "weekly", "weekday": 0, "time_of_day": "18:00", "tz": "UTC"},
            "sections": [
                {"type": "item_query", "heading": "Dairy on hand",
                 "config": {"tags": ["dairy"]}},
                {"type": "custom_message", "heading": "Reminder",
                 "config": {"text": "Check expiry dates before shopping."}},
            ],
        },
    ]

    reports = []
    for spec in report_samples:
        created = report_service.create_report(
            DEV_USER_ID, spec["name"], spec["schedule"], sections=spec["sections"],
        )
        reports.append(created)
        print(f"  ~ {created['name']} ({created['report_id']})")

    print(f"Seeded {len(report_samples)} reports for user '{DEV_USER_ID}'.")

    # Generate one message per report so the log/toolbar have sample content.
    for report in reports:
        message = report_generator.generate(report, tz="UTC")
        print(f"  # message {message['message_id']} from '{report['name']}'")

    print(f"Seeded {len(reports)} messages for user '{DEV_USER_ID}'.")


if __name__ == "__main__":
    main()
