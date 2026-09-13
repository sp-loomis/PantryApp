"""Report schedule computation for the notification engine.

Reports fire at a specific local time on a simple cron-ish cadence (daily, weekly,
or monthly). This module turns a report's ``schedule`` config into the next UTC
firing instant (``next_run``), which the periodic sweep uses to decide what is due.

Pure and stdlib-only (reuses ``recurrence.resolve_tz`` for IANA handling), so it is
trivially unit-testable. ``now`` is injectable throughout for deterministic tests.

Schedule shape::

    {
        "frequency": "daily" | "weekly" | "monthly",
        "time_of_day": "HH:00",      # 24h local time, on the hour; default "09:00"
        "weekday": 0-6,              # Mon=0 .. Sun=6; weekly only
        "day_of_month": 1-28,        # monthly only (capped at 28 for safety)
        "tz": "America/New_York",    # IANA; defaults to UTC
    }
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Optional

from recurrence import resolve_tz, local_now

FREQUENCIES = frozenset({"daily", "weekly", "monthly"})

DEFAULT_TIME_OF_DAY = "09:00"


def _parse_time_of_day(value: Any) -> tuple[int, int]:
    """Parse ``"HH:MM"`` into (hour, minute), raising ValueError if malformed.

    Reports fire only on the hour (the notification sweep runs hourly), so the
    minute component must be ``00``. A non-zero minute is rejected rather than
    silently floored, keeping the stored schedule honest about when it fires.
    """
    if value is None:
        value = DEFAULT_TIME_OF_DAY
    if not isinstance(value, str):
        raise ValueError("time_of_day must be a 'HH:MM' string")
    try:
        hh, mm = value.split(":")
        hour, minute = int(hh), int(mm)
    except (ValueError, AttributeError):
        raise ValueError("time_of_day must be a 'HH:MM' string")
    if not (0 <= hour <= 23 and 0 <= minute <= 59):
        raise ValueError("time_of_day must be within 00:00..23:59")
    if minute != 0:
        raise ValueError("time_of_day must be on the hour (minutes must be 00)")
    return hour, minute


def validate_schedule(schedule: Any) -> None:
    """Validate a report schedule, raising ValueError on any problem."""
    if not isinstance(schedule, dict):
        raise ValueError("schedule must be an object")
    frequency = schedule.get("frequency")
    if frequency not in FREQUENCIES:
        raise ValueError(
            f"Invalid frequency: {frequency!r} (must be one of {sorted(FREQUENCIES)})"
        )
    _parse_time_of_day(schedule.get("time_of_day"))
    if frequency == "weekly":
        weekday = schedule.get("weekday", 0)
        if isinstance(weekday, bool) or not isinstance(weekday, int) or not (0 <= weekday <= 6):
            raise ValueError("weekday must be an integer 0 (Mon) .. 6 (Sun) for weekly reports")
    if frequency == "monthly":
        dom = schedule.get("day_of_month", 1)
        if isinstance(dom, bool) or not isinstance(dom, int) or not (1 <= dom <= 28):
            raise ValueError("day_of_month must be an integer 1 .. 28 for monthly reports")


def compute_next_run(schedule: Dict[str, Any], now: Optional[datetime] = None) -> str:
    """Return the next firing instant as a UTC ISO-8601 string.

    Computes the next local time matching ``schedule`` strictly after ``now`` (so
    a report generated at its firing time schedules the following occurrence), then
    converts to UTC.
    """
    validate_schedule(schedule)
    tz = schedule.get("tz")
    tzinfo = resolve_tz(tz)
    now_local = local_now(tz, now)
    hour, minute = _parse_time_of_day(schedule.get("time_of_day"))
    frequency = schedule["frequency"]

    candidate = now_local.replace(hour=hour, minute=minute, second=0, microsecond=0)

    if frequency == "daily":
        if candidate <= now_local:
            candidate += timedelta(days=1)

    elif frequency == "weekly":
        target = schedule.get("weekday", 0)
        days_ahead = (target - candidate.weekday()) % 7
        candidate += timedelta(days=days_ahead)
        if candidate <= now_local:
            candidate += timedelta(days=7)

    elif frequency == "monthly":
        dom = schedule.get("day_of_month", 1)
        candidate = candidate.replace(day=dom)
        if candidate <= now_local:
            candidate = _add_month(candidate).replace(day=dom)

    return candidate.astimezone(timezone.utc).isoformat()


def _add_month(dt: datetime) -> datetime:
    """Return ``dt`` advanced by one calendar month (day set separately by caller)."""
    if dt.month == 12:
        return dt.replace(year=dt.year + 1, month=1)
    return dt.replace(month=dt.month + 1)
