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
    from services import ItemService, LocationService

    location_service = LocationService(dynamodb.Table(LOCATIONS_TABLE))
    item_service = ItemService(
        dynamodb.Table(ITEMS_TABLE), dynamodb.Table(ITEM_TAGS_TABLE)
    )

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


if __name__ == "__main__":
    main()
