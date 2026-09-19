"""
Service layer for the Pantry App.
Handles business logic and DynamoDB operations.
"""

import base64
import hashlib
import hmac
import json
import secrets as _secrets
import time
import urllib.parse
import urllib.request
from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta, timezone
from decimal import Decimal

from boto3.dynamodb.conditions import Key, Attr
from botocore.exceptions import ClientError
from aws_lambda_powertools import Logger

from models import Item, Location, Category, ItemTag, Task, Report, Message, SlackConnection
from dimensions import (
    Dimension, DimensionType, validate_dimension, validate_category_measure,
    aggregate_dimensions, aggregate_by_category,
)
from search import match_name, DEFAULT_MIN_SCORE
from recurrence import (
    RECURRENCE_TYPES, TRIGGER_ON, TRIGGER_DEADLINES, compute_status,
    current_window_key, completion_window_key, local_now, resolve_tasks,
)
from schedules import compute_next_run, validate_schedule
from report_sections import render_section, validate_sections
from report_conditions import validate_trigger, evaluate_trigger
from slack_blocks import render_message_blocks

logger = Logger(child=True)

# Upper bound on how many identical copies a single create request may add.
# Guards against accidental/abusive bulk writes while comfortably covering
# realistic pantry restocking (e.g. a case of cans).
COPIES_MAX = 100


def _now_iso() -> str:
    """Return the current UTC time as an ISO-8601 string."""
    return datetime.now(timezone.utc).isoformat()


def _validate_delivery(delivery: Any) -> None:
    """Validate a report's optional delivery config, raising ValueError.

    Empty/None means in-app only. A ``slack`` destination requires non-empty
    string ``connection_id`` and ``channel_id``.
    """
    if not delivery:
        return
    if not isinstance(delivery, dict):
        raise ValueError("delivery must be an object")
    slack = delivery.get("slack")
    if slack is not None:
        if not isinstance(slack, dict):
            raise ValueError("delivery.slack must be an object")
        for key in ("connection_id", "channel_id"):
            value = slack.get(key)
            if not value or not isinstance(value, str):
                raise ValueError(f"delivery.slack requires a non-empty '{key}'")


def _parse_iso(value: str) -> datetime:
    """Parse an ISO-8601 string to a timezone-aware datetime (assume UTC if naive).

    Normalizing to aware datetimes lets us compare date-only (``2026-09-09``) and
    full-timestamp (``2026-09-09T12:00:00+00:00``) values correctly, instead of the
    prefix-sensitive lexicographic string compare they'd otherwise get.
    """
    dt = datetime.fromisoformat(value)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt


def _floats_to_decimal(obj: Any) -> Any:
    """Recursively convert floats to Decimal for DynamoDB writes.

    Rendered report sections contain arbitrary nested content (e.g. item
    dimension values deserialized to float), and DynamoDB rejects float. This
    walks lists/dicts and coerces every float via str() to avoid binary drift.
    """
    if isinstance(obj, float):
        return Decimal(str(obj))
    if isinstance(obj, list):
        return [_floats_to_decimal(v) for v in obj]
    if isinstance(obj, dict):
        return {k: _floats_to_decimal(v) for k, v in obj.items()}
    return obj


def _decimals_to_float(obj: Any) -> Any:
    """Recursively convert Decimals back to float/int for JSON responses."""
    if isinstance(obj, Decimal):
        # Preserve whole numbers as int, everything else as float.
        return int(obj) if obj == obj.to_integral_value() else float(obj)
    if isinstance(obj, list):
        return [_decimals_to_float(v) for v in obj]
    if isinstance(obj, dict):
        return {k: _decimals_to_float(v) for k, v in obj.items()}
    return obj


