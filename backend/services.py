"""
Service layer for the Pantry App.
Handles business logic and DynamoDB operations.
"""

from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta, timezone
from decimal import Decimal

from boto3.dynamodb.conditions import Key, Attr
from aws_lambda_powertools import Logger

from models import Item, Location, ItemTag
from dimensions import (
    Dimension, DimensionType, validate_dimension, aggregate_dimensions
)
from search import match_name, DEFAULT_MIN_SCORE

logger = Logger(child=True)


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

    def create_item(
        self,
        user_id: str,
        name: str,
        location_id: str,
        dimensions: List[Dict[str, Any]] = None,
        use_by_date: Optional[str] = None,
        tags: List[str] = None,
        notes: str = ""
    ) -> Dict[str, Any]:
        """Create a new inventory item with optional dimensions for a specific user."""
        dimensions = dimensions or []
        tags = [t.lower() for t in (tags or [])]

        self._validate_dimensions(dimensions)

        item = Item.create(
            user_id=user_id,
            name=name,
            location_id=location_id,
            dimensions=dimensions,
            tags=tags,
            use_by_date=use_by_date,
            notes=notes
        )

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
            self.tag_service.add_tags_to_item(user_id, item.item_id, tags)

        logger.info(f"Created item: {item.item_id} for user: {user_id}")
        return self._deserialize_item(item.to_dict())

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
