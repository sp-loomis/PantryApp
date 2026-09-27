"""Unit tests for the pure recurrence/status logic (``recurrence.py``).

These exercise window computation, the "done for now" comparison, the flat
present/done/dormant status model, and window rollover — all with an injected
``now`` so they are fully deterministic and timezone-explicit.
"""

from datetime import datetime, timezone

import pytest

from recurrence import (
    compute_status,
    current_window_key,
    is_active,
    is_done_for_window,
    local_now,
    window_end_date,
)

# A fixed reference instant: Saturday 2026-09-05, 12:00 UTC.
# 2026-09-05 falls in ISO week 36 (Mon 2026-08-31 .. Sun 2026-09-06).
NOW = datetime(2026, 9, 5, 12, 0, tzinfo=timezone.utc)


def _at(*, tz="UTC", now=NOW):
    return local_now(tz, now)


# ---------------------------------------------------------------------------
# Window keys
# ---------------------------------------------------------------------------

def test_daily_window_key_is_local_date():
    task = {"recurrence_type": "daily"}
    assert current_window_key(task, _at()) == "2026-09-05"


def test_weekly_window_key_is_iso_year_week():
    task = {"recurrence_type": "weekly"}
    assert current_window_key(task, _at()) == "2026-W36"


def test_interval_window_key_snaps_to_window_start():
    # Anchored 2026-09-01, every 3 days -> windows start 09-01, 09-04, 09-07.
    # On 09-05 the current window started 09-04.
    task = {"recurrence_type": "interval", "recurrence_interval": 3, "anchor_date": "2026-09-01"}
    assert current_window_key(task, _at()) == "2026-09-04"


def test_one_shot_has_no_window_key():
    assert current_window_key({"recurrence_type": "none"}, _at()) == ""


# ---------------------------------------------------------------------------
# Window-end dates (reference/tests only; status no longer uses them)
# ---------------------------------------------------------------------------

def test_daily_window_ends_today():
    assert window_end_date({"recurrence_type": "daily"}, _at()).isoformat() == "2026-09-05"


def test_weekly_window_ends_end_of_iso_week_sunday():
    assert window_end_date({"recurrence_type": "weekly"}, _at()).isoformat() == "2026-09-06"


def test_interval_window_ends_last_day_of_window():
    task = {"recurrence_type": "interval", "recurrence_interval": 3, "anchor_date": "2026-09-01"}
    # Window 09-04..09-06 -> ends 09-06.
    assert window_end_date(task, _at()).isoformat() == "2026-09-06"


def test_one_shot_has_no_window_end():
    assert window_end_date({"recurrence_type": "none"}, _at()) is None


# ---------------------------------------------------------------------------
# Done-for-window + rollover
# ---------------------------------------------------------------------------

def test_daily_done_only_within_its_window():
    task = {"recurrence_type": "daily", "last_completed_window": "2026-09-05"}
    assert is_done_for_window(task, _at()) is True
    # Next day: the stored window no longer matches -> task is present again.
    tomorrow = datetime(2026, 9, 6, 12, 0, tzinfo=timezone.utc)
    assert is_done_for_window(task, _at(now=tomorrow)) is False


def test_completing_and_rollover_status_cycle():
    task = {"recurrence_type": "daily"}
    assert compute_status(task, "UTC", NOW)["computed_status"] == "present"

    task["last_completed_window"] = current_window_key(task, _at())
    assert compute_status(task, "UTC", NOW)["computed_status"] == "done"

    # A new day supersedes the old completion: the reminder is present again.
    tomorrow = datetime(2026, 9, 6, 12, 0, tzinfo=timezone.utc)
    status = compute_status(task, "UTC", tomorrow)
    assert status["computed_status"] == "present"
    assert status["done"] is False


# ---------------------------------------------------------------------------
# Dateless to-dos (recurrence_type "none")
# ---------------------------------------------------------------------------

def test_undone_to_do_is_present_and_active():
    task = {"recurrence_type": "none"}
    status = compute_status(task, "UTC", NOW)
    assert status["computed_status"] == "present"
    assert status["active"] is True


def test_completed_to_do_is_done_and_inactive():
    task = {"recurrence_type": "none", "last_completed_at": "2026-09-05T12:00:00+00:00"}
    status = compute_status(task, "UTC", NOW)
    assert status["done"] is True
    assert status["computed_status"] == "done"
    assert status["active"] is False


def test_active_reminder_stays_present_regardless_of_window_position():
    # A weekly reminder late in its window is still just "present" — no urgency.
    task = {"recurrence_type": "weekly"}
    assert compute_status(task, "UTC", NOW)["computed_status"] == "present"
    assert is_active(task, _at()) is True


# ---------------------------------------------------------------------------
# Timezone-sensitive rollover
# ---------------------------------------------------------------------------

def test_daily_window_respects_client_timezone():
    # 2026-09-05 23:30 UTC is still 09-05 in UTC but already 09-06 in Sydney.
    late = datetime(2026, 9, 5, 23, 30, tzinfo=timezone.utc)
    task = {"recurrence_type": "daily"}
    assert current_window_key(task, local_now("UTC", late)) == "2026-09-05"
    assert current_window_key(task, local_now("Australia/Sydney", late)) == "2026-09-06"


def test_unknown_timezone_falls_back_to_utc():
    task = {"recurrence_type": "daily"}
    assert current_window_key(task, local_now("Not/AZone", NOW)) == "2026-09-05"


