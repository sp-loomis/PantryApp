"""Report section rule engine.

A report's ``sections`` are ordered *rules* — ``{ type, heading, config }`` — that
the notification engine renders into a message's ``sections`` — rendered snapshots
``{ type, heading, content }`` — against live data at generation time.

This module is the extensible registry of section types. Each renderer is a pure
function ``fn(user_id, config, services, tz) -> content_dict`` where ``services``
exposes the app's service layer (``.task_service``, ``.item_service``). Adding a new
section type is a matter of writing a renderer and registering it in
``SECTION_RENDERERS`` — plus a Slack block renderer later, which consumes the same
rendered content.
"""

from datetime import datetime, timedelta, timezone
from typing import Any, Callable, Dict, List, Optional

from dimensions import aggregate_by_category


def resolve_use_by_end(query: Dict[str, Any], tz: Any = None) -> Optional[str]:
    """Resolve a query's expiry filter to a date-only ``use_by_date_end`` bound.

    Reports run on a recurring schedule, so the expiry filter is stored
    *relative* (``expires_within_days``) and recomputed each run: N days from
    today yields "expiring within N days". A ``custom`` picker instead stores an
    absolute ``use_by_date_end`` (passed through unchanged). Returns ``None`` when
    neither is set.

    ``today`` is taken in ``tz`` when one is supplied (the render path has the
    user's tz); the trigger path has none and falls back to UTC.
    """
    within = query.get("expires_within_days")
    if within is not None and not isinstance(within, bool):
        today = datetime.now(tz).date() if tz else datetime.now(timezone.utc).date()
        return (today + timedelta(days=int(within))).isoformat()
    end = query.get("use_by_date_end")
    return end or None


def _tags(config: Dict[str, Any]) -> List[str]:
    """Read a section's tag filter as a list.

    Prefers the ``tags`` array; falls back to a legacy scalar ``tag`` so configs
    stored before the multiselect change keep working.
    """
    tags = config.get("tags")
    if tags:
        return list(tags)
    single = config.get("tag")
    return [single] if single else []


def render_custom_message(user_id: str, config: Dict[str, Any], services: Any, tz: Any) -> Dict[str, Any]:
    """Render a static author-provided message section."""
    return {"text": config.get("text", "")}


def render_task_query(user_id: str, config: Dict[str, Any], services: Any, tz: Any) -> Dict[str, Any]:
    """Render tasks matching a query (status / tags / partial name).

    ``name`` is a partial, fuzzy match on the task name (same matcher as inventory
    search); ``tags`` is an AND filter.
    """
    tasks = services.task_service.list_tasks(
        user_id,
        tz=tz,
        status=config.get("status"),
        tags=_tags(config),
        name=config.get("name") or None,
    )
    return {"items": tasks, "count": len(tasks)}


def render_item_query(user_id: str, config: Dict[str, Any], services: Any, tz: Any) -> Dict[str, Any]:
    """Render inventory items matching a query (location / tags / partial name).

    Routes through the standard inventory search engine (``search_items``, the same
    one behind ``POST /search``), so ``name`` gets fuzzy matching and ``tags`` an
    AND filter for free.
    """
    items = services.item_service.search_items(
        user_id,
        name=config.get("name") or None,
        location_id=config.get("location_id") or None,
        tags=_tags(config) or None,
        use_by_date_end=resolve_use_by_end(config, tz),
    )
    # Roll the matched items up per category (aggregate value across all categories
    # present in the query). Skipped when no category service is wired.
    category_service = getattr(services, "category_service", None)
    category_totals: List[Dict[str, Any]] = []
    if category_service is not None:
        category_totals = aggregate_by_category(items, category_service.list_categories(user_id))
    return {"items": items, "count": len(items), "category_totals": category_totals}


# Registry of section type -> renderer. The keys are the valid ``type`` values a
# report section may declare.
SECTION_RENDERERS: Dict[str, Callable[..., Dict[str, Any]]] = {
    "custom_message": render_custom_message,
    "task_query": render_task_query,
    "item_query": render_item_query,
}

SECTION_TYPES = frozenset(SECTION_RENDERERS)


def render_section(
    section: Dict[str, Any], user_id: str, services: Any, tz: Any = None
) -> Dict[str, Any]:
    """Render one section rule into a snapshot ``{ type, heading, content }``."""
    section_type = section.get("type")
    renderer = SECTION_RENDERERS.get(section_type)
    if renderer is None:
        raise ValueError(f"Unknown section type: {section_type!r}")
    content = renderer(user_id, section.get("config") or {}, services, tz)
    return {
        "type": section_type,
        "heading": section.get("heading", ""),
        "content": content,
    }


def validate_sections(sections: Any) -> None:
    """Validate a report's section rules, raising ValueError on any problem."""
    if not isinstance(sections, list):
        raise ValueError("sections must be a list")
    for i, section in enumerate(sections):
        if not isinstance(section, dict):
            raise ValueError(f"section[{i}] must be an object")
        section_type = section.get("type")
        if section_type not in SECTION_TYPES:
            raise ValueError(
                f"section[{i}] has invalid type {section_type!r} "
                f"(must be one of {sorted(SECTION_TYPES)})"
            )
        config = section.get("config")
        if config is not None and not isinstance(config, dict):
            raise ValueError(f"section[{i}] config must be an object")
        config = config or {}
        if section_type == "custom_message":
            text = config.get("text")
            if not text or not isinstance(text, str):
                raise ValueError(
                    f"section[{i}] (custom_message) requires a non-empty 'text'"
                )
        else:
            # Query sections: optional name (str), tags (list of str), location_id (str).
            name = config.get("name")
            if name is not None and not isinstance(name, str):
                raise ValueError(f"section[{i}] 'name' must be a string")
            tags = config.get("tags")
            if tags is not None and (
                not isinstance(tags, list) or not all(isinstance(t, str) for t in tags)
            ):
                raise ValueError(f"section[{i}] 'tags' must be a list of strings")
            location_id = config.get("location_id")
            if location_id is not None and not isinstance(location_id, str):
                raise ValueError(f"section[{i}] 'location_id' must be a string")
            _validate_expiry(config, f"section[{i}]")


def _validate_expiry(query: Dict[str, Any], where: str) -> None:
    """Validate a query's optional expiry filter fields, raising ValueError.

    ``expires_within_days`` (relative) must be a positive number; ``use_by_date_end``
    (absolute) must be an ISO-8601 date string. Shared by section and trigger
    query validation.
    """
    within = query.get("expires_within_days")
    if within is not None:
        if isinstance(within, bool) or not isinstance(within, (int, float)) or within <= 0:
            raise ValueError(f"{where} 'expires_within_days' must be a positive number")
    end = query.get("use_by_date_end")
    if end is not None:
        if not isinstance(end, str):
            raise ValueError(f"{where} 'use_by_date_end' must be a string")
        try:
            datetime.fromisoformat(end)
        except ValueError:
            raise ValueError(f"{where} 'use_by_date_end' must be an ISO-8601 date")
