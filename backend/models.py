"""
Data models for the Pantry App.
"""

from dataclasses import dataclass, field
from typing import Optional, List
from datetime import datetime, timezone
import uuid


@dataclass
class Location:
    """Storage location model."""
    location_id: str
    name: str
    description: str = ""
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    updated_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    @classmethod
    def create(cls, name: str, description: str = "") -> "Location":
        """Create a new Location instance."""
        return cls(
            location_id=str(uuid.uuid4()),
            name=name,
            description=description
        )

    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "location_id": self.location_id,
            "name": self.name,
            "description": self.description,
            "created_at": self.created_at,
            "updated_at": self.updated_at
        }


@dataclass
class Item:
    """Inventory item model."""
    item_id: str
    name: str
    location_id: str
    item_name: str  # Normalized name for searching
    quantity: float = 1.0
    unit: str = "unit"
    use_by_date: Optional[str] = None
    notes: str = ""
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    updated_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    @classmethod
    def create(
        cls,
        name: str,
        location_id: str,
        quantity: float = 1.0,
        unit: str = "unit",
        use_by_date: Optional[str] = None,
        notes: str = ""
    ) -> "Item":
        """Create a new Item instance."""
        return cls(
            item_id=str(uuid.uuid4()),
            name=name,
            location_id=location_id,
            item_name=name.lower(),  # Normalized for searching
            quantity=quantity,
            unit=unit,
            use_by_date=use_by_date,
            notes=notes
        )

    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "item_id": self.item_id,
            "name": self.name,
            "location_id": self.location_id,
            "item_name": self.item_name,
            "quantity": self.quantity,
            "unit": self.unit,
            "use_by_date": self.use_by_date,
            "notes": self.notes,
            "created_at": self.created_at,
            "updated_at": self.updated_at
        }


@dataclass
class ItemTag:
    """Item-tag relationship model."""
    tag_name: str
    item_id: str
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "tag_name": self.tag_name,
            "item_id": self.item_id,
            "created_at": self.created_at
        }