def _serialize_dimensions(dimensions: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Return a copy of dimensions with values coerced to Decimal for DynamoDB."""
    serialized = []
    for dim in dimensions:
        d = dict(dim)
        if "value" in d:
            d["value"] = Decimal(str(d["value"]))
        serialized.append(d)
    return serialized


class LocationService:
    """Service for managing storage locations."""

    def __init__(self, table):
        self.table = table

    def create_location(self, user_id: str, name: str, description: str = "") -> Dict[str, Any]:
        """Create a new storage location for a user."""
        location = Location.create(user_id=user_id, name=name, description=description)

        self.table.put_item(Item=location.to_dict())
        logger.info(f"Created location: {location.location_id} for user: {user_id}")

        return location.to_dict()

    def get_location(self, user_id: str, location_id: str) -> Optional[Dict[str, Any]]:
        """Get a storage location by ID for a specific user."""
        response = self.table.get_item(Key={"user_id": user_id, "location_id": location_id})
        return response.get("Item")

    def list_locations(self, user_id: str) -> List[Dict[str, Any]]:
        """List all storage locations for a specific user."""
        response = self.table.query(
            KeyConditionExpression=Key("user_id").eq(user_id)
        )
        return response.get("Items", [])

    def update_location(self, user_id: str, location_id: str, updates: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Update a storage location for a specific user."""
        location = self.get_location(user_id, location_id)
        if not location:
            return None

        update_expr = "SET updated_at = :updated_at"
        expr_values = {":updated_at": _now_iso()}
        expr_names = {}

        if "name" in updates:
            update_expr += ", #n = :name"
            expr_values[":name"] = updates["name"]
            expr_names["#n"] = "name"

        if "description" in updates:
            update_expr += ", description = :description"
            expr_values[":description"] = updates["description"]

        update_kwargs = {
            "Key": {"user_id": user_id, "location_id": location_id},
            "UpdateExpression": update_expr,
            "ExpressionAttributeValues": expr_values,
            "ReturnValues": "ALL_NEW",
        }
        if expr_names:
            update_kwargs["ExpressionAttributeNames"] = expr_names

        response = self.table.update_item(**update_kwargs)

        logger.info(f"Updated location: {location_id} for user: {user_id}")
        return response.get("Attributes")

    def delete_location(self, user_id: str, location_id: str) -> bool:
        """Delete a storage location for a specific user.

        Returns False when the location does not exist so callers can surface a
        404 (DynamoDB's delete_item succeeds unconditionally, so we must check
        existence first). A genuine delete failure propagates (surfaced as 500)
        rather than being swallowed into a misleading 404.
        """
        if not self.get_location(user_id, location_id):
            return False
        self.table.delete_item(Key={"user_id": user_id, "location_id": location_id})
        logger.info(f"Deleted location: {location_id} for user: {user_id}")
        return True


class CategoryService:
    """Service for managing item categories.

    A category declares one ``measure_type`` and (for weight/volume) a
    ``preferred_unit``. Items reference a category via ``category_id``. Deleting a
    category clears that reference on its items so aggregation never trips over a
    dangling id.
    """

    def __init__(self, table, items_table=None):
        self.table = table
        # Optional handle to the items table, used only to clear category_id off
        # an item on category deletion (via the CategoryIndex GSI).
        self.items_table = items_table

    def create_category(
        self,
        user_id: str,
        name: str,
        measure_type: str,
        preferred_unit: Optional[str] = None,
        description: str = "",
    ) -> Dict[str, Any]:
        """Create a category, validating its measure_type / preferred_unit pair."""
        validate_category_measure(measure_type, preferred_unit)
        category = Category.create(
            user_id=user_id,
            name=name,
            measure_type=measure_type,
            preferred_unit=preferred_unit or None,
            description=description,
        )
        self.table.put_item(Item=category.to_dict())
        logger.info(f"Created category: {category.category_id} for user: {user_id}")
        return category.to_dict()

    def get_category(self, user_id: str, category_id: str) -> Optional[Dict[str, Any]]:
        """Get a category by ID for a specific user."""
        response = self.table.get_item(Key={"user_id": user_id, "category_id": category_id})
        return response.get("Item")

    def list_categories(self, user_id: str) -> List[Dict[str, Any]]:
        """List all categories for a specific user."""
        response = self.table.query(KeyConditionExpression=Key("user_id").eq(user_id))
        return response.get("Items", [])

    def update_category(
        self, user_id: str, category_id: str, updates: Dict[str, Any]
    ) -> Optional[Dict[str, Any]]:
        """Update a category for a specific user.

        Re-validates the measure_type / preferred_unit pair against the merged
        result so a category never ends up with an inconsistent measure.
        """
        category = self.get_category(user_id, category_id)
        if not category:
            return None

        # Validate the merged measure/unit before writing.
        measure_type = updates.get("measure_type", category.get("measure_type"))
        preferred_unit = (
            updates["preferred_unit"] if "preferred_unit" in updates
            else category.get("preferred_unit")
        )
        if "measure_type" in updates or "preferred_unit" in updates:
            validate_category_measure(measure_type, preferred_unit or None)

        set_parts = ["updated_at = :updated_at"]
        remove_parts = []
        expr_values = {":updated_at": _now_iso()}
        expr_names = {}

        if "name" in updates:
            set_parts.append("#n = :name")
            expr_values[":name"] = updates["name"]
            expr_names["#n"] = "name"
        if "description" in updates:
            set_parts.append("description = :description")
            expr_values[":description"] = updates["description"]
        if "measure_type" in updates:
            set_parts.append("measure_type = :measure_type")
            expr_values[":measure_type"] = updates["measure_type"]
        if "measure_type" in updates or "preferred_unit" in updates:
            # Keep preferred_unit consistent with the (possibly new) measure_type.
            if preferred_unit:
                set_parts.append("preferred_unit = :preferred_unit")
                expr_values[":preferred_unit"] = preferred_unit
            else:
                set_parts.append("preferred_unit = :preferred_unit")
                expr_values[":preferred_unit"] = None

        update_expr = "SET " + ", ".join(set_parts)
        if remove_parts:
            update_expr += " REMOVE " + ", ".join(remove_parts)

        update_kwargs = {
            "Key": {"user_id": user_id, "category_id": category_id},
            "UpdateExpression": update_expr,
            "ExpressionAttributeValues": expr_values,
            "ReturnValues": "ALL_NEW",
        }
        if expr_names:
            update_kwargs["ExpressionAttributeNames"] = expr_names

        response = self.table.update_item(**update_kwargs)
        logger.info(f"Updated category: {category_id} for user: {user_id}")
        return response.get("Attributes")

    def delete_category(self, user_id: str, category_id: str) -> bool:
        """Delete a category, clearing it off any items that reference it.

        Returns False when the category does not exist (for a 404).
        """
        if not self.get_category(user_id, category_id):
            return False
        self._clear_category_from_items(user_id, category_id)
        self.table.delete_item(Key={"user_id": user_id, "category_id": category_id})
        logger.info(f"Deleted category: {category_id} for user: {user_id}")
        return True

    def _clear_category_from_items(self, user_id: str, category_id: str) -> None:
        """Remove ``category_id`` from every item that references this category."""
        if self.items_table is None:
            return
        response = self.items_table.query(
            IndexName="CategoryIndex",
            KeyConditionExpression=Key("user_id").eq(user_id) & Key("category_id").eq(category_id),
        )
        items = response.get("Items", [])
        while "LastEvaluatedKey" in response:
            response = self.items_table.query(
                IndexName="CategoryIndex",
                KeyConditionExpression=Key("user_id").eq(user_id) & Key("category_id").eq(category_id),
                ExclusiveStartKey=response["LastEvaluatedKey"],
            )
            items.extend(response.get("Items", []))
        for item in items:
            # category_id backs a sparse GSI, so clearing it must REMOVE the attribute.
            self.items_table.update_item(
                Key={"user_id": user_id, "item_id": item["item_id"]},
                UpdateExpression="SET updated_at = :updated_at REMOVE category_id",
                ExpressionAttributeValues={":updated_at": _now_iso()},
            )


class TagService:
    """Service for managing the item-tag reverse index (items-by-tag lookups)."""

    def __init__(self, table):
        self.table = table

    def add_tags_to_item(self, user_id: str, item_id: str, tags: List[str]) -> None:
        """Add reverse-index rows for tags on an item for a specific user."""
        for tag in tags:
            item_tag = ItemTag.create(user_id=user_id, tag_name=tag.lower(), item_id=item_id)
            self.table.put_item(Item=item_tag.to_dict())

        logger.info(f"Added {len(tags)} tags to item: {item_id} for user: {user_id}")

    def remove_tags_from_item(self, user_id: str, item_id: str, tags: List[str]) -> None:
        """Remove reverse-index rows for tags on an item for a specific user."""
        for tag in tags:
            composite_key = f"tag:{tag.lower()}#item:{item_id}"
            self.table.delete_item(
                Key={"user_id": user_id, "tag_item_composite": composite_key}
            )

        logger.info(f"Removed {len(tags)} tags from item: {item_id} for user: {user_id}")

    def get_items_by_tag(self, user_id: str, tag: str) -> List[str]:
        """Get all item IDs with a specific tag for a specific user."""
        response = self.table.query(
            IndexName="TagIndex",
            KeyConditionExpression=Key("user_id").eq(user_id) & Key("tag_name").eq(tag.lower())
        )
        return [item["item_id"] for item in response.get("Items", [])]

    def list_all_tags(self, user_id: str) -> List[str]:
        """List all distinct tags across a user's inventory."""
        response = self.table.query(
            IndexName="TagIndex",
            KeyConditionExpression=Key("user_id").eq(user_id)
        )
        tags = {item["tag_name"] for item in response.get("Items", [])}
        return sorted(tags)


class ItemService:
    """Service for managing inventory items."""

    def __init__(self, items_table, tags_table, category_service=None):
        self.items_table = items_table
        self.tag_service = TagService(tags_table)
        # Optional CategoryService; enables category assignment + measure-type
        # enforcement on create/update. None disables category validation.
        self.category_service = category_service

    @staticmethod
    def _deserialize_item(item: Dict[str, Any]) -> Dict[str, Any]:
        """Normalize a raw DynamoDB item for API responses.

        Converts Decimal dimension values to float and guarantees a `tags` key.
        """
        if item.get("dimensions"):
            for dim in item["dimensions"]:
                if "value" in dim:
                    dim["value"] = float(dim["value"])
        # Guarantee a stable shape: items stored without dimensions omit the key.
        item.setdefault("dimensions", [])
        item.setdefault("tags", [])
        # category_id is a sparse-index key: absent on storage when unset, but
        # surfaced as None here so responses have a stable shape.
        item.setdefault("category_id", None)
        # use_by_date is a sparse-index key: absent on storage when unset, but
        # surfaced as None here so responses have a stable shape.
        item.setdefault("use_by_date", None)
        return item

    def _batch_get_items(self, user_id: str, item_ids: List[str]) -> List[Dict[str, Any]]:
        """Fetch multiple items by ID in as few round-trips as possible."""
        items: List[Dict[str, Any]] = []
        client = self.items_table.meta.client
        table_name = self.items_table.table_name

        # batch_get_item accepts at most 100 keys per request.
        for start in range(0, len(item_ids), 100):
            chunk = item_ids[start:start + 100]
            request_keys = [{"user_id": user_id, "item_id": iid} for iid in chunk]
            response = client.batch_get_item(
                RequestItems={table_name: {"Keys": request_keys}}
            )
            items.extend(response.get("Responses", {}).get(table_name, []))

            # Retry any unprocessed keys once (rare, but keeps results complete).
            unprocessed = response.get("UnprocessedKeys", {})
            while unprocessed:
                response = client.batch_get_item(RequestItems=unprocessed)
                items.extend(response.get("Responses", {}).get(table_name, []))
                unprocessed = response.get("UnprocessedKeys", {})

        return [self._deserialize_item(item) for item in items]

    def _persist_new_item(self, item: "Item", tags: List[str]) -> Dict[str, Any]:
        """Write one already-built Item (plus its tag reverse-index rows) to storage.

        Shared by the single- and multi-copy create paths so persistence stays
        in one place. Returns the response-shaped (deserialized) item dict.
        """
        # Build a storage-shaped dict (Decimal dimension values) without mutating
        # the response-shaped dict we hand back to the caller.
        storage_dict = item.to_dict()
        if storage_dict.get("dimensions"):
            storage_dict["dimensions"] = _serialize_dimensions(storage_dict["dimensions"])
        # use_by_date backs a sparse GSI: a NULL value is rejected on an index
        # key, so omit the attribute entirely when there is no expiry.
        if storage_dict.get("use_by_date") is None:
            storage_dict.pop("use_by_date", None)
        self.items_table.put_item(Item=storage_dict)

        if tags:
            self.tag_service.add_tags_to_item(item.user_id, item.item_id, tags)

        logger.info(f"Created item: {item.item_id} for user: {item.user_id}")
        return self._deserialize_item(item.to_dict())

    def create_item(
        self,
        user_id: str,
        name: str,
        location_id: str,
        dimensions: List[Dict[str, Any]] = None,
        use_by_date: Optional[str] = None,
        tags: List[str] = None,
        category_id: Optional[str] = None,
        notes: str = "",
        copies: int = 1
    ):
        """Create one or more inventory items with optional dimensions.

        ``copies`` creates that many distinct item entries (each its own
        ``item_id``) sharing identical fields. Returns a single item dict when
        ``copies == 1`` (the default, backward-compatible shape) and a list of
        item dicts when ``copies > 1``.
        """
        copies = self._validate_copies(copies)
        dimensions = dimensions or []
        tags = [t.lower() for t in (tags or [])]

        self._validate_dimensions(dimensions)
        self._validate_category(user_id, category_id, dimensions)

        created = []
        for _ in range(copies):
            item = Item.create(
                user_id=user_id,
                name=name,
                location_id=location_id,
                dimensions=dimensions,
                tags=tags,
                category_id=category_id,
                use_by_date=use_by_date,
                notes=notes
            )
            created.append(self._persist_new_item(item, tags))

        return created[0] if copies == 1 else created

    def get_item(self, user_id: str, item_id: str) -> Optional[Dict[str, Any]]:
        """Get an item by ID for a specific user."""
        response = self.items_table.get_item(
            Key={"user_id": user_id, "item_id": item_id}
        )
        item = response.get("Item")
        if not item:
            return None
        return self._deserialize_item(item)

    def list_all_items(self, user_id: str) -> List[Dict[str, Any]]:
        """List all items for a specific user."""
        response = self.items_table.query(
            KeyConditionExpression=Key("user_id").eq(user_id)
        )
        return [self._deserialize_item(item) for item in response.get("Items", [])]

    def get_items_by_location(self, user_id: str, location_id: str) -> List[Dict[str, Any]]:
        """Get all items in a specific location for a specific user."""
        response = self.items_table.query(
            IndexName="LocationIndex",
            KeyConditionExpression=Key("user_id").eq(user_id) & Key("location_id").eq(location_id)
        )
        return [self._deserialize_item(item) for item in response.get("Items", [])]

    def get_items_by_category(self, user_id: str, category_id: str) -> List[Dict[str, Any]]:
        """Get all items in a specific category for a specific user."""
        response = self.items_table.query(
            IndexName="CategoryIndex",
            KeyConditionExpression=Key("user_id").eq(user_id) & Key("category_id").eq(category_id)
        )
        return [self._deserialize_item(item) for item in response.get("Items", [])]

    def get_items_by_tag(self, user_id: str, tag: str) -> List[Dict[str, Any]]:
        """Get all items with a specific tag for a specific user."""
        item_ids = self.tag_service.get_items_by_tag(user_id, tag)
        if not item_ids:
            return []
        return self._batch_get_items(user_id, item_ids)

    def list_items(
        self,
        user_id: str,
        location_id: Optional[str] = None,
        tag: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """List items, optionally narrowing by location and/or tag.

        Filters **stack** (AND): passing both returns the intersection. Queries the
        more selective index for the primary filter and applies the remaining one
        in memory against the item's denormalized ``tags`` (same shape as
        ``get_expiring_items`` and ``search_items``).
        """
        if location_id:
            items = self.get_items_by_location(user_id, location_id)
        elif tag:
            items = self.get_items_by_tag(user_id, tag)
        else:
            items = self.list_all_items(user_id)

        # Second filter applied in memory when both are present.
        if location_id and tag:
            wanted = tag.lower()
            items = [item for item in items if wanted in item.get("tags", [])]

        return items

    def get_expiring_items(self, user_id: str, location_id: Optional[str] = None, days: int = 7) -> List[Dict[str, Any]]:
        """Get items expiring within the specified number of days for a specific user."""
        cutoff_date = (datetime.now(timezone.utc) + timedelta(days=days)).isoformat()

        # UseByDateIndex is sparse: only items that have a use_by_date appear.
        response = self.items_table.query(
            IndexName="UseByDateIndex",
            KeyConditionExpression=Key("user_id").eq(user_id) & Key("use_by_date").lte(cutoff_date)
        )
        items = [self._deserialize_item(item) for item in response.get("Items", [])]

        if location_id:
            items = [item for item in items if item.get("location_id") == location_id]

        return items

    def update_item(self, user_id: str, item_id: str, updates: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Update an item, including dimensions and tags, for a specific user."""
        item = self.get_item(user_id, item_id)
        if not item:
            return None

        set_parts = ["updated_at = :updated_at"]
        remove_parts = []
        expr_values = {":updated_at": _now_iso()}
        expr_names = {}

        if "name" in updates:
            set_parts.append("#n = :name")
            expr_values[":name"] = updates["name"]
            expr_names["#n"] = "name"

        if "location_id" in updates:
            set_parts.append("location_id = :location_id")
            expr_values[":location_id"] = updates["location_id"]

        if "dimensions" in updates:
            dimensions = updates["dimensions"]
            self._validate_dimensions(dimensions)
            set_parts.append("dimensions = :dimensions")
            expr_values[":dimensions"] = _serialize_dimensions(dimensions)

        if "use_by_date" in updates:
            # use_by_date backs a sparse GSI, so clearing it must REMOVE the
            # attribute rather than SET it to NULL.
            if updates["use_by_date"] is None:
                remove_parts.append("use_by_date")
            else:
                set_parts.append("use_by_date = :use_by_date")
                expr_values[":use_by_date"] = updates["use_by_date"]

        if "notes" in updates:
            set_parts.append("notes = :notes")
            expr_values[":notes"] = updates["notes"]

        # Tags are denormalized onto the item and mirrored into the reverse index.
        if "tags" in updates:
            new_tags = sorted({t.lower() for t in updates["tags"]})
            old_tags = set(item.get("tags", []))

            set_parts.append("#tags = :tags")
            expr_values[":tags"] = new_tags
            expr_names["#tags"] = "tags"

            tags_to_add = set(new_tags) - old_tags
            tags_to_remove = old_tags - set(new_tags)
            if tags_to_add:
                self.tag_service.add_tags_to_item(user_id, item_id, list(tags_to_add))
            if tags_to_remove:
                self.tag_service.remove_tags_from_item(user_id, item_id, list(tags_to_remove))

        # Category assignment enforces the measure-type constraint against the
        # item's effective dimensions (the incoming set if updated, else stored).
        effective_dimensions = (
            updates["dimensions"] if "dimensions" in updates else item.get("dimensions", [])
        )
        if "category_id" in updates:
            new_category_id = updates["category_id"]
            if new_category_id:
                self._validate_category(user_id, new_category_id, effective_dimensions)
                set_parts.append("category_id = :category_id")
                expr_values[":category_id"] = new_category_id
            else:
                # category_id backs a sparse GSI: clear it by REMOVING the attribute.
                remove_parts.append("category_id")
        elif "dimensions" in updates and item.get("category_id"):
            # Dimensions changed on a categorized item: re-check the constraint so
            # the item cannot drop the category's required measure type.
            self._validate_category(user_id, item["category_id"], effective_dimensions)

        update_expr = "SET " + ", ".join(set_parts)
        if remove_parts:
            update_expr += " REMOVE " + ", ".join(remove_parts)

        update_kwargs = {
            "Key": {"user_id": user_id, "item_id": item_id},
            "UpdateExpression": update_expr,
            "ExpressionAttributeValues": expr_values,
            "ReturnValues": "ALL_NEW",
        }
        if expr_names:
            update_kwargs["ExpressionAttributeNames"] = expr_names

        response = self.items_table.update_item(**update_kwargs)

        attributes = response.get("Attributes")
        if not attributes:
            # ALL_NEW returns the row after a successful update; an empty result
            # signals failure, not a valid empty item.
            return None

        logger.info(f"Updated item: {item_id} for user: {user_id}")
        return self._deserialize_item(attributes)

    def delete_item(self, user_id: str, item_id: str) -> bool:
        """Delete an item for a specific user."""
        item = self.get_item(user_id, item_id)
        if not item:
            return False

        # Not-found is handled above; a genuine failure below must propagate
        # (surfaced as 500) rather than be swallowed into a misleading 404.
        # Remove reverse-index rows for the item's tags (read off the item).
        tags = item.get("tags", [])
        if tags:
            self.tag_service.remove_tags_from_item(user_id, item_id, tags)

        self.items_table.delete_item(
            Key={"user_id": user_id, "item_id": item_id}
        )

        logger.info(f"Deleted item: {item_id} for user: {user_id}")
        return True

    # ------------------------------------------------------------------
    # Tag management (per-item)
    # ------------------------------------------------------------------

    def get_item_tags(self, user_id: str, item_id: str) -> Optional[List[str]]:
        """Get the tags for a specific item, or None if the item does not exist."""
        item = self.get_item(user_id, item_id)
        if item is None:
            return None
        return item.get("tags", [])

    def add_item_tags(self, user_id: str, item_id: str, tags: List[str]) -> Optional[List[str]]:
        """Add tags to an item, returning the item's full tag list (or None if missing)."""
        item = self.get_item(user_id, item_id)
        if item is None:
            return None

        new_tags = sorted(set(item.get("tags", [])) | {t.lower() for t in tags})
        self.update_item(user_id, item_id, {"tags": new_tags})
        return new_tags

    def remove_item_tag(self, user_id: str, item_id: str, tag: str) -> Optional[List[str]]:
        """Remove a single tag from an item, returning the remaining tags (or None if missing)."""
        item = self.get_item(user_id, item_id)
        if item is None:
            return None

        remaining = sorted(set(item.get("tags", [])) - {tag.lower()})
        self.update_item(user_id, item_id, {"tags": remaining})
        return remaining

    def list_all_tags(self, user_id: str) -> List[str]:
        """List all distinct tags across a user's inventory."""
        return self.tag_service.list_all_tags(user_id)

    # ------------------------------------------------------------------
    # Search & aggregation
    # ------------------------------------------------------------------

    def search_items(
        self,
        user_id: str,
        name: Optional[str] = None,
        location_id: Optional[str] = None,
        tags: List[str] = None,
        use_by_date_start: Optional[str] = None,
        use_by_date_end: Optional[str] = None,
        min_score: float = DEFAULT_MIN_SCORE
    ) -> List[Dict[str, Any]]:
        """Advanced search for items for a specific user.

        When ``name`` is given, items are fuzzy-matched by name (see
        ``search.match_name``): each match carries a ``match`` object with a
        relevance score and highlight spans, and results are ranked by score.
        ``location_id``, ``tags`` and the date range are applied as filters on
        top, independently of ``name`` (so "milk in the fridge" narrows by both).
        """
        if name:
            # Fuzzy name search loads the user's partition and ranks in memory.
            items = []
            for item in self.list_all_items(user_id):
                match = match_name(item.get("name", ""), name, min_score)
                if match is None:
                    continue
                item["match"] = match
                items.append(item)
            items.sort(key=lambda i: i["match"]["score"], reverse=True)
        elif location_id:
            items = self.get_items_by_location(user_id, location_id)
        else:
            items = self.list_all_items(user_id)

        # Structural filters apply regardless of whether a name query ran.
        if location_id:
            items = [item for item in items if item.get("location_id") == location_id]

        if tags:
            # AND semantics: an item must carry every requested tag.
            wanted = {t.lower() for t in tags}
            items = [
                item for item in items
                if wanted <= set(item.get("tags", []))
            ]

        if use_by_date_start or use_by_date_end:
            start = _parse_iso(use_by_date_start) if use_by_date_start else None
            end = _parse_iso(use_by_date_end) if use_by_date_end else None

            def _in_range(item: Dict[str, Any]) -> bool:
                raw = item.get("use_by_date")
                if not raw:
                    return False
                try:
                    dt = _parse_iso(raw)
                except (TypeError, ValueError):
                    # Skip items with an unparseable stored date rather than erroring.
                    return False
                if start and dt < start:
                    return False
                if end and dt > end:
                    return False
                return True

            items = [item for item in items if _in_range(item)]

        return items

    def get_aggregate_stats(
        self,
        user_id: str,
        location_id: Optional[str] = None,
        tag: Optional[str] = None,
        requested_units: Optional[Dict[str, str]] = None
    ) -> Dict[str, Any]:
        """
        Get aggregate statistics for inventory with dimension support for a specific user.

        Args:
            user_id: User ID to filter by
            location_id: Filter by location
            tag: Filter by tag
            requested_units: Optional dict mapping dimension type to desired unit
                            e.g., {"weight": "kg", "volume": "gallon"}
        """
        # location and tag stack (AND) when both are supplied.
        items = self.list_items(user_id, location_id, tag)

        total_items = len(items)
        items_with_expiry = sum(1 for item in items if item.get("use_by_date"))

        # Aggregate dimensions (count/weight/volume) across all matched items.
        aggregated_dimensions = aggregate_dimensions(items)

        # Convert to requested units if specified.
        if requested_units:
            for dim_type_str, target_unit in requested_units.items():
                if dim_type_str in aggregated_dimensions:
                    dim = aggregated_dimensions[dim_type_str]
                    base_value = dim.to_base_unit()
                    dim_type = DimensionType(dim_type_str)
                    aggregated_dimensions[dim_type_str] = Dimension.from_base_unit(
                        dim_type, base_value, target_unit
                    )

        dimensions_dict = {
            dim_type: dim.to_dict()
            for dim_type, dim in aggregated_dimensions.items()
        }

        # Per-category rollup over the same matched items (empty without a
        # CategoryService or when no matched item carries a category).
        by_category = []
        if self.category_service is not None:
            by_category = aggregate_by_category(
                items, self.category_service.list_categories(user_id)
            )

        return {
            "total_items": total_items,
            "items_with_expiry": items_with_expiry,
            "aggregated_dimensions": dimensions_dict,
            "by_category": by_category,
        }

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _validate_copies(copies: Any) -> int:
        """Validate the requested copy count, raising ValueError on any problem.

        Must be an integer in [1, COPIES_MAX]. ``bool`` is rejected explicitly
        (it is an ``int`` subclass) so ``True``/``False`` cannot slip through.
        """
        if isinstance(copies, bool) or not isinstance(copies, int):
            raise ValueError(f"Invalid value for 'copies': must be an integer (got {copies!r})")
        if copies < 1:
            raise ValueError("Invalid value for 'copies': must be at least 1")
        if copies > COPIES_MAX:
            raise ValueError(f"Invalid value for 'copies': must be at most {COPIES_MAX}")
        return copies

    @staticmethod
    def _validate_dimensions(dimensions: List[Dict[str, Any]]) -> None:
        """Validate a list of dimensions, raising ValueError on any problem."""
        if not dimensions:
            return

        for dim in dimensions:
            if not validate_dimension(dim.get("dimension_type"), dim.get("unit")):
                raise ValueError(f"Invalid dimension: {dim}")
            # A dimension needs a numeric value; a missing/non-numeric value would
            # otherwise fail late in Decimal() as an opaque 500.
            value = dim.get("value")
            if isinstance(value, bool) or not isinstance(value, (int, float, Decimal)):
                raise ValueError(f"Invalid dimension value: {dim}")

        dim_types = [d.get("dimension_type") for d in dimensions]
        if len(dim_types) != len(set(dim_types)):
            raise ValueError("Duplicate dimension types not allowed")

    def _validate_category(
        self, user_id: str, category_id: Optional[str], dimensions: List[Dict[str, Any]]
    ) -> None:
        """Validate an item's category assignment, raising ValueError on any problem.

        A ``weight`` / ``volume`` category rolls up the matching dimension, so an
        item may join only if it carries a dimension of that type. A ``count``
        category just counts items (dimension values are irrelevant), so any item
        may join it. No-op when ``category_id`` is unset or no CategoryService is
        wired.
        """
        if not category_id or self.category_service is None:
            return
        category = self.category_service.get_category(user_id, category_id)
        if not category:
            raise ValueError(f"Category not found: {category_id}")
        measure_type = category.get("measure_type")
        if measure_type == DimensionType.COUNT.value:
            return
        have_types = {d.get("dimension_type") for d in (dimensions or [])}
        if measure_type not in have_types:
            raise ValueError(
                f"item in category '{category.get('name', category_id)}' must have a "
                f"{measure_type} dimension"
            )


class TaskService:
    """Service for managing tasks/chores (one-shot and recurring).

    Recurring tasks are stored as a single row plus a rule; their status is
    computed on read via ``recurrence.compute_status`` from the caller's
    timezone. No occurrence rows, no history, no scheduled cleanup — see
    ``recurrence.py`` for the "graceful disappearance" model.
    """

    def __init__(self, tasks_table):
        self.tasks_table = tasks_table

    @staticmethod
    def _deserialize_task(task: Dict[str, Any]) -> Dict[str, Any]:
        """Guarantee a stable task shape for API responses.

        Tasks stored without a ``due_date`` (the sparse-index key) omit it; the
        other optional fields are surfaced as None so every response has the
        same keys.
        """
        task.setdefault("notes", "")
        task.setdefault("tags", [])
        task.setdefault("recurrence_type", "none")
        task.setdefault("recurrence_interval", None)
        task.setdefault("anchor_date", None)
        task.setdefault("due_date", None)
        task.setdefault("graceful", True)
        task.setdefault("last_completed_window", None)
        task.setdefault("last_completed_at", None)
        task.setdefault("answer_mode", "checkbox")
        task.setdefault("last_decision", None)
        task.setdefault("trigger", None)
        return task

    def _with_status(
        self, task: Dict[str, Any], tz: Optional[str], now: Optional[Any] = None
    ) -> Dict[str, Any]:
        """Normalize a raw task and merge its computed status fields."""
        task = self._deserialize_task(task)
        task.update(compute_status(task, tz, now))
        return task

    def create_task(
        self,
        user_id: str,
        name: str,
        notes: str = "",
        tags: List[str] = None,
        recurrence_type: str = "none",
        recurrence_interval: Optional[int] = None,
        anchor_date: Optional[str] = None,
        due_date: Optional[str] = None,
        graceful: bool = True,
        answer_mode: str = "checkbox",
        trigger: Optional[Dict[str, Any]] = None,
        tz: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Create a task, validating its recurrence rule and optional trigger."""
        tags = [t.lower() for t in (tags or [])]
        self._validate_recurrence(recurrence_type, recurrence_interval, anchor_date, due_date)
        answer_mode = self._validate_answer_mode(answer_mode)
        trigger = self._validate_trigger(user_id, trigger)

        # Interval tasks need a stable anchor; default to "today" (in the
        # caller's tz) so windows are computed from creation onward.
        if recurrence_type == "interval" and not anchor_date:
            anchor_date = local_now(tz).date().isoformat()

        task = Task.create(
            user_id=user_id,
            name=name,
            notes=notes,
            tags=tags,
            recurrence_type=recurrence_type,
            recurrence_interval=recurrence_interval,
            anchor_date=anchor_date,
            due_date=due_date,
            graceful=graceful,
            answer_mode=answer_mode,
            trigger=trigger,
        )

        storage_dict = task.to_dict()
        # due_date backs a sparse GSI: a NULL value is rejected on an index key,
        # so omit the attribute entirely when there is no deadline.
        if storage_dict.get("due_date") is None:
            storage_dict.pop("due_date", None)
        self.tasks_table.put_item(Item=storage_dict)

        logger.info(f"Created task: {task.task_id} for user: {user_id}")
        return self._with_status(task.to_dict(), tz)

    def get_task(self, user_id: str, task_id: str, tz: Optional[str] = None) -> Optional[Dict[str, Any]]:
        """Get a task by ID for a specific user, with computed status.

        A triggered task's status depends on its source, so we resolve against
        the user's whole task set rather than the single row.
        """
        response = self.tasks_table.get_item(Key={"user_id": user_id, "task_id": task_id})
        if not response.get("Item"):
            return None
        for task in self._resolved_tasks(user_id, tz):
            if task.get("task_id") == task_id:
                return task
        return None

    def _resolved_tasks(
        self, user_id: str, tz: Optional[str] = None, now: Optional[Any] = None
    ) -> List[Dict[str, Any]]:
        """Query a user's tasks and merge computed status (trigger-aware)."""
        response = self.tasks_table.query(
            KeyConditionExpression=Key("user_id").eq(user_id)
        )
        tasks = [self._deserialize_task(t) for t in response.get("Items", [])]
        return resolve_tasks(tasks, tz, now)

    def list_tasks(
        self,
        user_id: str,
        tz: Optional[str] = None,
        status: Optional[str] = None,
        tag: Optional[str] = None,
        tags: Optional[List[str]] = None,
        name: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """List a user's tasks with computed status.

        ``status`` filters the computed status: ``active`` (the default view of
        what needs doing now), ``done`` (completed for the current window), or
        None/``all`` for everything. ``tag`` (scalar, legacy) and ``tags`` (list,
        AND) narrow by denormalized tags. ``name`` is a partial, fuzzy match on the
        task name via the same matcher as inventory search. All tasks are evaluated
        against a single ``now`` for a consistent snapshot.
        """
        now = local_now(tz)
        tasks = self._resolved_tasks(user_id, tz, now)

        # Combine the legacy scalar tag with the tags list; all must match (AND).
        wanted_tags = {t.lower() for t in (tags or [])}
        if tag:
            wanted_tags.add(tag.lower())
        if wanted_tags:
            tasks = [t for t in tasks if wanted_tags.issubset(set(t.get("tags", [])))]

        if name:
            tasks = [t for t in tasks if match_name(t.get("name", ""), name) is not None]

        if status == "active":
            tasks = [t for t in tasks if t["active"]]
        elif status == "done":
            tasks = [t for t in tasks if t["done"]]

        return tasks

    def update_task(
        self, user_id: str, task_id: str, updates: Dict[str, Any], tz: Optional[str] = None
    ) -> Optional[Dict[str, Any]]:
        """Partially update a task for a specific user."""
        response = self.tasks_table.get_item(Key={"user_id": user_id, "task_id": task_id})
        existing = response.get("Item")
        if not existing:
            return None
        existing = self._deserialize_task(existing)

        # Validate against the merged view so a partial recurrence change (e.g.
        # switching to "interval") is checked with its companion fields.
        recurrence_fields = ("recurrence_type", "recurrence_interval", "anchor_date", "due_date")
        if any(f in updates for f in recurrence_fields):
            merged = {**existing, **updates}
            self._validate_recurrence(
                merged.get("recurrence_type", "none"),
                merged.get("recurrence_interval"),
                merged.get("anchor_date"),
                merged.get("due_date"),
            )

        if "answer_mode" in updates:
            updates["answer_mode"] = self._validate_answer_mode(updates["answer_mode"])
        if "trigger" in updates:
            updates["trigger"] = self._validate_trigger(
                user_id, updates["trigger"], self_task_id=task_id
            )

        set_parts = ["updated_at = :updated_at"]
        remove_parts = []
        expr_values = {":updated_at": _now_iso()}
        expr_names = {}

        if "name" in updates:
            set_parts.append("#n = :name")
            expr_values[":name"] = updates["name"]
            expr_names["#n"] = "name"

        for field_name in (
            "notes", "recurrence_type", "recurrence_interval", "anchor_date",
            "graceful", "answer_mode",
        ):
            if field_name in updates:
                set_parts.append(f"{field_name} = :{field_name}")
                expr_values[f":{field_name}"] = updates[field_name]

        if "trigger" in updates:
            # Clearing a trigger REMOVEs it (back to a plain task); setting one
            # SETs the validated dict.
            if updates["trigger"] is None:
                remove_parts.append("trigger")
            else:
                set_parts.append("trigger = :trigger")
                expr_values[":trigger"] = updates["trigger"]

        if "tags" in updates:
            set_parts.append("#tags = :tags")
            expr_values[":tags"] = sorted({t.lower() for t in updates["tags"]})
            expr_names["#tags"] = "tags"

        if "due_date" in updates:
            # due_date backs a sparse GSI, so clearing it must REMOVE the
            # attribute rather than SET it to NULL.
            if updates["due_date"] is None:
                remove_parts.append("due_date")
            else:
                set_parts.append("due_date = :due_date")
                expr_values[":due_date"] = updates["due_date"]

        update_expr = "SET " + ", ".join(set_parts)
        if remove_parts:
            update_expr += " REMOVE " + ", ".join(remove_parts)

        update_kwargs = {
            "Key": {"user_id": user_id, "task_id": task_id},
            "UpdateExpression": update_expr,
            "ExpressionAttributeValues": expr_values,
            "ReturnValues": "ALL_NEW",
        }
        if expr_names:
            update_kwargs["ExpressionAttributeNames"] = expr_names

        response = self.tasks_table.update_item(**update_kwargs)
        attributes = response.get("Attributes")
        if not attributes:
            return None

        logger.info(f"Updated task: {task_id} for user: {user_id}")
        # Resolve against siblings so a (now) triggered task reports true status.
        return self.get_task(user_id, task_id, tz)

    def complete_task(
        self,
        user_id: str,
        task_id: str,
        decision: Optional[str] = None,
        tz: Optional[str] = None,
        now: Optional[Any] = None,
    ) -> Optional[Dict[str, Any]]:
        """Mark a task complete / answer a decision for its current window.

        ``decision`` (``"yes"``/``"no"``) is required for a ``yesno`` (decision)
        task and ignored for a plain ``checkbox`` task. A triggered task records
        its *source's* window so it re-arms in lockstep with the decision it
        depends on; see ``recurrence.completion_window_key``.
        """
        # Query the whole partition once: we need siblings both to find the task
        # and to resolve a triggered task's borrowed completion window.
        query = self.tasks_table.query(KeyConditionExpression=Key("user_id").eq(user_id))
        tasks = [self._deserialize_task(t) for t in query.get("Items", [])]
        task = next((t for t in tasks if t.get("task_id") == task_id), None)
        if task is None:
            return None

        set_parts = ["updated_at = :updated_at", "last_completed_at = :completed_at"]
        expr_values = {":updated_at": _now_iso(), ":completed_at": _now_iso()}

        if task.get("answer_mode") == "yesno":
            if decision not in ("yes", "no"):
                raise ValueError("A decision task requires a 'yes' or 'no' decision")
            set_parts.append("last_decision = :decision")
            expr_values[":decision"] = decision

        # Record which window was completed so recurring / triggered tasks
        # reappear once their window rolls over. One-shot untriggered tasks have
        # no window (key ""), and rely on last_completed_at alone.
        window_key = completion_window_key(tasks, task_id, tz, now)
        if window_key:
            set_parts.append("last_completed_window = :window")
            expr_values[":window"] = window_key

        response = self.tasks_table.update_item(
            Key={"user_id": user_id, "task_id": task_id},
            UpdateExpression="SET " + ", ".join(set_parts),
            ExpressionAttributeValues=expr_values,
            ReturnValues="ALL_NEW",
        )
        logger.info(f"Completed task: {task_id} for user: {user_id}")
        # Re-resolve against the partition so a triggered task's status reflects
        # its (now possibly changed) dependency state.
        updated = self._deserialize_task(response["Attributes"])
        others = [t for t in tasks if t.get("task_id") != task_id]
        resolved = resolve_tasks(others + [updated], tz, now)
        return next(t for t in resolved if t.get("task_id") == task_id)

    def uncomplete_task(
        self, user_id: str, task_id: str, tz: Optional[str] = None, now: Optional[Any] = None
    ) -> Optional[Dict[str, Any]]:
        """Undo completion for the current window, making the task active again."""
        response = self.tasks_table.get_item(Key={"user_id": user_id, "task_id": task_id})
        if not response.get("Item"):
            return None

        response = self.tasks_table.update_item(
            Key={"user_id": user_id, "task_id": task_id},
            UpdateExpression=(
                "SET updated_at = :updated_at "
                "REMOVE last_completed_at, last_completed_window, last_decision"
            ),
            ExpressionAttributeValues={":updated_at": _now_iso()},
            ReturnValues="ALL_NEW",
        )
        logger.info(f"Uncompleted task: {task_id} for user: {user_id}")
        # Re-resolve so dependents of this decision reflect its cleared state.
        return self.get_task(user_id, task_id, tz)

    def delete_task(self, user_id: str, task_id: str) -> bool:
        """Delete a task for a specific user.

        Returns False when the task does not exist so callers can surface a 404
        (DynamoDB's delete_item succeeds unconditionally, so we check first).
        """
        response = self.tasks_table.get_item(Key={"user_id": user_id, "task_id": task_id})
        if not response.get("Item"):
            return False
        self.tasks_table.delete_item(Key={"user_id": user_id, "task_id": task_id})
        logger.info(f"Deleted task: {task_id} for user: {user_id}")
        return True

    @staticmethod
    def _validate_recurrence(
        recurrence_type: Any,
        recurrence_interval: Any,
        anchor_date: Any,
        due_date: Any,
    ) -> None:
        """Validate a recurrence rule, raising ValueError on any problem."""
        if recurrence_type not in RECURRENCE_TYPES:
            raise ValueError(
                f"Invalid recurrence_type: {recurrence_type!r} "
                f"(must be one of {sorted(RECURRENCE_TYPES)})"
            )
        if recurrence_type == "interval":
            if (
                isinstance(recurrence_interval, bool)
                or not isinstance(recurrence_interval, int)
                or recurrence_interval < 1
            ):
                raise ValueError(
                    "recurrence_interval must be a positive integer for interval tasks"
                )
        for label, value in (("anchor_date", anchor_date), ("due_date", due_date)):
            if value is not None:
                try:
                    datetime.fromisoformat(value)
                except (TypeError, ValueError):
                    raise ValueError(f"Invalid {label}: must be an ISO-8601 date")

    @staticmethod
    def _validate_answer_mode(answer_mode: Any) -> str:
        """Validate a task's answer mode, defaulting None to ``checkbox``."""
        if answer_mode is None:
            return "checkbox"
        if answer_mode not in ("checkbox", "yesno"):
            raise ValueError("answer_mode must be 'checkbox' or 'yesno'")
        return answer_mode

    def _validate_trigger(
        self, user_id: str, trigger: Any, self_task_id: Optional[str] = None
    ) -> Optional[Dict[str, Any]]:
        """Validate a task trigger, returning a normalized dict or None.

        Checks the shape, that the source task exists and (for yes/no branches)
        is itself a decision task, and — on update, when ``self_task_id`` is
        known — that the dependency chain does not cycle back to this task.
        """
        if trigger is None:
            return None
        if not isinstance(trigger, dict):
            raise ValueError("trigger must be an object")

        source_id = trigger.get("source_task_id")
        if not source_id or not isinstance(source_id, str):
            raise ValueError("trigger.source_task_id is required")
        if source_id == self_task_id:
            raise ValueError("A task cannot trigger on itself")

        on = trigger.get("on", "any")
        if on not in TRIGGER_ON:
            raise ValueError(f"trigger.on must be one of {sorted(TRIGGER_ON)}")

        deadline = trigger.get("deadline", "same_day")
        if deadline not in TRIGGER_DEADLINES:
            raise ValueError(f"trigger.deadline must be one of {sorted(TRIGGER_DEADLINES)}")

        clean: Dict[str, Any] = {"source_task_id": source_id, "on": on, "deadline": deadline}
        if deadline == "offset":
            offset = trigger.get("offset_days")
            if isinstance(offset, bool) or not isinstance(offset, int) or offset < 0:
                raise ValueError(
                    "trigger.offset_days must be a non-negative integer for an offset deadline"
                )
            clean["offset_days"] = offset

        source = self.tasks_table.get_item(
            Key={"user_id": user_id, "task_id": source_id}
        ).get("Item")
        if source is None:
            raise ValueError("trigger.source_task_id does not reference an existing task")
        if on in ("yes", "no") and source.get("answer_mode") != "yesno":
            raise ValueError(
                "A yes/no trigger requires the source task to be a decision (yesno) task"
            )

        # Cycle guard (update path): walk the source's own trigger chain.
        if self_task_id is not None:
            seen = set()
            cursor = source.get("trigger", {}).get("source_task_id") if source.get("trigger") else None
            while cursor:
                if cursor == self_task_id:
                    raise ValueError("trigger would create a dependency cycle")
                if cursor in seen:
                    break
                seen.add(cursor)
                node = self.tasks_table.get_item(
                    Key={"user_id": user_id, "task_id": cursor}
                ).get("Item")
                cursor = node.get("trigger", {}).get("source_task_id") if node and node.get("trigger") else None

        return clean


class ReportService:
    """Service for managing scheduled-report configs.

    A report stores *what* to report (ordered section rules) and *when* (a simple
    cron-ish schedule). ``next_run`` is computed from the schedule on write and
    advanced after each generation; it backs the periodic sweep's due filter.
    """

    def __init__(self, reports_table, category_service=None):
        self.reports_table = reports_table
        # Optional CategoryService; when present, trigger validation checks that
        # referenced category_ids exist.
        self.category_service = category_service

    @staticmethod
    def _deserialize_report(report: Dict[str, Any]) -> Dict[str, Any]:
        """Guarantee a stable report shape for API responses.

        DynamoDB returns all numbers as Decimal, so schedule fields like
        ``weekday`` / ``day_of_month`` come back as Decimal and would fail the
        ``int`` checks in schedule validation (and JSON serialization). Convert
        them back to plain int/float on read.
        """
        report.setdefault("enabled", True)
        report.setdefault("schedule", {})
        report.setdefault("sections", [])
        report.setdefault("delivery", {})
        report.setdefault("trigger", {})
        report.setdefault("next_run", None)
        report.setdefault("last_run_at", None)
        report["schedule"] = _decimals_to_float(report["schedule"])
        report["sections"] = _decimals_to_float(report["sections"])
        report["trigger"] = _decimals_to_float(report["trigger"])
        return report

    def _validate_trigger(self, user_id: str, trigger: Any) -> None:
        """Validate a report trigger against the user's existing categories."""
        valid_ids = None
        if trigger and self.category_service is not None:
            valid_ids = {c["category_id"] for c in self.category_service.list_categories(user_id)}
        validate_trigger(trigger, valid_ids)

    def create_report(
        self,
        user_id: str,
        name: str,
        schedule: Dict[str, Any],
        sections: List[Dict[str, Any]] = None,
        enabled: bool = True,
        now: Optional[Any] = None,
        delivery: Dict[str, Any] = None,
        trigger: Dict[str, Any] = None,
    ) -> Dict[str, Any]:
        """Create a report, validating its schedule, sections, delivery, trigger."""
        sections = sections or []
        validate_schedule(schedule)
        validate_sections(sections)
        _validate_delivery(delivery)
        self._validate_trigger(user_id, trigger)

        next_run = compute_next_run(schedule, now)
        report = Report.create(
            user_id=user_id,
            name=name,
            schedule=schedule,
            sections=sections,
            enabled=enabled,
            next_run=next_run,
            delivery=delivery or {},
            trigger=trigger or {},
        )
        self.reports_table.put_item(Item=report.to_dict())
        logger.info(f"Created report: {report.report_id} for user: {user_id}")
        return self._deserialize_report(report.to_dict())

    def get_report(self, user_id: str, report_id: str) -> Optional[Dict[str, Any]]:
        """Get a report by ID for a specific user."""
        response = self.reports_table.get_item(Key={"user_id": user_id, "report_id": report_id})
        report = response.get("Item")
        if not report:
            return None
        return self._deserialize_report(report)

    def list_reports(self, user_id: str) -> List[Dict[str, Any]]:
        """List all of a user's reports."""
        response = self.reports_table.query(
            KeyConditionExpression=Key("user_id").eq(user_id)
        )
        return [self._deserialize_report(r) for r in response.get("Items", [])]

    def update_report(
        self, user_id: str, report_id: str, updates: Dict[str, Any], now: Optional[Any] = None
    ) -> Optional[Dict[str, Any]]:
        """Partially update a report. Recomputes next_run if the schedule changes."""
        response = self.reports_table.get_item(Key={"user_id": user_id, "report_id": report_id})
        existing = response.get("Item")
        if not existing:
            return None

        if "schedule" in updates:
            validate_schedule(updates["schedule"])
        if "sections" in updates:
            validate_sections(updates["sections"])
        if "delivery" in updates:
            _validate_delivery(updates["delivery"])
        if "trigger" in updates:
            self._validate_trigger(user_id, updates["trigger"])

        set_parts = ["updated_at = :updated_at"]
        expr_values = {":updated_at": _now_iso()}
        expr_names = {}

        if "name" in updates:
            set_parts.append("#n = :name")
            expr_values[":name"] = updates["name"]
            expr_names["#n"] = "name"

        for field_name in ("enabled", "sections", "delivery", "trigger"):
            if field_name in updates:
                set_parts.append(f"{field_name} = :{field_name}")
                expr_values[f":{field_name}"] = updates[field_name]

        if "schedule" in updates:
            set_parts.append("schedule = :schedule")
            expr_values[":schedule"] = updates["schedule"]
            # A changed schedule invalidates the old firing time.
            set_parts.append("next_run = :next_run")
            expr_values[":next_run"] = compute_next_run(updates["schedule"], now)

        update_kwargs = {
            "Key": {"user_id": user_id, "report_id": report_id},
            "UpdateExpression": "SET " + ", ".join(set_parts),
            "ExpressionAttributeValues": expr_values,
            "ReturnValues": "ALL_NEW",
        }
        if expr_names:
            update_kwargs["ExpressionAttributeNames"] = expr_names

        response = self.reports_table.update_item(**update_kwargs)
        attributes = response.get("Attributes")
        if not attributes:
            return None
        logger.info(f"Updated report: {report_id} for user: {user_id}")
        return self._deserialize_report(attributes)

    def delete_report(self, user_id: str, report_id: str) -> bool:
        """Delete a report; returns False when it does not exist (for a 404)."""
        response = self.reports_table.get_item(Key={"user_id": user_id, "report_id": report_id})
        if not response.get("Item"):
            return False
        self.reports_table.delete_item(Key={"user_id": user_id, "report_id": report_id})
        logger.info(f"Deleted report: {report_id} for user: {user_id}")
        return True

    def list_due_reports(self, now: Optional[Any] = None) -> List[Dict[str, Any]]:
        """Return all enabled reports across users whose next_run is at or before now.

        The sweep runs cross-user, so this Scans the table (volume is low and the
        table is PAY_PER_REQUEST). If report counts grow, back this with a GSI on
        a constant partition keyed by next_run instead.
        """
        now_iso = (now.astimezone(timezone.utc).isoformat() if now is not None else _now_iso())
        response = self.reports_table.scan(
            FilterExpression=Attr("enabled").eq(True) & Attr("next_run").lte(now_iso)
        )
        items = [self._deserialize_report(r) for r in response.get("Items", [])]
        while "LastEvaluatedKey" in response:
            response = self.reports_table.scan(
                FilterExpression=Attr("enabled").eq(True) & Attr("next_run").lte(now_iso),
                ExclusiveStartKey=response["LastEvaluatedKey"],
            )
            items.extend(self._deserialize_report(r) for r in response.get("Items", []))
        return items

    def mark_run(
        self, user_id: str, report_id: str, schedule: Dict[str, Any], now: Optional[Any] = None
    ) -> None:
        """Record a generation: advance next_run and stamp last_run_at."""
        self.reports_table.update_item(
            Key={"user_id": user_id, "report_id": report_id},
            UpdateExpression="SET next_run = :next_run, last_run_at = :last_run_at, updated_at = :updated_at",
            ExpressionAttributeValues={
                ":next_run": compute_next_run(schedule, now),
                ":last_run_at": _now_iso(),
                ":updated_at": _now_iso(),
            },
        )


class MessageService:
    """Service for the notification/message log.

    Messages are generated by the report engine (or created directly). Unread
    state is modeled with a sparse GSI: an unread message carries an
    ``unread_sort`` attribute (its ``created_at``, so the index sorts newest-first)
    and appears in the ``UnreadIndex``; marking read REMOVES that attribute
    (dropping the row from the index) and stamps ``read_at``. This powers the
    toolbar badge without scanning all rows. ``unread_sort`` is storage-only and
    stripped from API responses.
    """

    UNREAD_INDEX = "UnreadIndex"
    UNREAD_SORT_ATTR = "unread_sort"

    def __init__(self, messages_table):
        self.messages_table = messages_table

    @classmethod
    def _deserialize_message(cls, message: Dict[str, Any]) -> Dict[str, Any]:
        """Guarantee a stable message shape for API responses."""
        message.pop(cls.UNREAD_SORT_ATTR, None)  # storage-only index key
        message.setdefault("report_id", None)
        message.setdefault("sections", [])
        message.setdefault("read_at", None)
        # Section content may hold Decimals (from stored item/task snapshots);
        # convert back to float/int so the response is JSON-serializable.
        message["sections"] = _decimals_to_float(message["sections"])
        return message

    def create_message(
        self,
        user_id: str,
        title: str,
        sections: List[Dict[str, Any]] = None,
        report_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Create a message (unread: carries unread_sort, omits read_at)."""
        message = Message.create(
            user_id=user_id,
            title=title,
            sections=sections or [],
            report_id=report_id,
        )
        storage_dict = message.to_dict()
        # read_at is absent while unread; unread_sort (=created_at) places the row
        # in the sparse UnreadIndex, sorted newest-first.
        storage_dict.pop("read_at", None)
        storage_dict[self.UNREAD_SORT_ATTR] = message.created_at
        # Section snapshots may carry floats (e.g. item dimensions); DynamoDB
        # needs Decimal.
        storage_dict["sections"] = _floats_to_decimal(storage_dict["sections"])
        self.messages_table.put_item(Item=storage_dict)
        logger.info(f"Created message: {message.message_id} for user: {user_id}")
        return self._deserialize_message(message.to_dict())

    def get_message(self, user_id: str, message_id: str) -> Optional[Dict[str, Any]]:
        """Get a message by ID for a specific user."""
        response = self.messages_table.get_item(Key={"user_id": user_id, "message_id": message_id})
        message = response.get("Item")
        if not message:
            return None
        return self._deserialize_message(message)

    def list_messages(self, user_id: str) -> List[Dict[str, Any]]:
        """List a user's messages, newest first."""
        response = self.messages_table.query(
            KeyConditionExpression=Key("user_id").eq(user_id)
        )
        messages = [self._deserialize_message(m) for m in response.get("Items", [])]
        messages.sort(key=lambda m: m.get("created_at", ""), reverse=True)
        return messages

    def list_unread(self, user_id: str) -> List[Dict[str, Any]]:
        """List a user's unread messages via the sparse UnreadIndex, newest first."""
        response = self.messages_table.query(
            IndexName=self.UNREAD_INDEX,
            KeyConditionExpression=Key("user_id").eq(user_id),
        )
        messages = [self._deserialize_message(m) for m in response.get("Items", [])]
        messages.sort(key=lambda m: m.get("created_at", ""), reverse=True)
        return messages

    def unread_count(self, user_id: str) -> int:
        """Count a user's unread messages (queries the sparse index)."""
        response = self.messages_table.query(
            IndexName=self.UNREAD_INDEX,
            KeyConditionExpression=Key("user_id").eq(user_id),
            Select="COUNT",
        )
        return response.get("Count", 0)

    def mark_read(self, user_id: str, message_id: str) -> Optional[Dict[str, Any]]:
        """Mark a message read (writes read_at, dropping it from the unread index)."""
        response = self.messages_table.get_item(Key={"user_id": user_id, "message_id": message_id})
        if not response.get("Item"):
            return None
        response = self.messages_table.update_item(
            Key={"user_id": user_id, "message_id": message_id},
            UpdateExpression=f"SET read_at = :read_at REMOVE {self.UNREAD_SORT_ATTR}",
            ExpressionAttributeValues={":read_at": _now_iso()},
            ReturnValues="ALL_NEW",
        )
        logger.info(f"Marked message read: {message_id} for user: {user_id}")
        return self._deserialize_message(response["Attributes"])

    def mark_unread(self, user_id: str, message_id: str) -> Optional[Dict[str, Any]]:
        """Mark a message unread (restores unread_sort, REMOVEs read_at)."""
        response = self.messages_table.get_item(Key={"user_id": user_id, "message_id": message_id})
        existing = response.get("Item")
        if not existing:
            return None
        response = self.messages_table.update_item(
            Key={"user_id": user_id, "message_id": message_id},
            UpdateExpression=f"SET {self.UNREAD_SORT_ATTR} = :unread_sort REMOVE read_at",
            ExpressionAttributeValues={":unread_sort": existing.get("created_at", _now_iso())},
            ReturnValues="ALL_NEW",
        )
        logger.info(f"Marked message unread: {message_id} for user: {user_id}")
        return self._deserialize_message(response["Attributes"])

    def delete_message(self, user_id: str, message_id: str) -> bool:
        """Delete a message; returns False when it does not exist (for a 404)."""
        response = self.messages_table.get_item(Key={"user_id": user_id, "message_id": message_id})
        if not response.get("Item"):
            return False
        self.messages_table.delete_item(Key={"user_id": user_id, "message_id": message_id})
        logger.info(f"Deleted message: {message_id} for user: {user_id}")
        return True

    def mark_read_bulk(self, user_id: str, message_ids: List[str]) -> int:
        """Mark a set of the user's messages read; return how many were updated.

        Applies the same update as :meth:`mark_read` to each id (SET read_at,
        REMOVE unread_sort). Ids that don't exist for this user are skipped, so
        the count reflects rows actually updated. DynamoDB has no batch
        update_item, so this loops.
        """
        read_at = _now_iso()
        updated = 0
        for message_id in message_ids:
            existing = self.messages_table.get_item(
                Key={"user_id": user_id, "message_id": message_id}
            )
            if not existing.get("Item"):
                continue
            self.messages_table.update_item(
                Key={"user_id": user_id, "message_id": message_id},
                UpdateExpression=f"SET read_at = :read_at REMOVE {self.UNREAD_SORT_ATTR}",
                ExpressionAttributeValues={":read_at": read_at},
            )
            updated += 1
        logger.info(f"Marked {updated} messages read for user: {user_id}")
        return updated

    def delete_bulk(self, user_id: str, message_ids: List[str]) -> int:
        """Delete a set of the user's messages; return how many existed.

        Missing ids are skipped (counted only when present). Deletes are issued
        through a ``batch_writer`` to cut round-trips.
        """
        to_delete = [
            mid
            for mid in message_ids
            if self.messages_table.get_item(
                Key={"user_id": user_id, "message_id": mid}
            ).get("Item")
        ]
        if to_delete:
            with self.messages_table.batch_writer() as batch:
                for message_id in to_delete:
                    batch.delete_item(Key={"user_id": user_id, "message_id": message_id})
        logger.info(f"Deleted {len(to_delete)} messages for user: {user_id}")
        return len(to_delete)


class ReportGenerator:
    """Renders a report config into a message (the in-app delivery sink).

    This is the seam the Slack integration will extend: today ``generate`` writes
    the rendered message to the message log; a Slack sink will later consume the
    same rendered :class:`Message` (see ``docs/slack-integration-plan.md``'s
    ``post_message`` boundary). Section rules are resolved against live data at
    generation time via the injected services, then snapshotted into the message.
    """

    def __init__(self, report_service, message_service, task_service, item_service,
                 category_service=None, slack_service=None, app_base_url=""):
        self.report_service = report_service
        self.message_service = message_service
        # Exposed as attributes so section renderers can reach the service layer.
        self.task_service = task_service
        self.item_service = item_service
        # Section renderers and the trigger engine use category data.
        self.category_service = category_service
        # Optional Slack delivery sink; None disables Slack posting.
        self.slack_service = slack_service
        # Web app base URL for links back from Slack (e.g. task/item deep links).
        self.app_base_url = app_base_url

    def render_sections(
        self, report: Dict[str, Any], tz: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """Render a report's section rules into snapshots against live data.

        The pure render step shared by ``generate`` (which persists + delivers)
        and the live ``/reports/<id>/preview`` endpoint (which does neither, so
        answering a decision on the report page can re-fetch the next round of
        newly-activated tasks).
        """
        user_id = report["user_id"]
        return [
            render_section(section, user_id, self, tz)
            for section in report.get("sections", [])
        ]

    def generate(
        self, report: Dict[str, Any], tz: Optional[str] = None, now: Optional[Any] = None
    ) -> Dict[str, Any]:
        """Render one report into a message and persist it.

        Advances the report's next_run / last_run_at. Returns the created message.
        """
        user_id = report["user_id"]
        rendered_sections = self.render_sections(report, tz)
        message = self.message_service.create_message(
            user_id=user_id,
            title=report.get("name", "Report"),
            sections=rendered_sections,
            report_id=report.get("report_id"),
        )
        self.report_service.mark_run(
            user_id, report["report_id"], report.get("schedule", {}), now
        )
        logger.info(
            f"Generated report {report['report_id']} -> message "
            f"{message['message_id']} for user {user_id}"
        )
        self._deliver_to_slack(report, message)
        return message

    def _deliver_to_slack(self, report: Dict[str, Any], message: Dict[str, Any]) -> None:
        """Post the generated report to Slack when the report has a destination.

        Best-effort: a delivery failure (revoked token, bad channel, Slack down)
        is logged and swallowed so the in-app message still stands and the sweep
        keeps going. Ownership is enforced by post_message scoping the token to
        the report's user_id.
        """
        target = (report.get("delivery") or {}).get("slack")
        if not target or self.slack_service is None:
            return
        try:
            blocks = render_message_blocks(
                message["title"], message.get("sections", []), self.app_base_url
            )
            self.slack_service.post_message(
                report["user_id"],
                target["connection_id"],
                target["channel_id"],
                blocks=blocks,
                text=message["title"],
            )
            logger.info(
                f"Delivered report {report['report_id']} to Slack channel "
                f"{target['channel_id']}"
            )
        except Exception as exc:
            logger.warning(
                f"Slack delivery failed for report {report.get('report_id')}: {exc}"
            )


class SlackError(RuntimeError):
    """A Slack Web API call returned ``ok: false`` (carries the Slack error code)."""


class SlackService:
    """Bring-your-own-Slack connections: OAuth install, token storage, posting.

    Multi-tenant by ``user_id`` (Cognito sub) — one customer's bot token can
    never post into another's workspace. Bot tokens are stored ONLY as ciphertext
    (KMS-encrypted, base64) and never returned by the API. The Slack Web API is
    called with stdlib ``urllib`` (no SDK dependency); only four methods are used:
    ``oauth.v2.access``, ``conversations.list``, ``chat.postMessage``,
    ``auth.revoke``.

    ``post_message`` / ``_get_token`` are the primitives the report/notification
    engine consumes.

    Local mode (``local_mode=True``, set by the Flask dev shim) short-circuits
    every AWS/Slack network dependency: tokens are base64-passthrough (no KMS),
    secrets are stubbed, and Slack calls return canned responses. This lets the
    SPA and CLI exercise the whole flow offline via ``dev_stub_connect``.
    """

    AUTHORIZE_URL = "https://slack.com/oauth/v2/authorize"
    API_BASE = "https://slack.com/api/"
    # Minimal bot scopes (see docs/slack-integration-plan.md §2). chat:write to
    # post; channels:read/groups:read to list channels for the picker;
    # chat:write.public to post to public channels without an explicit invite.
    SCOPES = "chat:write,channels:read,groups:read,chat:write.public"
    STATE_TTL_SECONDS = 600  # signed OAuth state is valid for 10 minutes

    def __init__(
        self,
        connections_table,
        kms_client,
        secrets_client,
        *,
        client_id: str,
        redirect_uri: str,
        kms_key_id: Optional[str] = None,
        secret_arn: Optional[str] = None,
        nonces_table=None,
        local_mode: bool = False,
    ):
        self.connections_table = connections_table
        self.kms_client = kms_client
        self.secrets_client = secrets_client
        self.client_id = client_id
        self.redirect_uri = redirect_uri
        self.kms_key_id = kms_key_id
        self.secret_arn = secret_arn
        # Single-use OAuth-state store: each verified nonce is recorded here with
        # a conditional put so a replayed state is rejected. Rows self-expire via
        # DynamoDB TTL on ``expires_at``. When None, single-use is not enforced
        # (misconfiguration) and only the signature + TTL guard the state.
        self.nonces_table = nonces_table
        self.local_mode = local_mode
        self._secret_cache: Optional[Dict[str, str]] = None

    # -- secrets ------------------------------------------------------------
    def _secret(self) -> Dict[str, str]:
        """Return the app-level Slack secret JSON, cached per warm invocation.

        Holds ``client_secret`` (for oauth.v2.access) and ``state_hmac`` (for
        signing OAuth state). Never logged.
        """
        if self._secret_cache is not None:
            return self._secret_cache
        if self.local_mode:
            self._secret_cache = {
                "client_secret": "local-client-secret",
                "state_hmac": "local-state-hmac",
            }
            return self._secret_cache
        resp = self.secrets_client.get_secret_value(SecretId=self.secret_arn)
        self._secret_cache = json.loads(resp["SecretString"])
        return self._secret_cache

    # -- token encryption ---------------------------------------------------
    def _encrypt(self, token: str) -> str:
        """Encrypt a bot token to a base64 string for storage.

        Local mode uses a marked passthrough (NO real crypto) so the dev tier
        needs no KMS; the ``local:`` prefix makes such rows self-identifying.
        """
        if self.local_mode:
            return "local:" + base64.b64encode(token.encode()).decode()
        blob = self.kms_client.encrypt(KeyId=self.kms_key_id, Plaintext=token.encode())["CiphertextBlob"]
        return base64.b64encode(blob).decode()

    def _decrypt(self, cipher: str) -> str:
        """Decrypt a stored bot token ciphertext back to plaintext."""
        if cipher.startswith("local:"):
            return base64.b64decode(cipher[len("local:"):]).decode()
        blob = base64.b64decode(cipher)
        return self.kms_client.decrypt(CiphertextBlob=blob)["Plaintext"].decode()

    # -- OAuth state (CSRF + identity binding) ------------------------------
    def _mint_state(self, user_id: str) -> str:
        """Mint a signed, expiring ``state`` binding the Cognito identity.

        Format: ``base64url(payload).base64url(hmac_sha256(payload))``. The
        callback is hit by Slack's redirect (no Cognito context), so identity
        must ride inside a value we can verify — never a plaintext user_id.

        Note: the ``nonce`` gives per-mint entropy but true single-use
        enforcement (rejecting a replayed valid state) would need a nonce store;
        that is deferred. The short TTL bounds the replay window.
        """
        payload = json.dumps({
            "user_id": user_id,
            "nonce": _secrets.token_urlsafe(16),
            "exp": int(time.time()) + self.STATE_TTL_SECONDS,
        }, separators=(",", ":")).encode()
        raw = base64.urlsafe_b64encode(payload).decode()
        return raw + "." + self._sign(raw)

    def _sign(self, raw: str) -> str:
        key = self._secret()["state_hmac"].encode()
        sig = hmac.new(key, raw.encode(), hashlib.sha256).digest()
        return base64.urlsafe_b64encode(sig).decode()

    def _verify_state(self, state: str) -> str:
        """Verify a ``state`` blob and return the bound ``user_id``.

        Verifies signature and expiry, then CONSUMES the nonce so the state is
        single-use: a conditional put records the nonce, and a second attempt to
        use the same state is rejected. Raises ValueError on a malformed,
        tampered, expired, or already-used state.
        """
        try:
            raw, sig = state.split(".", 1)
        except (ValueError, AttributeError):
            raise ValueError("Malformed OAuth state")
        # Constant-time signature check before trusting any payload bytes.
        if not hmac.compare_digest(sig, self._sign(raw)):
            raise ValueError("Invalid OAuth state signature")
        payload = json.loads(base64.urlsafe_b64decode(raw))
        exp = int(payload.get("exp", 0))
        if exp < int(time.time()):
            raise ValueError("Expired OAuth state")
        self._consume_nonce(payload["nonce"], exp)
        return payload["user_id"]

    def _consume_nonce(self, nonce: str, exp: int) -> None:
        """Record a nonce once; reject a replay. No-op if no nonce store.

        The row self-expires shortly after the state would have expired anyway
        (DynamoDB TTL on ``expires_at``), so the table never grows unbounded.
        """
        if self.nonces_table is None:
            return
        try:
            self.nonces_table.put_item(
                Item={"nonce": nonce, "expires_at": exp + 60},
                ConditionExpression="attribute_not_exists(nonce)",
            )
        except ClientError as err:
            if err.response["Error"]["Code"] == "ConditionalCheckFailedException":
                raise ValueError("OAuth state already used")
            raise

    # -- Slack Web API transport -------------------------------------------
    def _slack_call(self, method: str, params: Dict[str, str], token: Optional[str] = None) -> Dict[str, Any]:
        """POST to a Slack Web API method (form-encoded); raise on ``ok: false``.

        In local mode, return canned responses so nothing hits the network.
        """
        if self.local_mode:
            return self._local_response(method, params)
        data = urllib.parse.urlencode(params).encode()
        headers = {"Content-Type": "application/x-www-form-urlencoded"}
        if token:
            headers["Authorization"] = f"Bearer {token}"
        req = urllib.request.Request(self.API_BASE + method, data=data, headers=headers)
        with urllib.request.urlopen(req, timeout=10) as resp:  # noqa: S310 (fixed https host)
            body = json.loads(resp.read().decode())
        if not body.get("ok"):
            # Slack returns a machine-readable error code, not the token — safe to log.
            logger.warning(f"Slack API {method} failed: {body.get('error')}")
            raise SlackError(body.get("error", "unknown_error"))
        return body

    @staticmethod
    def _local_response(method: str, params: Dict[str, str]) -> Dict[str, Any]:
        """Canned Slack responses for the fully-local dev tier."""
        if method == "oauth.v2.access":
            return {
                "ok": True,
                "access_token": "xoxb-local-stub-token",
                "scope": SlackService.SCOPES,
                "bot_user_id": "U_LOCALBOT",
                "team": {"id": "T_LOCAL", "name": "Local Dev Workspace"},
                "authed_user": {"id": "U_LOCALUSER"},
            }
        if method == "conversations.list":
            return {"ok": True, "channels": [
                {"id": "C_LOCAL_GENERAL", "name": "general"},
                {"id": "C_LOCAL_RANDOM", "name": "random"},
            ]}
        if method == "chat.postMessage":
            return {"ok": True, "channel": params.get("channel"), "ts": "1234567890.000100"}
        if method == "auth.revoke":
            return {"ok": True, "revoked": True}
        return {"ok": True}

    # -- OAuth flow ---------------------------------------------------------
    def build_authorize_url(self, user_id: str) -> str:
        """Build the Slack authorize URL for a logged-in user (start of OAuth).

        Raises ValueError when the Slack app is not configured (empty client_id
        or redirect_uri) so the caller surfaces a clear error instead of
        redirecting to a broken Slack authorize page ("Please specify client_id").
        """
        if not self.client_id or not self.redirect_uri:
            raise ValueError(
                "Slack integration is not configured (missing SLACK_CLIENT_ID / "
                "SLACK_REDIRECT_URI)"
            )
        query = urllib.parse.urlencode({
            "client_id": self.client_id,
            "scope": self.SCOPES,
            "redirect_uri": self.redirect_uri,
            "state": self._mint_state(user_id),
        })
        return f"{self.AUTHORIZE_URL}?{query}"

    def complete_oauth(self, code: str, state: str) -> Dict[str, Any]:
        """Verify ``state``, exchange ``code`` for a token, store it encrypted.

        Returns the API-safe connection shape (no token).
        """
        user_id = self._verify_state(state)  # verify BEFORE calling Slack
        resp = self._slack_call("oauth.v2.access", {
            "client_id": self.client_id,
            "client_secret": self._secret()["client_secret"],
            "code": code,
            "redirect_uri": self.redirect_uri,
        })
        team = resp.get("team", {}) or {}
        connection = SlackConnection.create(
            user_id=user_id,
            team_id=team.get("id", ""),
            team_name=team.get("name", ""),
            bot_token_cipher=self._encrypt(resp["access_token"]),
            bot_user_id=resp.get("bot_user_id", ""),
            scopes=resp.get("scope", ""),
            authed_user_id=(resp.get("authed_user", {}) or {}).get("id", ""),
        )
        self.connections_table.put_item(Item=connection.to_dict())
        logger.info(f"Slack connected: team={connection.team_id} for user={user_id}")
        return connection.to_public_dict()

    # -- connections --------------------------------------------------------
    def list_connections(self, user_id: str) -> List[Dict[str, Any]]:
        """List a user's connected workspaces (token stripped)."""
        response = self.connections_table.query(
            KeyConditionExpression=Key("user_id").eq(user_id)
        )
        return [SlackConnection.public_from_item(item) for item in response.get("Items", [])]

    def list_channels(self, user_id: str, connection_id: str) -> List[Dict[str, Any]]:
        """List channels for the picker (public + private the bot can see)."""
        token = self._get_token(user_id, connection_id)
        resp = self._slack_call("conversations.list", {
            "types": "public_channel,private_channel",
            "exclude_archived": "true",
            "limit": "200",
        }, token=token)
        return [{"id": c["id"], "name": c["name"]} for c in resp.get("channels", [])]

    def disconnect(self, user_id: str, connection_id: str) -> bool:
        """Revoke the token and delete the row — best effort on each half.

        Per the security plan, revoke even if the row delete fails and delete
        even if revoke fails; a missing connection returns False (→ 404).
        """
        item = self._get_item(user_id, connection_id)
        if not item:
            return False
        try:
            token = self._decrypt(item["bot_token_cipher"])
            self._slack_call("auth.revoke", {}, token=token)
        except Exception as exc:  # revoke is best-effort; proceed to delete
            logger.warning(f"Slack auth.revoke failed for {connection_id}: {exc}")
        self.connections_table.delete_item(
            Key={"user_id": user_id, "connection_id": connection_id}
        )
        logger.info(f"Slack disconnected: {connection_id} for user={user_id}")
        return True

    def post_message(
        self,
        user_id: str,
        connection_id: str,
        channel_id: str,
        blocks: Optional[List[Dict[str, Any]]] = None,
        text: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Post a message to a channel — the seam the report engine builds on."""
        token = self._get_token(user_id, connection_id)
        params: Dict[str, str] = {"channel": channel_id}
        if blocks:
            params["blocks"] = json.dumps(blocks)
        # Slack requires text or blocks; always send a text fallback for
        # notifications/accessibility even when blocks are present.
        params["text"] = text or "Homestead Manager notification"
        return self._slack_call("chat.postMessage", params, token=token)

    # -- local dev ----------------------------------------------------------
    def dev_stub_connect(self, user_id: str, team_name: str = "Local Dev Workspace") -> Dict[str, Any]:
        """Insert a fake connection row for local UI/API work (LOCAL MODE ONLY)."""
        if not self.local_mode:
            raise PermissionError("dev_stub_connect is only available in local mode")
        connection = SlackConnection.create(
            user_id=user_id,
            team_id="T_LOCAL",
            team_name=team_name,
            bot_token_cipher=self._encrypt("xoxb-local-stub-token"),
            bot_user_id="U_LOCALBOT",
            scopes=self.SCOPES,
            authed_user_id=user_id,
        )
        self.connections_table.put_item(Item=connection.to_dict())
        logger.info(f"Slack dev-stub connected for user={user_id}")
        return connection.to_public_dict()

    # -- internals ----------------------------------------------------------
    def _get_item(self, user_id: str, connection_id: str) -> Optional[Dict[str, Any]]:
        response = self.connections_table.get_item(
            Key={"user_id": user_id, "connection_id": connection_id}
        )
        return response.get("Item")

    def _get_token(self, user_id: str, connection_id: str) -> str:
        """Decrypt and return the bot token for a connection (internal only).

        Raises ValueError when the connection does not exist (→ 404).
        """
        item = self._get_item(user_id, connection_id)
        if not item:
            raise ValueError("Slack connection not found")
        return self._decrypt(item["bot_token_cipher"])

