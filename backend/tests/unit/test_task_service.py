"""Service-layer tests for ``TaskService``.

These use the ``task_service`` fixture (real mocked DynamoDB) and inject ``now``
into complete/status so window rollover can be exercised deterministically —
something the E2E path (which always uses the real clock) cannot do.
"""

from datetime import datetime, timezone

import pytest

from recurrence import compute_status

DAY1 = datetime(2026, 9, 5, 12, 0, tzinfo=timezone.utc)
DAY2 = datetime(2026, 9, 6, 12, 0, tzinfo=timezone.utc)

USER = "user-1"


def test_daily_task_completes_then_reappears_next_day(task_service):
    task = task_service.create_task(USER, "Water plants", recurrence_type="daily", tz="UTC")
    tid = task["task_id"]

    # Complete for day 1 -> done for that window.
    completed = task_service.complete_task(USER, tid, tz="UTC", now=DAY1)
    assert completed["done"] is True

    # Day 2: the stored window no longer matches -> the chore is due again.
    stored = task_service.get_task(USER, tid, tz="UTC")
    status = compute_status(stored, "UTC", DAY2)
    assert status["done"] is False
    assert status["computed_status"] == "due_today"
    assert status["active"] is True


def test_uncomplete_restores_active_state(task_service):
    task = task_service.create_task(USER, "Sweep", recurrence_type="daily", tz="UTC")
    tid = task["task_id"]

    task_service.complete_task(USER, tid, tz="UTC", now=DAY1)
    restored = task_service.uncomplete_task(USER, tid, tz="UTC", now=DAY1)
    assert restored["done"] is False
    assert restored["last_completed_window"] is None
    assert restored["last_completed_at"] is None


def test_one_shot_due_date_roundtrips_and_clears(task_service):
    task = task_service.create_task(USER, "Fix gate", due_date="2026-09-10", tz="UTC")
    tid = task["task_id"]
    assert task_service.get_task(USER, tid, tz="UTC")["due_date"] == "2026-09-10"

    cleared = task_service.update_task(USER, tid, {"due_date": None}, tz="UTC")
    assert cleared["due_date"] is None


def test_invalid_recurrence_type_raises(task_service):
    with pytest.raises(ValueError):
        task_service.create_task(USER, "bad", recurrence_type="yearly", tz="UTC")
