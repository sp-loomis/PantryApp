"""
Service layer for the Pantry App.
Handles business logic and DynamoDB operations.
"""

from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta, timezone
from decimal import Decimal

from boto3.dynamodb.conditions import Key, Attr
from aws_lambda_powertools import Logger

from models import Item, Location, ItemTag, Task, Report, Message
from dimensions import (
    Dimension, DimensionType, validate_dimension, aggregate_dimensions
)
from search import match_name, DEFAULT_MIN_SCORE
from recurrence import (
    RECURRENCE_TYPES, compute_status, current_window_key, local_now,
)
from schedules import compute_next_run, validate_schedule
from report_sections import render_section, validate_sections

logger = Logger(child=True)

# Upper bound on how many identical copies a single create request may add.
# Guards against accidental/abusive bulk writes while comfortably covering
# realistic pantry restocking (e.g. a case of cans).
COPIES_MAX = 100


def _now_iso() -> str:
    """Return the current UTC time as an ISO-8601 string."""
    return datetime.now(timezone.utc).isoformat()


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

    def __init__(self, items_table, tags_table):
        self.items_table = items_table
        self.tag_service = TagService(tags_table)

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

        created = []
        for _ in range(copies):
            item = Item.create(
                user_id=user_id,
                name=name,
                location_id=location_id,
                dimensions=dimensions,
                tags=tags,
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

        return {
            "total_items": total_items,
            "items_with_expiry": items_with_expiry,
            "aggregated_dimensions": dimensions_dict
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
        tz: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Create a task, validating its recurrence rule."""
        tags = [t.lower() for t in (tags or [])]
        self._validate_recurrence(recurrence_type, recurrence_interval, anchor_date, due_date)

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
        """Get a task by ID for a specific user, with computed status."""
        response = self.tasks_table.get_item(Key={"user_id": user_id, "task_id": task_id})
        task = response.get("Item")
        if not task:
            return None
        return self._with_status(task, tz)

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
        response = self.tasks_table.query(
            KeyConditionExpression=Key("user_id").eq(user_id)
        )
        now = local_now(tz)
        tasks = [self._with_status(t, tz, now) for t in response.get("Items", [])]

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

        set_parts = ["updated_at = :updated_at"]
        remove_parts = []
        expr_values = {":updated_at": _now_iso()}
        expr_names = {}

        if "name" in updates:
            set_parts.append("#n = :name")
            expr_values[":name"] = updates["name"]
            expr_names["#n"] = "name"

        for field_name in ("notes", "recurrence_type", "recurrence_interval", "anchor_date", "graceful"):
            if field_name in updates:
                set_parts.append(f"{field_name} = :{field_name}")
                expr_values[f":{field_name}"] = updates[field_name]

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
        return self._with_status(attributes, tz)

    def complete_task(
        self, user_id: str, task_id: str, tz: Optional[str] = None, now: Optional[Any] = None
    ) -> Optional[Dict[str, Any]]:
        """Mark a task complete for its current window (recurring) or lifetime (one-shot)."""
        response = self.tasks_table.get_item(Key={"user_id": user_id, "task_id": task_id})
        task = response.get("Item")
        if not task:
            return None
        task = self._deserialize_task(task)

        now_local = local_now(tz, now)
        set_parts = ["updated_at = :updated_at", "last_completed_at = :completed_at"]
        expr_values = {":updated_at": _now_iso(), ":completed_at": _now_iso()}

        # Recurring tasks record *which* window was completed so they reappear
        # once the window rolls over.
        if task.get("recurrence_type", "none") != "none":
            set_parts.append("last_completed_window = :window")
            expr_values[":window"] = current_window_key(task, now_local)

        response = self.tasks_table.update_item(
            Key={"user_id": user_id, "task_id": task_id},
            UpdateExpression="SET " + ", ".join(set_parts),
            ExpressionAttributeValues=expr_values,
            ReturnValues="ALL_NEW",
        )
        logger.info(f"Completed task: {task_id} for user: {user_id}")
        return self._with_status(response["Attributes"], tz, now)

    def uncomplete_task(
        self, user_id: str, task_id: str, tz: Optional[str] = None, now: Optional[Any] = None
    ) -> Optional[Dict[str, Any]]:
        """Undo completion for the current window, making the task active again."""
        response = self.tasks_table.get_item(Key={"user_id": user_id, "task_id": task_id})
        if not response.get("Item"):
            return None

        response = self.tasks_table.update_item(
            Key={"user_id": user_id, "task_id": task_id},
            UpdateExpression="SET updated_at = :updated_at REMOVE last_completed_at, last_completed_window",
            ExpressionAttributeValues={":updated_at": _now_iso()},
            ReturnValues="ALL_NEW",
        )
        logger.info(f"Uncompleted task: {task_id} for user: {user_id}")
        return self._with_status(response["Attributes"], tz, now)

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


class ReportService:
    """Service for managing scheduled-report configs.

    A report stores *what* to report (ordered section rules) and *when* (a simple
    cron-ish schedule). ``next_run`` is computed from the schedule on write and
    advanced after each generation; it backs the periodic sweep's due filter.
    """

    def __init__(self, reports_table):
        self.reports_table = reports_table

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
        report.setdefault("next_run", None)
        report.setdefault("last_run_at", None)
        report["schedule"] = _decimals_to_float(report["schedule"])
        report["sections"] = _decimals_to_float(report["sections"])
        return report

    def create_report(
        self,
        user_id: str,
        name: str,
        schedule: Dict[str, Any],
        sections: List[Dict[str, Any]] = None,
        enabled: bool = True,
        now: Optional[Any] = None,
    ) -> Dict[str, Any]:
        """Create a report, validating its schedule and section rules."""
        sections = sections or []
        validate_schedule(schedule)
        validate_sections(sections)

        next_run = compute_next_run(schedule, now)
        report = Report.create(
            user_id=user_id,
            name=name,
            schedule=schedule,
            sections=sections,
            enabled=enabled,
            next_run=next_run,
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

        set_parts = ["updated_at = :updated_at"]
        expr_values = {":updated_at": _now_iso()}
        expr_names = {}

        if "name" in updates:
            set_parts.append("#n = :name")
            expr_values[":name"] = updates["name"]
            expr_names["#n"] = "name"

        for field_name in ("enabled", "sections"):
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


class ReportGenerator:
    """Renders a report config into a message (the in-app delivery sink).

    This is the seam the Slack integration will extend: today ``generate`` writes
    the rendered message to the message log; a Slack sink will later consume the
    same rendered :class:`Message` (see ``docs/slack-integration-plan.md``'s
    ``post_message`` boundary). Section rules are resolved against live data at
    generation time via the injected services, then snapshotted into the message.
    """

    def __init__(self, report_service, message_service, task_service, item_service):
        self.report_service = report_service
        self.message_service = message_service
        # Exposed as attributes so section renderers can reach the service layer.
        self.task_service = task_service
        self.item_service = item_service

    def generate(
        self, report: Dict[str, Any], tz: Optional[str] = None, now: Optional[Any] = None
    ) -> Dict[str, Any]:
        """Render one report into a message and persist it.

        Advances the report's next_run / last_run_at. Returns the created message.
        """
        user_id = report["user_id"]
        rendered_sections = [
            render_section(section, user_id, self, tz)
            for section in report.get("sections", [])
        ]
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
        return message