def test_interval_future_anchor_reports_first_window():
    # Anchor in the future: the current window clamps to the first one.
    task = {"recurrence_type": "interval", "recurrence_interval": 5, "anchor_date": "2026-09-10"}
    status = compute_status(task, "UTC", NOW)
    assert status["computed_status"] == "present"
    assert status["active"] is True


# ---------------------------------------------------------------------------
# Decision paths: trigger resolution (resolve_tasks)
# ---------------------------------------------------------------------------

from recurrence import resolve_tasks, deadline_date, trigger_matches, completion_window_key  # noqa: E402
from datetime import date  # noqa: E402


def _daily_decision(task_id, decision):
    """A daily yes/no decision source, answered `decision` for NOW's window."""
    return {
        "task_id": task_id,
        "name": task_id,
        "recurrence_type": "daily",
        "answer_mode": "yesno",
        "last_decision": decision,
        "last_completed_window": "2026-09-05",  # NOW's daily window
    }


def _dependent(task_id, source_id, on="yes", deadline="same_day", offset_days=None, **extra):
    trigger = {"source_task_id": source_id, "on": on, "deadline": deadline}
    if offset_days is not None:
        trigger["offset_days"] = offset_days
    return {"task_id": task_id, "name": task_id, "recurrence_type": "none",
            "trigger": trigger, **extra}


def _by_id(resolved):
    return {t["task_id"]: t for t in resolved}


def test_trigger_matches_semantics():
    assert trigger_matches("yes", "yes") is True
    assert trigger_matches("yes", "no") is False
    assert trigger_matches("any", "no") is True
    assert trigger_matches("any", None) is False  # unanswered never satisfies


def test_deadline_date_variants():
    anchor = date(2026, 9, 5)  # Saturday, ISO week 36
    assert deadline_date(anchor, "same_day", None) == anchor
    assert deadline_date(anchor, "same_week", None) == date(2026, 9, 6)  # Sunday
    assert deadline_date(anchor, "offset", 3) == date(2026, 9, 8)


def test_dependent_present_when_source_answered_yes():
    src = _daily_decision("a", "yes")
    dep = _dependent("b", "a", on="yes")
    r = _by_id(resolve_tasks([src, dep], "UTC", NOW))
    assert r["b"]["computed_status"] == "present"
    assert r["b"]["active"] is True


def test_dependent_dormant_when_source_unanswered():
    src = {"task_id": "a", "recurrence_type": "daily", "answer_mode": "yesno"}
    dep = _dependent("b", "a", on="yes")
    r = _by_id(resolve_tasks([src, dep], "UTC", NOW))
    assert r["b"]["computed_status"] == "dormant"
    assert r["b"]["active"] is False


def test_yes_and_no_branch_are_mutually_exclusive():
    src = _daily_decision("a", "no")
    yes_dep = _dependent("y", "a", on="yes")
    no_dep = _dependent("n", "a", on="no")
    r = _by_id(resolve_tasks([src, yes_dep, no_dep], "UTC", NOW))
    assert r["y"]["active"] is False and r["y"]["computed_status"] == "dormant"
    assert r["n"]["active"] is True and r["n"]["computed_status"] == "present"


def test_dependent_done_keyed_to_source_window():
    src = _daily_decision("a", "yes")
    # Completed against the source's current window -> done.
    dep = _dependent("b", "a", on="yes", last_completed_window="2026-09-05")
    r = _by_id(resolve_tasks([src, dep], "UTC", NOW))
    assert r["b"]["done"] is True
    assert r["b"]["active"] is False


def test_dependent_rearms_when_source_window_rolls():
    # Source answered yes yesterday (old window), completed dependent then too.
    src = {"task_id": "a", "recurrence_type": "daily", "answer_mode": "yesno",
           "last_decision": "yes", "last_completed_window": "2026-09-04"}
    dep = _dependent("b", "a", on="yes", last_completed_window="2026-09-04")
    r = _by_id(resolve_tasks([src, dep], "UTC", NOW))
    # NOW is 09-05: source no longer answered for today -> dependent dormant again.
    assert r["a"]["done"] is False
    assert r["b"]["computed_status"] == "dormant"
    assert r["b"]["active"] is False


def test_chained_dependents_resolve_transitively():
    a = _daily_decision("a", "yes")
    # b is itself a decision, triggered by a; answered yes for the borrowed window.
    b = _dependent("b", "a", on="yes", answer_mode="yesno", last_decision="yes",
                   last_completed_window="2026-09-05")
    c = _dependent("c", "b", on="yes")
    r = _by_id(resolve_tasks([a, b, c], "UTC", NOW))
    assert r["b"]["done"] is True          # b answered yes for the window
    assert r["c"]["active"] is True        # c fires off b's yes


def test_cycle_degrades_to_untriggered_without_crashing():
    a = _dependent("a", "b", on="any")
    b = _dependent("b", "a", on="any")
    # Should not raise; both simply resolve (untriggered fallback for the cycle).
    resolved = resolve_tasks([a, b], "UTC", NOW)
    assert {t["task_id"] for t in resolved} == {"a", "b"}


def test_dangling_source_is_dormant():
    dep = _dependent("b", "missing", on="yes")
    r = _by_id(resolve_tasks([dep], "UTC", NOW))
    assert r["b"]["computed_status"] == "dormant"
    assert r["b"]["active"] is False


def test_completion_window_key_borrows_source_window():
    src = _daily_decision("a", "yes")
    dep = _dependent("b", "a", on="yes")
    # b borrows a's daily window as its completion key.
    assert completion_window_key([src, dep], "b", "UTC", NOW) == "2026-09-05"
    # a uses its own window.
    assert completion_window_key([src, dep], "a", "UTC", NOW) == "2026-09-05"
