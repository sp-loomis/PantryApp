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

logger = Logger(child=True)


class LocationService:
    """Service for managing storage locations."""

    def __init__(self, table):
        self.table = table

    def create_location(self, name: str, description: str = "") -> Dict[str, Any]:
        """Create a new storage location."""
        location = Location.create(name=name, description=description)

        self.table.put_item(Item=location.to_dict())
        logger.info(f"Created location: {location.location_id}")

        return location.to_dict()

    def get_location(self, location_id: str) -> Optional[Dict[str, Any]]:
        """Get a storage location by ID."""
        response = self.table.get_item(Key={"location_id": location_id})
        return response.get("Item")

    def list_locations(self) -> List[Dict[str, Any]]:
        """List all storage locations."""
        response = self.table.scan()
        return response.get("Items", [])

    def update_location(self, location_id: str, updates: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Update a storage location."""
        location = self.get_location(location_id)
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
            Key={"location_id": location_id},
            UpdateExpression=update_expr,
            ExpressionAttributeValues=expr_values,
            ExpressionAttributeNames={"#n": "name"} if "name" in updates else None,
            ReturnValues="ALL_NEW"
        )

        logger.info(f"Updated location: {location_id}")
        return response.get("Attributes")

    def delete_location(self, location_id: str) -> bool:
        """Delete a storage location."""
        try:
            self.table.delete_item(Key={"location_id": location_id})
            logger.info(f"Deleted location: {location_id}")
            return True
        except Exception as e:
            logger.exception(f"Error deleting location: {location_id}")
            return False


class TagService:
    """Service for managing item tags."""

    def __init__(self, table):
        self.table = table

    def add_tags_to_item(self, item_id: str, tags: List[str]) -> None:
        """Add tags to an item."""
        for tag in tags:
            item_tag = ItemTag(tag_name=tag.lower(), item_id=item_id)
            self.table.put_item(Item=item_tag.to_dict())

        logger.info(f"Added {len(tags)} tags to item: {item_id}")

    def remove_tags_from_item(self, item_id: str, tags: List[str]) -> None:
        """Remove tags from an item."""
        for tag in tags:
            self.table.delete_item(
                Key={"tag_name": tag.lower(), "item_id": item_id}
            )

        logger.info(f"Removed {len(tags)} tags from item: {item_id}")

    def get_tags_for_item(self, item_id: str) -> List[str]:
        """Get all tags for an item."""
        response = self.table.query(
            IndexName="ItemTagsIndex",
            KeyConditionExpression=Key("item_id").eq(item_id)
        )
        return [item["tag_name"] for item in response.get("Items", [])]

    def get_items_by_tag(self, tag: str) -> List[str]:
        """Get all item IDs with a specific tag."""
        response = self.table.query(
            KeyConditionExpression=Key("tag_name").eq(tag.lower())
        )
        return [item["item_id"] for item in response.get("Items", [])]


class ItemService:
    """Service for managing inventory items."""

    def __init__(self, items_table, tags_table):
        self.items_table = items_table
        self.tag_service = TagService(tags_table)

    def create_item(
        self,
        name: str,
        location_id: str,
        quantity: float = 1.0,
        unit: str = "unit",
        use_by_date: Optional[str] = None,
        tags: List[str] = None,
        notes: str = ""
    ) -> Dict[str, Any]:
        """Create a new inventory item."""
        item = Item.create(
            name=name,
            location_id=location_id,
            quantity=Decimal(str(quantity)),
            unit=unit,
            use_by_date=use_by_date,
            notes=notes
        )

        item_dict = item.to_dict()
        item_dict["quantity"] = Decimal(str(item_dict["quantity"]))
        self.items_table.put_item(Item=item_dict)

        if tags:
            self.tag_service.add_tags_to_item(item.item_id, tags)

        logger.info(f"Created item: {item.item_id}")
        return item.to_dict()

    def get_item(self, item_id: str) -> Optional[Dict[str, Any]]:
        """Get an item by ID."""
        # Since we need both item_id and created_at for the key, we need to query
        response = self.items_table.query(
            KeyConditionExpression=Key("item_id").eq(item_id)
        )
        items = response.get("Items", [])
        if not items:
            return None

        item = items[0]
        # Convert Decimal to float for JSON serialization
        if "quantity" in item:
            item["quantity"] = float(item["quantity"])

        # Add tags
        item["tags"] = self.tag_service.get_tags_for_item(item_id)
        return item

    def list_all_items(self) -> List[Dict[str, Any]]:
        """List all items."""
        response = self.items_table.scan()
        items = response.get("Items", [])

        # Convert Decimal to float and add tags
        for item in items:
            if "quantity" in item:
                item["quantity"] = float(item["quantity"])
            item["tags"] = self.tag_service.get_tags_for_item(item["item_id"])

        return items

    def get_items_by_location(self, location_id: str) -> List[Dict[str, Any]]:
        """Get all items in a specific location."""
        response = self.items_table.query(
            IndexName="LocationIndex",
            KeyConditionExpression=Key("location_id").eq(location_id)
        )
        items = response.get("Items", [])

        for item in items:
            if "quantity" in item:
                item["quantity"] = float(item["quantity"])
            item["tags"] = self.tag_service.get_tags_for_item(item["item_id"])

        return items

    def get_items_by_tag(self, tag: str) -> List[Dict[str, Any]]:
        """Get all items with a specific tag."""
        item_ids = self.tag_service.get_items_by_tag(tag)
        items = []

        for item_id in item_ids:
            item = self.get_item(item_id)
            if item:
                items.append(item)

        return items

    def search_items_by_name(self, name: str) -> List[Dict[str, Any]]:
        """Search items by name."""
        response = self.items_table.query(
            IndexName="ItemNameIndex",
            KeyConditionExpression=Key("item_name").eq(name.lower())
        )
        items = response.get("Items", [])

        for item in items:
            if "quantity" in item:
                item["quantity"] = float(item["quantity"])
            item["tags"] = self.tag_service.get_tags_for_item(item["item_id"])

        return items

    def get_expiring_items(self, location_id: Optional[str] = None, days: int = 7) -> List[Dict[str, Any]]:
        """Get items expiring within the specified number of days."""
        cutoff_date = (datetime.utcnow() + timedelta(days=days)).isoformat()

        if location_id:
            response = self.items_table.query(
                IndexName="UseByDateIndex",
                KeyConditionExpression=Key("location_id").eq(location_id) & Key("use_by_date").lte(cutoff_date)
            )
        else:
            response = self.items_table.scan(
                FilterExpression=Attr("use_by_date").lte(cutoff_date) & Attr("use_by_date").exists()
            )

        items = response.get("Items", [])

        for item in items:
            if "quantity" in item:
                item["quantity"] = float(item["quantity"])
            item["tags"] = self.tag_service.get_tags_for_item(item["item_id"])

        return items

    def update_item(self, item_id: str, updates: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Update an item."""
        item = self.get_item(item_id)
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

        if "use_by_date" in updates:
            update_expr += ", use_by_date = :use_by_date"
            expr_values[":use_by_date"] = updates["use_by_date"]

        if "notes" in updates:
            update_expr += ", notes = :notes"
            expr_values[":notes"] = updates["notes"]

        response = self.items_table.update_item(
            Key={"item_id": item_id, "created_at": item["created_at"]},
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
                self.tag_service.add_tags_to_item(item_id, list(tags_to_add))
            if tags_to_remove:
                self.tag_service.remove_tags_from_item(item_id, list(tags_to_remove))

        logger.info(f"Updated item: {item_id}")
        updated_item = response.get("Attributes")

        if updated_item and "quantity" in updated_item:
            updated_item["quantity"] = float(updated_item["quantity"])
        updated_item["tags"] = self.tag_service.get_tags_for_item(item_id)

        return updated_item

    def delete_item(self, item_id: str) -> bool:
        """Delete an item."""
        item = self.get_item(item_id)
        if not item:
            return False

        try:
            # Remove all tags
            tags = self.tag_service.get_tags_for_item(item_id)
            if tags:
                self.tag_service.remove_tags_from_item(item_id, tags)

            # Delete the item
            self.items_table.delete_item(
                Key={"item_id": item_id, "created_at": item["created_at"]}
            )

            logger.info(f"Deleted item: {item_id}")
            return True
        except Exception as e:
            logger.exception(f"Error deleting item: {item_id}")
            return False

    def search_items(
        self,
        name: Optional[str] = None,
        location_id: Optional[str] = None,
        tags: List[str] = None,
        use_by_date_start: Optional[str] = None,
        use_by_date_end: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """Advanced search for items."""
        # Start with all items (or filter by most selective criteria)
        if name:
            items = self.search_items_by_name(name)
        elif location_id:
            items = self.get_items_by_location(location_id)
        else:
            items = self.list_all_items()

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

    def get_aggregate_stats(self, location_id: Optional[str] = None, tag: Optional[str] = None) -> Dict[str, Any]:
        """Get aggregate statistics for inventory."""
        if location_id:
            items = self.get_items_by_location(location_id)
        elif tag:
            items = self.get_items_by_tag(tag)
        else:
            items = self.list_all_items()

        total_items = len(items)
        total_quantity = sum(item.get("quantity", 0) for item in items)
        items_with_expiry = sum(1 for item in items if item.get("use_by_date"))

        # Group by unit
        quantities_by_unit = {}
        for item in items:
            unit = item.get("unit", "unit")
            quantity = item.get("quantity", 0)
            quantities_by_unit[unit] = quantities_by_unit.get(unit, 0) + quantity

        return {
            "total_items": total_items,
            "total_quantity": total_quantity,
            "items_with_expiry": items_with_expiry,
            "quantities_by_unit": quantities_by_unit
        }
