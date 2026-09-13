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
class Task:
    """Task/chore model with support for one-shot and recurring schedules.

    A recurring task is stored as a single row plus a recurrence rule; its
    status (and whether it is done "for now") is computed on read from the
    current time, never materialized as per-occurrence rows. See
    ``recurrence.py`` for the window/status logic.

    - ``recurrence_type``: ``none`` (one-shot), ``daily``, ``weekly`` or
      ``interval`` (every ``recurrence_interval`` days from ``anchor_date``).
    - ``due_date``: one-shot deadline (ISO). Backs a sparse GSI, so it is
      omitted from storage when unset (see ``TaskService``).
    - ``graceful``: one-shot only — when True (default) a past-due task
      self-hides from active views instead of nagging as overdue.
    - ``last_completed_window`` / ``last_completed_at``: current-state
      completion markers (no history is kept).
    """
    user_id: str
    task_id: str
    name: str
    notes: str = ""
    tags: List[str] = field(default_factory=list)  # Denormalized tags for filtering
    recurrence_type: str = "none"  # none | daily | weekly | interval
    recurrence_interval: Optional[int] = None  # every N days, for interval tasks
    anchor_date: Optional[str] = None  # ISO date; window anchor for interval tasks
    due_date: Optional[str] = None  # ISO; one-shot deadline (sparse GSI key)
    graceful: bool = True  # one-shot: self-hide once past due
    last_completed_window: Optional[str] = None  # recurring: window key last completed
    last_completed_at: Optional[str] = None  # last completion timestamp
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    updated_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    @classmethod
    def create(
        cls,
        user_id: str,
        name: str,
        notes: str = "",
        tags: List[str] = None,
        recurrence_type: str = "none",
        recurrence_interval: Optional[int] = None,
        anchor_date: Optional[str] = None,
        due_date: Optional[str] = None,
        graceful: bool = True,
    ) -> "Task":
        """Create a new Task instance."""
        return cls(
            user_id=user_id,
            task_id=str(uuid.uuid4()),
            name=name,
            notes=notes,
            tags=tags or [],
            recurrence_type=recurrence_type,
            recurrence_interval=recurrence_interval,
            anchor_date=anchor_date,
            due_date=due_date,
            graceful=graceful,
        )

    def to_dict(self) -> dict:
        """Convert to dictionary.

        ``due_date`` is included as None for a stable response shape; the
        service layer omits it from storage when unset (sparse-index rule).
        """
        return {
            "user_id": self.user_id,
            "task_id": self.task_id,
            "name": self.name,
            "notes": self.notes,
            "tags": self.tags,
            "recurrence_type": self.recurrence_type,
            "recurrence_interval": self.recurrence_interval,
            "anchor_date": self.anchor_date,
            "due_date": self.due_date,
            "graceful": self.graceful,
            "last_completed_window": self.last_completed_window,
            "last_completed_at": self.last_completed_at,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }


@dataclass
class Report:
    """Scheduled-report config model.

    A report is a user-defined rule set that the notification engine renders into
    a :class:`Message` on a schedule. It stores *what* to report (an ordered list
    of section rules) and *when* (a simple cron-ish schedule), never the rendered
    output itself.

    - ``schedule``: ``{ frequency: daily|weekly|monthly, time_of_day: "HH:MM",
      weekday: 0-6 (Mon=0, weekly only), day_of_month: 1-28 (monthly only),
      tz: IANA }``.
    - ``sections``: ordered list of ``{ type, heading, config }`` rules. See
      ``report_sections.py`` for the supported types.
    - ``next_run``: ISO-8601 UTC timestamp of the next scheduled generation.
      Computed from ``schedule`` on write and advanced after each run. Backs the
      sweep's due-report filter.
    - ``last_run_at``: timestamp of the most recent generation (None until run).
    """
    user_id: str
    report_id: str
    name: str
    enabled: bool = True
    schedule: Dict[str, Any] = field(default_factory=dict)
    sections: List[Dict[str, Any]] = field(default_factory=list)
    next_run: Optional[str] = None
    last_run_at: Optional[str] = None
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    updated_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    @classmethod
    def create(
        cls,
        user_id: str,
        name: str,
        schedule: Dict[str, Any] = None,
        sections: List[Dict[str, Any]] = None,
        enabled: bool = True,
        next_run: Optional[str] = None,
    ) -> "Report":
        """Create a new Report instance."""
        return cls(
            user_id=user_id,
            report_id=str(uuid.uuid4()),
            name=name,
            enabled=enabled,
            schedule=schedule or {},
            sections=sections or [],
            next_run=next_run,
        )

    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "user_id": self.user_id,
            "report_id": self.report_id,
            "name": self.name,
            "enabled": self.enabled,
            "schedule": self.schedule,
            "sections": self.sections,
            "next_run": self.next_run,
            "last_run_at": self.last_run_at,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }


@dataclass
class Message:
    """A generated notification/message-log entry.

    Produced by the report engine (or created directly as a system/manual
    message). Its ``sections`` are a *rendered snapshot* of the report's rules
    against live data at generation time — the log shows what was true when the
    report ran, not a live re-query.

    - ``report_id``: the source report (None for manual/system messages).
    - ``sections``: ordered list of rendered ``{ type, heading, content }``.
    - ``read_at``: ISO timestamp when the user marked it read. Backs a sparse
      GSI (``UnreadIndex``), so it is omitted from storage while unread and the
      attribute's absence *is* the unread state. Surfaced as None in responses.
    """
    user_id: str
    message_id: str
    title: str
    sections: List[Dict[str, Any]] = field(default_factory=list)
    report_id: Optional[str] = None
    read_at: Optional[str] = None
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    @classmethod
    def create(
        cls,
        user_id: str,
        title: str,
        sections: List[Dict[str, Any]] = None,
        report_id: Optional[str] = None,
    ) -> "Message":
        """Create a new Message instance."""
        return cls(
            user_id=user_id,
            message_id=str(uuid.uuid4()),
            title=title,
            sections=sections or [],
            report_id=report_id,
        )

    def to_dict(self) -> dict:
        """Convert to dictionary.

        ``read_at`` is included as None for a stable response shape; the service
        layer omits it from storage when unset (sparse-index rule).
        """
        return {
            "user_id": self.user_id,
            "message_id": self.message_id,
            "report_id": self.report_id,
            "title": self.title,
            "sections": self.sections,
            "read_at": self.read_at,
            "created_at": self.created_at,
        }


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
