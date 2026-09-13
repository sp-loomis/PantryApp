"""Unit tests for the pure recurrence/status logic (``recurrence.py``).

These exercise window computation, the "done for now" comparison, graceful
one-shot hiding, and window rollover — all with an injected ``now`` so they are
fully deterministic and timezone-explicit.
"""

from datetime import datetime, timezone

import pytest

from recurrence import (
    compute_status,
    current_window_key,
    is_active,
    is_done_for_window,
    local_now,
    window_due_date,
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
# Due dates per window
# ---------------------------------------------------------------------------

def test_daily_due_today():
    assert window_due_date({"recurrence_type": "daily"}, _at()).isoformat() == "2026-09-05"


def test_weekly_due_end_of_iso_week_sunday():
    assert window_due_date({"recurrence_type": "weekly"}, _at()).isoformat() == "2026-09-06"


def test_interval_due_is_last_day_of_window():
    task = {"recurrence_type": "interval", "recurrence_interval": 3, "anchor_date": "2026-09-01"}
    # Window 09-04..09-06 -> due 09-06.
    assert window_due_date(task, _at()).isoformat() == "2026-09-06"


# ---------------------------------------------------------------------------
# Done-for-window + rollover
# ---------------------------------------------------------------------------

def test_daily_done_only_within_its_window():
    task = {"recurrence_type": "daily", "last_completed_window": "2026-09-05"}
    assert is_done_for_window(task, _at()) is True
    # Next day: the stored window no longer matches -> task is due again.
    tomorrow = datetime(2026, 9, 6, 12, 0, tzinfo=timezone.utc)
    assert is_done_for_window(task, _at(now=tomorrow)) is False


def test_completing_and_rollover_status_cycle():
    task = {"recurrence_type": "daily"}
    assert compute_status(task, "UTC", NOW)["computed_status"] == "due_today"

    task["last_completed_window"] = current_window_key(task, _at())
    assert compute_status(task, "UTC", NOW)["computed_status"] == "done"

    tomorrow = datetime(2026, 9, 6, 12, 0, tzinfo=timezone.utc)
    status = compute_status(task, "UTC", tomorrow)
    assert status["computed_status"] == "due_today"
    assert status["done"] is False


# ---------------------------------------------------------------------------
# One-shot tasks + graceful hiding
# ---------------------------------------------------------------------------

def test_one_shot_future_due_is_upcoming_or_soon():
    task = {"recurrence_type": "none", "due_date": "2026-09-20"}
    status = compute_status(task, "UTC", NOW)
    assert status["computed_status"] == "upcoming"
    assert status["due_in_days"] == 15
    assert status["active"] is True


def test_one_shot_due_soon_within_a_week():
    task = {"recurrence_type": "none", "due_date": "2026-09-09"}
    assert compute_status(task, "UTC", NOW)["computed_status"] == "due_soon"


def test_graceful_past_due_one_shot_self_hides():
    task = {"recurrence_type": "none", "due_date": "2026-09-01", "graceful": True}
    status = compute_status(task, "UTC", NOW)
    assert status["computed_status"] == "overdue"
    assert status["active"] is False  # graceful -> disappears from the active list


def test_non_graceful_past_due_one_shot_keeps_nagging():
    task = {"recurrence_type": "none", "due_date": "2026-09-01", "graceful": False}
    status = compute_status(task, "UTC", NOW)
    assert status["computed_status"] == "overdue"
    assert status["active"] is True


def test_completed_one_shot_is_done_and_inactive():
    task = {"recurrence_type": "none", "due_date": "2026-09-09", "last_completed_at": "2026-09-05T12:00:00+00:00"}
    status = compute_status(task, "UTC", NOW)
    assert status["done"] is True
    assert status["active"] is False


def test_undated_one_shot_is_active_until_done():
    task = {"recurrence_type": "none"}
    status = compute_status(task, "UTC", NOW)
    assert status["active"] is True
    assert status["current_due"] is None
    assert status["computed_status"] == "upcoming"


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
    assert status["current_due"] == "2026-09-14"  # 09-10 + (5-1) days
    assert status["active"] is True
