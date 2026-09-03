"""
Data models for the Pantry App.
"""

from dataclasses import dataclass, field
from typing import Optional, List, Dict, Any
from datetime import datetime, timezone
import uuid


@dataclass
class Location:
    """Storage location model."""
    user_id: str
    location_id: str
    name: str
    description: str = ""
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    updated_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    @classmethod
    def create(cls, user_id: str, name: str, description: str = "") -> "Location":
        """Create a new Location instance."""
        return cls(
            user_id=user_id,
            location_id=str(uuid.uuid4()),
            name=name,
            description=description
        )

    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "user_id": self.user_id,
            "location_id": self.location_id,
            "name": self.name,
            "description": self.description,
            "created_at": self.created_at,
            "updated_at": self.updated_at
        }


@dataclass
class Item:
    """Inventory item model with support for multiple dimensions."""
    user_id: str
    item_id: str
    name: str
    location_id: str
    dimensions: List[Dict[str, Any]] = field(default_factory=list)
    tags: List[str] = field(default_factory=list)  # Denormalized tags for read efficiency
    use_by_date: Optional[str] = None
    notes: str = ""
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    updated_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    @classmethod
    def create(
        cls,
        user_id: str,
        name: str,
        location_id: str,
        dimensions: List[Dict[str, Any]] = None,
        tags: List[str] = None,
        use_by_date: Optional[str] = None,
        notes: str = ""
    ) -> "Item":
        """Create a new Item instance."""
        return cls(
            user_id=user_id,
            item_id=str(uuid.uuid4()),
            name=name,
            location_id=location_id,
            dimensions=dimensions or [],
            tags=tags or [],
            use_by_date=use_by_date,
            notes=notes
        )

    def to_dict(self) -> dict:
        """Convert to dictionary."""
        result = {
            "user_id": self.user_id,
            "item_id": self.item_id,
            "name": self.name,
            "location_id": self.location_id,
            "tags": self.tags,
            "use_by_date": self.use_by_date,
            "notes": self.notes,
            "created_at": self.created_at,
            "updated_at": self.updated_at
        }
        if self.dimensions:
            result["dimensions"] = self.dimensions
        return result


@dataclass
class ItemTag:
    """Item-tag relationship model."""
    user_id: str
    tag_name: str
    item_id: str
    tag_item_composite: str  # Composite key: "tag:<tag>#item:<item_id>"
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    @classmethod
    def create(cls, user_id: str, tag_name: str, item_id: str) -> "ItemTag":
        """Create a new ItemTag instance."""
        composite = f"tag:{tag_name}#item:{item_id}"
        return cls(
            user_id=user_id,
            tag_name=tag_name,
            item_id=item_id,
            tag_item_composite=composite
        )

    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "user_id": self.user_id,
            "tag_name": self.tag_name,
            "item_id": self.item_id,
            "tag_item_composite": self.tag_item_composite,
            "created_at": self.created_at
        }
