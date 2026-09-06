"""
Recurrence & task-status computation for the Homestead Manager task tracker.

Pure and dependency-free (stdlib only), so it is trivially unit-testable and safe
to import anywhere. A recurring task is stored as a single row plus a rule; its
status is computed on read from ``now`` in the caller's timezone, never
materialized as per-occurrence rows.

Because we only ever evaluate the *current* window, missed past windows simply
never appear — that is the "graceful disappearance" of daily/weekly chores. A
task is "done for now" iff it was completed within the current window; when the
window rolls over, that no longer holds and the task reappears fresh.

``now`` is injectable throughout for deterministic tests.
"""

from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from typing import Any, Dict, Optional
from zoneinfo import ZoneInfo

# Recurrence rules supported in v1. "none" is a one-shot task with an optional
# due_date; the others repeat and derive their status from the current window.
RECURRENCE_TYPES = frozenset({"none", "daily", "weekly", "interval"})

# Calendar-days-out threshold separating "due soon" (orange) from "upcoming".
DUE_SOON_DAYS = 7

Task = Dict[str, Any]


def resolve_tz(tz: Optional[str]):
    """Resolve an IANA tz name (e.g. ``America/New_York``) to a tzinfo.

    Falls back to UTC on a missing or unrecognized name so a bad client value
    can never break status computation.
    """
    if not tz:
        return timezone.utc
    try:
        return ZoneInfo(tz)
    except Exception:  # unknown zone, missing tz database, etc.
        return timezone.utc


def local_now(tz: Optional[str], now: Optional[datetime] = None) -> datetime:
    """Return the current instant as an aware datetime in ``tz``.

    ``now`` may be passed for tests (aware, or naive and assumed UTC); it
    defaults to the real current time.
    """
    tzinfo = resolve_tz(tz)
    if now is None:
        return datetime.now(tzinfo)
    if now.tzinfo is None:
        now = now.replace(tzinfo=timezone.utc)
    return now.astimezone(tzinfo)


def _parse_date(value: Optional[str]) -> Optional[date]:
    """Parse an ISO date/datetime string to a ``date`` (date portion), or None."""
    if not value:
        return None
    try:
        return datetime.fromisoformat(value).date()
    except ValueError:
        try:
            return date.fromisoformat(value[:10])
        except ValueError:
            return None


def _interval_window(task: Task, today: date):
    """Return ``(window_start, interval)`` for the current interval window.

    The anchor defaults to today when unset. A future anchor clamps to window 0
    so a not-yet-started task reports its first window rather than a nonsensical
    negative index.
    """
    anchor = _parse_date(task.get("anchor_date")) or today
    interval = task.get("recurrence_interval") or 1
    interval = max(int(interval), 1)
    if today < anchor:
        index = 0
    else:
        index = (today - anchor).days // interval
    return anchor + timedelta(days=index * interval), interval


def current_window_key(task: Task, now_local: datetime) -> str:
    """Stable string identifying the task's current recurrence window.

    Completion is recorded against this key; comparing a stored key to the
    freshly computed one is how we know whether a task is done "for now".
    One-shot tasks have no window and return ``""``.
    """
    rtype = task.get("recurrence_type", "none")
    today = now_local.date()
    if rtype == "daily":
        return today.isoformat()
    if rtype == "weekly":
        iso_year, iso_week, _ = today.isocalendar()
        return f"{iso_year}-W{iso_week:02d}"
    if rtype == "interval":
        start, _ = _interval_window(task, today)
        return start.isoformat()
    return ""


def window_due_date(task: Task, now_local: datetime) -> Optional[date]:
    """The date by which the current window's occurrence is due, or None.

    Daily → today; weekly → the end (Sunday) of the current ISO week; interval →
    the last day of the current window; one-shot → its ``due_date`` (or None).
    """
    rtype = task.get("recurrence_type", "none")
    today = now_local.date()
    if rtype == "daily":
        return today
    if rtype == "weekly":
        _, _, weekday = today.isocalendar()  # 1=Mon .. 7=Sun
        return today + timedelta(days=7 - weekday)
    if rtype == "interval":
        start, interval = _interval_window(task, today)
        return start + timedelta(days=interval - 1)
    return _parse_date(task.get("due_date"))


def is_done_for_window(task: Task, now_local: datetime) -> bool:
    """Whether the task is complete for its current window / one-shot lifetime."""
    if task.get("recurrence_type", "none") == "none":
        return bool(task.get("last_completed_at"))
    return task.get("last_completed_window") == current_window_key(task, now_local)


def is_active(task: Task, now_local: datetime) -> bool:
    """Whether the task belongs in the active list right now.

    Done tasks drop out (recurring ones return next window). A past-due one-shot
    stays only when it is *not* graceful; a graceful one self-hides.
    """
    if is_done_for_window(task, now_local):
        return False
    if task.get("recurrence_type", "none") != "none":
        return True
    due = _parse_date(task.get("due_date"))
    if due is None or due >= now_local.date():
        return True
    return not task.get("graceful", True)


def compute_status(task: Task, tz: Optional[str] = None, now: Optional[datetime] = None) -> Dict[str, Any]:
    """Compute the derived status fields merged onto a task in API responses.

    Returns ``done``, ``computed_status`` (one of ``overdue``/``due_today``/
    ``due_soon``/``upcoming``/``done``), ``current_due`` (ISO date or None),
    ``due_in_days`` (calendar days from today; negative if overdue) and
    ``active``.
    """
    now_local = local_now(tz, now)
    today = now_local.date()

    done = is_done_for_window(task, now_local)
    due = window_due_date(task, now_local)
    due_in_days = (due - today).days if due is not None else None

    if done:
        status = "done"
    elif due is None:
        status = "upcoming"
    elif due_in_days < 0:
        status = "overdue"
    elif due_in_days == 0:
        status = "due_today"
    elif due_in_days <= DUE_SOON_DAYS:
        status = "due_soon"
    else:
        status = "upcoming"

    return {
        "done": done,
        "computed_status": status,
        "current_due": due.isoformat() if due is not None else None,
        "due_in_days": due_in_days,
        "active": is_active(task, now_local),
    }
