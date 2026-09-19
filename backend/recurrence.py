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

# Task-trigger vocabulary (decision paths). A task with a ``trigger`` is dormant
# until its source task is answered a matching way; see ``resolve_tasks``.
TRIGGER_ON = frozenset({"yes", "no", "any"})  # which decision activates the task
TRIGGER_DEADLINES = frozenset({"same_day", "same_week", "offset"})

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


# ---------------------------------------------------------------------------
# Decision paths: trigger resolution
#
# A task may carry a ``trigger`` making it depend on another task's decision. It
# stays *dormant* until its source is answered a matching way (Yes / No / any),
# then becomes active with a due date computed relative to the source's window.
#
# A dependent borrows its source's recurrence window for BOTH activation and
# completion-reset: answer a daily decision Yes today and its dependents surface
# for today; when the day rolls over the source needs answering again and the
# dependents go dormant — the same "graceful disappearance" as recurring chores,
# with no materialized rows and no history. Chains (a dependent of a dependent)
# resolve transitively; a cycle degrades to treating the task as untriggered.
# ---------------------------------------------------------------------------


def trigger_matches(on: str, decision: Optional[str]) -> bool:
    """Whether a source ``decision`` satisfies a trigger's ``on`` condition."""
    if decision is None:
        return False
    if on == "any":
        return True
    return on == decision


def deadline_date(anchor: date, deadline: str, offset_days: Optional[int]) -> date:
    """Resolve a dependent's due date from its source window's anchor date.

    ``same_day`` → the anchor; ``same_week`` → the end (Sunday) of the anchor's
    ISO week; ``offset`` → anchor + ``offset_days``.
    """
    if deadline == "same_week":
        _, _, weekday = anchor.isocalendar()  # 1=Mon .. 7=Sun
        return anchor + timedelta(days=7 - weekday)
    if deadline == "offset":
        return anchor + timedelta(days=int(offset_days or 0))
    return anchor  # same_day (default)


def _window_keys(tasks_by_id: Dict[str, Task], now_local: datetime) -> Dict[str, str]:
    """Map each task_id to the window key its completion resets against.

    A triggered task borrows its source's (effective) window; everything else
    uses its own ``current_window_key``. Cycles fall back to the task's own key.
    """
    memo: Dict[str, str] = {}

    def resolve(task: Task, stack: frozenset) -> str:
        tid = task.get("task_id")
        if tid in memo:
            return memo[tid]
        trigger = task.get("trigger")
        if trigger and tid not in stack:
            source = tasks_by_id.get(trigger.get("source_task_id"))
            if source is not None:
                memo[tid] = resolve(source, stack | {tid})
                return memo[tid]
        memo[tid] = current_window_key(task, now_local)
        return memo[tid]

    return {tid: resolve(task, frozenset()) for tid, task in tasks_by_id.items()}


def completion_window_key(
    tasks: list, task_id: str, tz: Optional[str] = None, now: Optional[datetime] = None
) -> str:
    """The window key to record when completing ``task_id`` among ``tasks``.

    Equals the task's own current window for a plain/recurring task, or its
    source's borrowed window for a triggered dependent (so it re-arms in lockstep
    with the decision it hangs off). Used by ``TaskService.complete_task``.
    """
    now_local = local_now(tz, now)
    by_id = {t.get("task_id"): t for t in tasks if t.get("task_id")}
    return _window_keys(by_id, now_local).get(task_id, "")


def _status_triggered(
    task: Task,
    trigger: Dict[str, Any],
    source: Optional[Task],
    source_status: Optional[Dict[str, Any]],
    borrowed_window: str,
    now_local: datetime,
) -> Dict[str, Any]:
    """Compute status for a task gated by a trigger (see module notes)."""
    today = now_local.date()

    # The source's decision for its current window, or None if unanswered / gone.
    decision: Optional[str] = None
    if source is not None and source_status is not None and source_status.get("done"):
        decision = source.get("last_decision") or "yes"  # answered checkbox == yes
    satisfied = trigger_matches(trigger.get("on", "any"), decision)

    # Done-state is keyed to the borrowed window so it resets with the source.
    if borrowed_window:
        done = task.get("last_completed_window") == borrowed_window
    else:
        done = bool(task.get("last_completed_at"))

    due: Optional[date] = None
    if satisfied:
        anchor = _parse_date((source_status or {}).get("current_due")) or today
        due = deadline_date(anchor, trigger.get("deadline", "same_day"), trigger.get("offset_days"))
    due_in_days = (due - today).days if due is not None else None

    if done:
        status = "done"
    elif not satisfied:
        status = "dormant"  # source not (yet) answered a matching way
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

    active = (
        satisfied
        and not done
        and (due is None or due_in_days >= 0 or not task.get("graceful", True))
    )

    return {
        "done": done,
        "computed_status": status,
        "current_due": due.isoformat() if due is not None else None,
        "due_in_days": due_in_days,
        "active": active,
    }


def resolve_tasks(
    tasks: list, tz: Optional[str] = None, now: Optional[datetime] = None
) -> list:
    """Return the tasks with computed status, resolving trigger dependencies.

    Untriggered tasks get the same status as :func:`compute_status`. Triggered
    tasks are dormant until their source is answered a matching way, then active
    with a due date relative to the source's window. Chains resolve transitively;
    a cycle degrades the offending task to untriggered. Pure and deterministic
    for a fixed ``now``.
    """
    now_local = local_now(tz, now)
    by_id = {t.get("task_id"): t for t in tasks if t.get("task_id")}
    windows = _window_keys(by_id, now_local)
    memo: Dict[str, Dict[str, Any]] = {}

    def resolve(task: Task, stack: frozenset) -> Dict[str, Any]:
        tid = task.get("task_id")
        if tid in memo:
            return memo[tid]
        trigger = task.get("trigger")
        if not trigger or tid in stack:
            memo[tid] = compute_status(task, tz, now)
            return memo[tid]
        source = by_id.get(trigger.get("source_task_id"))
        source_status = resolve(source, stack | {tid}) if source is not None else None
        memo[tid] = _status_triggered(
            task, trigger, source, source_status, windows.get(tid, ""), now_local
        )
        return memo[tid]

    return [{**task, **resolve(task, frozenset())} for task in tasks]
