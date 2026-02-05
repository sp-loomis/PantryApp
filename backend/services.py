"""
Service layer for the Pantry App.
Handles business logic and DynamoDB operations.
"""

from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta
from decimal import Decimal

from boto3.dynamodb.conditions import Key, Attr
from aws_lambda_powertools import Logger

from models import Item, Location, ItemTag
from dimensions import (
    Dimension, DimensionType, validate_dimension, aggregate_dimensions
)

logger = Logger(child=True)


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
        expr_values = {":updated_at": datetime.utcnow().isoformat()}

        if "name" in updates:
            update_expr += ", #n = :name"
            expr_values[":name"] = updates["name"]

        if "description" in updates:
            update_expr += ", description = :description"
            expr_values[":description"] = updates["description"]

        response = self.table.update_item(
            Key={"user_id": user_id, "location_id": location_id},
            UpdateExpression=update_expr,
            ExpressionAttributeValues=expr_values,
            ExpressionAttributeNames={"#n": "name"} if "name" in updates else None,
            ReturnValues="ALL_NEW"
        )

        logger.info(f"Updated location: {location_id} for user: {user_id}")
        return response.get("Attributes")

    def delete_location(self, user_id: str, location_id: str) -> bool:
        """Delete a storage location for a specific user."""
        try:
            self.table.delete_item(Key={"user_id": user_id, "location_id": location_id})
            logger.info(f"Deleted location: {location_id} for user: {user_id}")
            return True
        except Exception as e:
            logger.exception(f"Error deleting location: {location_id}")
            return False


class TagService:
    """Service for managing item tags."""

    def __init__(self, table):
        self.table = table

    def add_tags_to_item(self, user_id: str, item_id: str, tags: List[str]) -> None:
        """Add tags to an item for a specific user."""
        for tag in tags:
            item_tag = ItemTag.create(user_id=user_id, tag_name=tag.lower(), item_id=item_id)
            self.table.put_item(Item=item_tag.to_dict())

        logger.info(f"Added {len(tags)} tags to item: {item_id} for user: {user_id}")

    def remove_tags_from_item(self, user_id: str, item_id: str, tags: List[str]) -> None:
        """Remove tags from an item for a specific user."""
        for tag in tags:
            composite_key = f"tag:{tag.lower()}#item:{item_id}"
            self.table.delete_item(
                Key={"user_id": user_id, "tag_item_composite": composite_key}
            )

        logger.info(f"Removed {len(tags)} tags from item: {item_id} for user: {user_id}")

    def get_tags_for_item(self, user_id: str, item_id: str) -> List[str]:
        """Get all tags for an item for a specific user."""
        response = self.table.query(
            IndexName="ItemTagsIndex",
            KeyConditionExpression=Key("user_id").eq(user_id) & Key("item_id").eq(item_id)
        )
        return [item["tag_name"] for item in response.get("Items", [])]

    def get_items_by_tag(self, user_id: str, tag: str) -> List[str]:
        """Get all item IDs with a specific tag for a specific user."""
        response = self.table.query(
            IndexName="TagIndex",
            KeyConditionExpression=Key("user_id").eq(user_id) & Key("tag_name").eq(tag.lower())
        )
        return [item["item_id"] for item in response.get("Items", [])]


