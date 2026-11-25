"""
Data models for the Pantry App.
"""

from dataclasses import dataclass, field
from typing import Optional, List, Dict, Any
from datetime import datetime, timezone
import uuid


def now_iso() -> str:
    """Current UTC time as a full ISO-8601 string (the one timestamp convention).

    Shared by the model ``created_at``/``updated_at`` defaults and the service
    layer (``services._now_iso``) so every timestamp is minted identically.
    """
    return datetime.now(timezone.utc).isoformat()


@dataclass
class Location:
    """Storage location model."""
    user_id: str
    location_id: str
    name: str
    description: str = ""
    created_at: str = field(default_factory=now_iso)
    updated_at: str = field(default_factory=now_iso)

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
class Category:
    """Item category model.

    A category declares a single ``measure_type`` (``count`` / ``weight`` /
    ``volume``, matching :class:`dimensions.DimensionType`). Items assigned to it
    must carry a dimension of that type. Aggregation over a category rolls those
    dimensions up: ``count`` reports the *number of items*; ``weight`` / ``volume``
    sum the matching dimension and convert to ``preferred_unit``.

    ``preferred_unit`` is only meaningful for weight/volume (the reporting target
    unit); it is ignored for ``count`` and stored as None there.
    """
    user_id: str
    category_id: str
    name: str
    measure_type: str
    preferred_unit: Optional[str] = None
    description: str = ""
    created_at: str = field(default_factory=now_iso)
    updated_at: str = field(default_factory=now_iso)

    @classmethod
    def create(
        cls,
        user_id: str,
        name: str,
        measure_type: str,
        preferred_unit: Optional[str] = None,
        description: str = "",
    ) -> "Category":
        """Create a new Category instance."""
        return cls(
            user_id=user_id,
            category_id=str(uuid.uuid4()),
            name=name,
            measure_type=measure_type,
            preferred_unit=preferred_unit,
            description=description,
        )

    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "user_id": self.user_id,
            "category_id": self.category_id,
            "name": self.name,
            "measure_type": self.measure_type,
            "preferred_unit": self.preferred_unit,
            "description": self.description,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
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
    category_id: Optional[str] = None  # At most one category (FK to Category)
    use_by_date: Optional[str] = None
    notes: str = ""
    # Soft-delete marker: absent (None) means active. Set on delete/depletion so
    # history and the ledger are preserved; filtered out of live reads.
    deleted_at: Optional[str] = None
    created_at: str = field(default_factory=now_iso)
    updated_at: str = field(default_factory=now_iso)

    @classmethod
    def create(
        cls,
        user_id: str,
        name: str,
        location_id: str,
        dimensions: List[Dict[str, Any]] = None,
        tags: List[str] = None,
        category_id: Optional[str] = None,
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
            category_id=category_id,
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
        # category_id backs a sparse GSI: omit the attribute entirely when unset
        # (a NULL value is rejected on an index key).
        if self.category_id:
            result["category_id"] = self.category_id
        return result


@dataclass
class Task:
    """Task model: cadence-based reminders and dateless to-dos.

    Two kinds of task share this row:

    - A **reminder** (``recurrence_type`` ``daily``/``weekly``/``interval``) is
      stored as a single row plus a recurrence rule; whether it is done "for
      now" is computed on read from the current time, never materialized as
      per-occurrence rows. It is present each window until marked off and resets
      when the window rolls (a missed window never piles up). See
      ``recurrence.py`` for the window logic.
    - A **to-do** (``recurrence_type`` ``none``) has no date: it simply stays on
      the active list until it is marked done.

    - ``recurrence_type``: ``none`` (to-do), ``daily``, ``weekly`` or
      ``interval`` (every ``recurrence_interval`` days from ``anchor_date``).
    - ``last_completed_window`` / ``last_completed_at``: current-state
      completion markers (no history is kept).
    - ``answer_mode``: ``checkbox`` (plain done/not-done) or ``yesno`` (a
      *decision* — completing it records a Yes/No answer in ``last_decision``).
    - ``last_decision``: ``yes``/``no``/None — the current-window (or one-shot)
      answer to a decision task, recorded alongside the completion markers. No
      history is kept, mirroring ``last_completed_window``.
    - ``trigger``: an optional dependency on another task's decision. When set the
      task is *dormant* until its source is answered a matching way, and it
      borrows the source's recurrence window for activation and completion-reset.
      See ``recurrence.py`` for the resolution logic. Shape::

          { "source_task_id": str,
            "on": "yes" | "no" | "any",
            "deadline": "same_day" | "same_week" | "offset",
            "offset_days": int }   # required only when deadline == "offset"
    """
    user_id: str
    task_id: str
    name: str
    notes: str = ""
    tags: List[str] = field(default_factory=list)  # Denormalized tags for filtering
    recurrence_type: str = "none"  # none | daily | weekly | interval
    recurrence_interval: Optional[int] = None  # every N days, for interval tasks
    anchor_date: Optional[str] = None  # ISO date; window anchor for interval tasks
    last_completed_window: Optional[str] = None  # recurring: window key last completed
    last_completed_at: Optional[str] = None  # last completion timestamp
    answer_mode: str = "checkbox"  # checkbox | yesno (decision task)
    last_decision: Optional[str] = None  # yes | no | None (decision answer)
    trigger: Optional[dict] = None  # dependency on another task's decision
    # Soft-delete marker: absent (None) = active. Filtered out of live reads.
    deleted_at: Optional[str] = None
    created_at: str = field(default_factory=now_iso)
    updated_at: str = field(default_factory=now_iso)

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
        answer_mode: str = "checkbox",
        trigger: Optional[dict] = None,
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
            answer_mode=answer_mode,
            trigger=trigger,
        )

    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "user_id": self.user_id,
            "task_id": self.task_id,
            "name": self.name,
            "notes": self.notes,
            "tags": self.tags,
            "recurrence_type": self.recurrence_type,
            "recurrence_interval": self.recurrence_interval,
            "anchor_date": self.anchor_date,
            "last_completed_window": self.last_completed_window,
            "last_completed_at": self.last_completed_at,
            "answer_mode": self.answer_mode,
            "last_decision": self.last_decision,
            "trigger": self.trigger,
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

    - ``schedule``: ``{ frequency: daily|weekly|monthly, time_of_day: "HH:00"
      (on the hour; sweep runs hourly),
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
    # Optional delivery destinations beyond the in-app message log, e.g.
    # {"slack": {"connection_id": ..., "channel_id": ...}}. Empty = in-app only.
    delivery: Dict[str, Any] = field(default_factory=dict)
    # Optional conditional gate. When non-empty, the sweep generates the report
    # only if the trigger evaluates true against live data. Shape:
    # {"match": "all"|"any", "conditions": [{"source": "item"|"task",
    #  "query": {...}, "match": "all"|"any", "inequalities": [...]}]}. An "item"
    # condition (the default when "source" is absent) has category-keyed
    # inequalities {"category_id", "operator": "below"|"above", "threshold"}; a
    # "task" condition fires on the matching-task count with inequalities
    # {"operator", "threshold"} (no category_id).
    # Empty = no gate (fire on schedule). See report_conditions.evaluate_trigger.
    trigger: Dict[str, Any] = field(default_factory=dict)
    next_run: Optional[str] = None
    last_run_at: Optional[str] = None
    created_at: str = field(default_factory=now_iso)
    updated_at: str = field(default_factory=now_iso)

    @classmethod
    def create(
        cls,
        user_id: str,
        name: str,
        schedule: Dict[str, Any] = None,
        sections: List[Dict[str, Any]] = None,
        enabled: bool = True,
        next_run: Optional[str] = None,
        delivery: Dict[str, Any] = None,
        trigger: Dict[str, Any] = None,
    ) -> "Report":
        """Create a new Report instance."""
        return cls(
            user_id=user_id,
            report_id=str(uuid.uuid4()),
            name=name,
            enabled=enabled,
            schedule=schedule or {},
            sections=sections or [],
            delivery=delivery or {},
            trigger=trigger or {},
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
            "delivery": self.delivery,
            "trigger": self.trigger,
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
    created_at: str = field(default_factory=now_iso)

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
class SlackConnection:
    """A user's connected Slack workspace (bring-your-own-Slack, OAuth v2).

    One row per installed workspace, scoped by ``user_id`` (Cognito sub) so one
    customer's connection can never post into another's Slack. The bot token is
    stored ONLY as ciphertext (``bot_token_cipher`` — KMS-encrypted, base64) and
    is never returned by the API: response shapes come from ``to_public_dict``,
    which omits it. See ``SlackService`` for the encrypt/decrypt seam.

    - ``connection_id``: uuid range key (allows >1 workspace per user later).
    - ``scopes``: space/comma-delimited bot scopes granted at install.
    - ``authed_user_id``: the Slack user who performed the install.
    """
    user_id: str
    connection_id: str
    team_id: str
    team_name: str
    bot_token_cipher: str
    bot_user_id: str = ""
    scopes: str = ""
    authed_user_id: str = ""
    created_at: str = field(default_factory=now_iso)
    updated_at: str = field(default_factory=now_iso)

    @classmethod
    def create(
        cls,
        user_id: str,
        team_id: str,
        team_name: str,
        bot_token_cipher: str,
        bot_user_id: str = "",
        scopes: str = "",
        authed_user_id: str = "",
    ) -> "SlackConnection":
        """Create a new SlackConnection instance."""
        return cls(
            user_id=user_id,
            connection_id=str(uuid.uuid4()),
            team_id=team_id,
            team_name=team_name,
            bot_token_cipher=bot_token_cipher,
            bot_user_id=bot_user_id,
            scopes=scopes,
            authed_user_id=authed_user_id,
        )

    def to_dict(self) -> dict:
        """Convert to dictionary for storage (includes the token ciphertext)."""
        return {
            "user_id": self.user_id,
            "connection_id": self.connection_id,
            "team_id": self.team_id,
            "team_name": self.team_name,
            "bot_token_cipher": self.bot_token_cipher,
            "bot_user_id": self.bot_user_id,
            "scopes": self.scopes,
            "authed_user_id": self.authed_user_id,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }

    def to_public_dict(self) -> dict:
        """Convert to the API-safe shape — NEVER includes ``bot_token_cipher``."""
        return {
            "connection_id": self.connection_id,
            "team_id": self.team_id,
            "team_name": self.team_name,
            "bot_user_id": self.bot_user_id,
            "scopes": self.scopes,
            "authed_user_id": self.authed_user_id,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }

    @staticmethod
    def public_from_item(item: Dict[str, Any]) -> dict:
        """Strip a stored DynamoDB item down to the API-safe shape.

        Guards against the token ever leaking: whatever else the row holds, only
        the whitelisted public keys are returned.
        """
        return {
            "connection_id": item.get("connection_id"),
            "team_id": item.get("team_id"),
            "team_name": item.get("team_name"),
            "bot_user_id": item.get("bot_user_id", ""),
            "scopes": item.get("scopes", ""),
            "authed_user_id": item.get("authed_user_id", ""),
            "created_at": item.get("created_at"),
            "updated_at": item.get("updated_at"),
        }


# Ledger event types. Items distinguish genuine usage (consumed) from a data
# removal (removed/deleted) and from a plain edit (adjusted).
EVENT_ITEM_CREATED = "item_created"
EVENT_ITEM_ADJUSTED = "item_adjusted"
EVENT_ITEM_CONSUMED = "item_consumed"
EVENT_ITEM_REMOVED = "item_removed"
EVENT_TASK_COMPLETED = "task_completed"
EVENT_TASK_UNCOMPLETED = "task_uncompleted"

ENTITY_ITEM = "item"
ENTITY_TASK = "task"


@dataclass
class LedgerEvent:
    """An append-only domain event (history / analytics source of truth).

    Immutable: rows are only ever inserted, never updated or deleted. Live
    operational reads NEVER consult the ledger — it exists for history and the
    S3/Athena analytics tier only (CQRS-lite, not event sourcing).

    Keys:
    - ``event_sk`` = ``"{occurred_at}#{event_id}"`` — the table range key, giving
      a time-ordered per-user stream.
    - ``entity_sk`` = ``"{entity_type}#{entity_id}#{occurred_at}"`` — the
      EntityIndex range key, for a single item's / task's history.

    ``payload`` carries event-specific data plus denormalized snapshot fields for
    analytics (e.g. item name, location_id, category_id, a dimension delta, or a
    task decision), so Athena queries need not join back to the live tables.
    """
    user_id: str
    entity_type: str  # ENTITY_ITEM | ENTITY_TASK
    entity_id: str
    event_type: str
    event_id: str
    occurred_at: str
    payload: Dict[str, Any] = field(default_factory=dict)

    @classmethod
    def create(
        cls,
        user_id: str,
        entity_type: str,
        entity_id: str,
        event_type: str,
        payload: Optional[Dict[str, Any]] = None,
        occurred_at: Optional[str] = None,
    ) -> "LedgerEvent":
        """Build a new event (fresh id + timestamp unless ``occurred_at`` given)."""
        return cls(
            user_id=user_id,
            entity_type=entity_type,
            entity_id=entity_id,
            event_type=event_type,
            event_id=str(uuid.uuid4()),
            occurred_at=occurred_at or now_iso(),
            payload=payload or {},
        )

    @property
    def event_sk(self) -> str:
        return f"{self.occurred_at}#{self.event_id}"

    @property
    def entity_sk(self) -> str:
        return f"{self.entity_type}#{self.entity_id}#{self.occurred_at}"

    def to_dict(self) -> dict:
        """Convert to the DynamoDB storage shape (includes the index keys)."""
        return {
            "user_id": self.user_id,
            "event_sk": self.event_sk,
            "entity_sk": self.entity_sk,
            "event_id": self.event_id,
            "occurred_at": self.occurred_at,
            "entity_type": self.entity_type,
            "entity_id": self.entity_id,
            "event_type": self.event_type,
            "payload": self.payload,
        }