class ItemService:
    """Service for managing inventory items."""

    def __init__(self, items_table, tags_table):
        self.items_table = items_table
        self.tag_service = TagService(tags_table)

    def create_item(
        self,
        user_id: str,
        name: str,
        location_id: str,
        quantity: float = 1.0,
        unit: str = "unit",
        dimensions: List[Dict[str, Any]] = None,
        use_by_date: Optional[str] = None,
        tags: List[str] = None,
        notes: str = ""
    ) -> Dict[str, Any]:
        """Create a new inventory item with optional dimensions for a specific user."""
        # Debug logging
        logger.info(f"create_item called with dimensions: {dimensions}")

        # Validate dimensions if provided
        if dimensions:
            for dim in dimensions:
                if not validate_dimension(dim.get("dimension_type"), dim.get("unit")):
                    raise ValueError(f"Invalid dimension: {dim}")

            # Ensure no duplicate dimension types
            dim_types = [d.get("dimension_type") for d in dimensions]
            if len(dim_types) != len(set(dim_types)):
                raise ValueError("Duplicate dimension types not allowed")

        item = Item.create(
            user_id=user_id,
            name=name,
            location_id=location_id,
            quantity=Decimal(str(quantity)),
            unit=unit,
            dimensions=dimensions if dimensions is not None else [],
            use_by_date=use_by_date,
            notes=notes
        )

        item_dict = item.to_dict()
        logger.info(f"Item dict before Decimal conversion: {item_dict}")
        item_dict["quantity"] = Decimal(str(item_dict["quantity"]))

        # Convert dimension values to Decimal for DynamoDB
        if "dimensions" in item_dict and item_dict["dimensions"]:
            for dim in item_dict["dimensions"]:
                if "value" in dim:
                    dim["value"] = Decimal(str(dim["value"]))

        logger.info(f"Item dict after Decimal conversion (about to write to DynamoDB): {item_dict}")
        self.items_table.put_item(Item=item_dict)
        logger.info("Successfully wrote item to DynamoDB")

        if tags:
            self.tag_service.add_tags_to_item(user_id, item.item_id, tags)

        logger.info(f"Created item: {item.item_id} for user: {user_id}")
        return item.to_dict()

    def get_item(self, user_id: str, item_id: str) -> Optional[Dict[str, Any]]:
        """Get an item by ID for a specific user."""
        response = self.items_table.get_item(
            Key={"user_id": user_id, "item_id": item_id}
        )
        item = response.get("Item")
        if not item:
            return None

        # Convert Decimal to float for JSON serialization
        if "quantity" in item:
            item["quantity"] = float(item["quantity"])

        # Convert dimension values from Decimal to float
        if "dimensions" in item and item["dimensions"]:
            for dim in item["dimensions"]:
                if "value" in dim:
                    dim["value"] = float(dim["value"])

        # Add tags
        item["tags"] = self.tag_service.get_tags_for_item(user_id, item_id)
        return item

    def list_all_items(self, user_id: str) -> List[Dict[str, Any]]:
        """List all items for a specific user."""
        response = self.items_table.query(
            KeyConditionExpression=Key("user_id").eq(user_id)
        )
        items = response.get("Items", [])

        # Convert Decimal to float and add tags
        for item in items:
            if "quantity" in item:
                item["quantity"] = float(item["quantity"])
            # Convert dimension values from Decimal to float
            if "dimensions" in item and item["dimensions"]:
                for dim in item["dimensions"]:
                    if "value" in dim:
                        dim["value"] = float(dim["value"])
            item["tags"] = self.tag_service.get_tags_for_item(user_id, item["item_id"])

        return items

    def get_items_by_location(self, user_id: str, location_id: str) -> List[Dict[str, Any]]:
        """Get all items in a specific location for a specific user."""
        response = self.items_table.query(
            IndexName="LocationIndex",
            KeyConditionExpression=Key("user_id").eq(user_id) & Key("location_id").eq(location_id)
        )
        items = response.get("Items", [])

        for item in items:
            if "quantity" in item:
                item["quantity"] = float(item["quantity"])
            # Convert dimension values from Decimal to float
            if "dimensions" in item and item["dimensions"]:
                for dim in item["dimensions"]:
                    if "value" in dim:
                        dim["value"] = float(dim["value"])
            item["tags"] = self.tag_service.get_tags_for_item(user_id, item["item_id"])

        return items

    def get_items_by_tag(self, user_id: str, tag: str) -> List[Dict[str, Any]]:
        """Get all items with a specific tag for a specific user."""
        item_ids = self.tag_service.get_items_by_tag(user_id, tag)
        items = []

        for item_id in item_ids:
            item = self.get_item(user_id, item_id)
            if item:
                items.append(item)

        return items

    def search_items_by_name(self, user_id: str, name: str) -> List[Dict[str, Any]]:
        """Search items by name for a specific user."""
        response = self.items_table.query(
            IndexName="ItemNameIndex",
            KeyConditionExpression=Key("user_id").eq(user_id) & Key("item_name").eq(name.lower())
        )
        items = response.get("Items", [])

        for item in items:
            if "quantity" in item:
                item["quantity"] = float(item["quantity"])
            # Convert dimension values from Decimal to float
            if "dimensions" in item and item["dimensions"]:
                for dim in item["dimensions"]:
                    if "value" in dim:
                        dim["value"] = float(dim["value"])
            item["tags"] = self.tag_service.get_tags_for_item(user_id, item["item_id"])

        return items

    def get_expiring_items(self, user_id: str, location_id: Optional[str] = None, days: int = 7) -> List[Dict[str, Any]]:
        """Get items expiring within the specified number of days for a specific user."""
        cutoff_date = (datetime.utcnow() + timedelta(days=days)).isoformat()

        if location_id:
            response = self.items_table.query(
                IndexName="UseByDateIndex",
                KeyConditionExpression=Key("user_id").eq(user_id) & Key("use_by_date").lte(cutoff_date)
            )
        else:
            response = self.items_table.query(
                KeyConditionExpression=Key("user_id").eq(user_id),
                FilterExpression=Attr("use_by_date").lte(cutoff_date) & Attr("use_by_date").exists()
            )

        items = response.get("Items", [])

        for item in items:
            if "quantity" in item:
                item["quantity"] = float(item["quantity"])
            # Convert dimension values from Decimal to float
            if "dimensions" in item and item["dimensions"]:
                for dim in item["dimensions"]:
                    if "value" in dim:
                        dim["value"] = float(dim["value"])
            item["tags"] = self.tag_service.get_tags_for_item(user_id, item["item_id"])

        return items

    def update_item(self, user_id: str, item_id: str, updates: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Update an item, including dimensions, for a specific user."""
        item = self.get_item(user_id, item_id)
        if not item:
            return None

        update_expr = "SET updated_at = :updated_at"
        expr_values = {":updated_at": datetime.utcnow().isoformat()}
        expr_names = {}

        if "name" in updates:
            update_expr += ", #n = :name, item_name = :item_name"
            expr_values[":name"] = updates["name"]
            expr_values[":item_name"] = updates["name"].lower()
            expr_names["#n"] = "name"

        if "location_id" in updates:
            update_expr += ", location_id = :location_id"
            expr_values[":location_id"] = updates["location_id"]

        if "quantity" in updates:
            update_expr += ", quantity = :quantity"
            expr_values[":quantity"] = Decimal(str(updates["quantity"]))

        if "unit" in updates:
            update_expr += ", #u = :unit"
            expr_values[":unit"] = updates["unit"]
            expr_names["#u"] = "unit"

        if "dimensions" in updates:
            # Validate dimensions
            dimensions = updates["dimensions"]
            for dim in dimensions:
                if not validate_dimension(dim.get("dimension_type"), dim.get("unit")):
                    raise ValueError(f"Invalid dimension: {dim}")

            # Ensure no duplicate dimension types
            dim_types = [d.get("dimension_type") for d in dimensions]
            if len(dim_types) != len(set(dim_types)):
                raise ValueError("Duplicate dimension types not allowed")

            # Convert dimension values to Decimal for DynamoDB
            for dim in dimensions:
                if "value" in dim:
                    dim["value"] = Decimal(str(dim["value"]))

            update_expr += ", dimensions = :dimensions"
            expr_values[":dimensions"] = dimensions

        if "use_by_date" in updates:
            update_expr += ", use_by_date = :use_by_date"
            expr_values[":use_by_date"] = updates["use_by_date"]

        if "notes" in updates:
            update_expr += ", notes = :notes"
            expr_values[":notes"] = updates["notes"]

        response = self.items_table.update_item(
            Key={"user_id": user_id, "item_id": item_id},
            UpdateExpression=update_expr,
            ExpressionAttributeValues=expr_values,
            ExpressionAttributeNames=expr_names if expr_names else None,
            ReturnValues="ALL_NEW"
        )

        # Handle tags update
        if "tags" in updates:
            old_tags = set(item.get("tags", []))
            new_tags = set(updates["tags"])

            tags_to_add = new_tags - old_tags
            tags_to_remove = old_tags - new_tags

            if tags_to_add:
                self.tag_service.add_tags_to_item(user_id, item_id, list(tags_to_add))
            if tags_to_remove:
                self.tag_service.remove_tags_from_item(user_id, item_id, list(tags_to_remove))

        logger.info(f"Updated item: {item_id} for user: {user_id}")
        updated_item = response.get("Attributes")

        if updated_item and "quantity" in updated_item:
            updated_item["quantity"] = float(updated_item["quantity"])
        # Convert dimension values from Decimal to float
        if updated_item and "dimensions" in updated_item and updated_item["dimensions"]:
            for dim in updated_item["dimensions"]:
                if "value" in dim:
                    dim["value"] = float(dim["value"])
        updated_item["tags"] = self.tag_service.get_tags_for_item(user_id, item_id)

        return updated_item

    def delete_item(self, user_id: str, item_id: str) -> bool:
        """Delete an item for a specific user."""
        item = self.get_item(user_id, item_id)
        if not item:
            return False

        try:
            # Remove all tags
            tags = self.tag_service.get_tags_for_item(user_id, item_id)
            if tags:
                self.tag_service.remove_tags_from_item(user_id, item_id, tags)

            # Delete the item
            self.items_table.delete_item(
                Key={"user_id": user_id, "item_id": item_id}
            )

            logger.info(f"Deleted item: {item_id} for user: {user_id}")
            return True
        except Exception as e:
            logger.exception(f"Error deleting item: {item_id}")
            return False

    def search_items(
        self,
        user_id: str,
        name: Optional[str] = None,
        location_id: Optional[str] = None,
        tags: List[str] = None,
        use_by_date_start: Optional[str] = None,
        use_by_date_end: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """Advanced search for items for a specific user."""
        # Start with all items (or filter by most selective criteria)
        if name:
            items = self.search_items_by_name(user_id, name)
        elif location_id:
            items = self.get_items_by_location(user_id, location_id)
        else:
            items = self.list_all_items(user_id)

        # Apply additional filters
        if location_id and not name:
            items = [item for item in items if item["location_id"] == location_id]

        if tags:
            items = [
                item for item in items
                if any(tag in item.get("tags", []) for tag in tags)
            ]

        if use_by_date_start:
            items = [
                item for item in items
                if item.get("use_by_date") and item["use_by_date"] >= use_by_date_start
            ]

        if use_by_date_end:
            items = [
                item for item in items
                if item.get("use_by_date") and item["use_by_date"] <= use_by_date_end
            ]

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
        if location_id:
            items = self.get_items_by_location(user_id, location_id)
        elif tag:
            items = self.get_items_by_tag(user_id, tag)
        else:
            items = self.list_all_items(user_id)

        total_items = len(items)
        total_quantity = sum(item.get("quantity", 0) for item in items)
        items_with_expiry = sum(1 for item in items if item.get("use_by_date"))

        # Legacy: Group by unit
        quantities_by_unit = {}
        for item in items:
            unit = item.get("unit", "unit")
            quantity = item.get("quantity", 0)
            quantities_by_unit[unit] = quantities_by_unit.get(unit, 0) + quantity

        # New: Aggregate dimensions
        aggregated_dimensions = aggregate_dimensions(items)

        # Convert to requested units if specified
        if requested_units:
            for dim_type_str, target_unit in requested_units.items():
                if dim_type_str in aggregated_dimensions:
                    dim = aggregated_dimensions[dim_type_str]
                    base_value = dim.to_base_unit()
                    dim_type = DimensionType(dim_type_str)
                    aggregated_dimensions[dim_type_str] = Dimension.from_base_unit(
                        dim_type, base_value, target_unit
                    )

        # Convert dimensions to dict format
        dimensions_dict = {
            dim_type: dim.to_dict()
            for dim_type, dim in aggregated_dimensions.items()
        }

        return {
            "total_items": total_items,
            "total_quantity": total_quantity,
            "items_with_expiry": items_with_expiry,
            "quantities_by_unit": quantities_by_unit,
            "aggregated_dimensions": dimensions_dict
        }
