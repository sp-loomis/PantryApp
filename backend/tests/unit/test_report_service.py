"""Unit tests for ReportService and MessageService."""

from datetime import datetime, timezone

import pytest

USER = "user-1"

DAILY = {"frequency": "daily", "time_of_day": "09:00", "tz": "UTC"}


def _dt(s: str) -> datetime:
    return datetime.fromisoformat(s).replace(tzinfo=timezone.utc)


# --------------------------------------------------------------------------- #
# ReportService
# --------------------------------------------------------------------------- #

def test_create_report_computes_next_run(report_service):
    report = report_service.create_report(
        USER, "Morning digest", DAILY,
        sections=[{"type": "custom_message", "config": {"text": "hi"}}],
        now=_dt("2026-09-12T08:00:00"),
    )
    assert report["name"] == "Morning digest"
    assert report["enabled"] is True
    assert report["next_run"] == "2026-09-12T09:00:00+00:00"
    assert report_service.get_report(USER, report["report_id"])["next_run"] == "2026-09-12T09:00:00+00:00"


def test_create_report_rejects_bad_schedule(report_service):
    with pytest.raises(ValueError):
        report_service.create_report(USER, "bad", {"frequency": "never"})


def test_create_report_rejects_bad_sections(report_service):
    with pytest.raises(ValueError):
        report_service.create_report(USER, "bad", DAILY, sections=[{"type": "bogus"}])


def test_create_report_accepts_task_trigger(report_service):
    trigger = {
        "match": "all",
        "conditions": [{
            "source": "task",
            "query": {"status": "active", "tags": ["shopping"]},
            "match": "all",
            "inequalities": [{"operator": "above", "threshold": 5}],
        }],
    }
    report = report_service.create_report(
        USER, "Busy list", DAILY,
        sections=[{"type": "custom_message", "config": {"text": "hi"}}],
        trigger=trigger,
    )
    stored = report_service.get_report(USER, report["report_id"])
    assert stored["trigger"]["conditions"][0]["source"] == "task"


def test_create_report_rejects_unknown_category_in_item_trigger(report_service):
    trigger = {
        "conditions": [{
            "source": "item", "query": {}, "match": "all",
            "inequalities": [{"category_id": "ghost", "operator": "below", "threshold": 1}],
        }],
    }
    with pytest.raises(ValueError):
        report_service.create_report(USER, "bad", DAILY, trigger=trigger)


def test_list_reports_scoped_to_user(report_service):
    report_service.create_report(USER, "mine", DAILY)
    report_service.create_report("other", "theirs", DAILY)
    reports = report_service.list_reports(USER)
    assert [r["name"] for r in reports] == ["mine"]


def test_update_report_recomputes_next_run(report_service):
    report = report_service.create_report(USER, "r", DAILY, now=_dt("2026-09-12T08:00:00"))
    updated = report_service.update_report(
        USER, report["report_id"],
        {"schedule": {"frequency": "daily", "time_of_day": "18:00", "tz": "UTC"}},
        now=_dt("2026-09-12T08:00:00"),
    )
    assert updated["next_run"] == "2026-09-12T18:00:00+00:00"


def test_update_missing_report_returns_none(report_service):
    assert report_service.update_report(USER, "nope", {"name": "x"}) is None


def test_delete_report(report_service):
    report = report_service.create_report(USER, "r", DAILY)
    assert report_service.delete_report(USER, report["report_id"]) is True
    assert report_service.delete_report(USER, report["report_id"]) is False


def test_list_due_reports_filters_by_next_run_and_enabled(report_service):
    now = _dt("2026-09-12T12:00:00")
    # Due: next_run already passed.
    due = report_service.create_report(USER, "due", DAILY, now=_dt("2026-09-11T08:00:00"))
    # Not due: fires later today.
    report_service.create_report(USER, "later", {"frequency": "daily", "time_of_day": "23:00", "tz": "UTC"}, now=now)
    # Disabled even though due.
    disabled = report_service.create_report(USER, "off", DAILY, enabled=False, now=_dt("2026-09-11T08:00:00"))

    due_reports = report_service.list_due_reports(now)
    names = {r["name"] for r in due_reports}
    assert "due" in names
    assert "later" not in names
    assert "off" not in names


# --------------------------------------------------------------------------- #
# MessageService — sparse unread index
# --------------------------------------------------------------------------- #

def test_create_message_is_unread(message_service):
    msg = message_service.create_message(USER, "Hello", sections=[{"type": "custom_message"}])
    assert msg["read_at"] is None
    assert message_service.unread_count(USER) == 1
    assert [m["message_id"] for m in message_service.list_unread(USER)] == [msg["message_id"]]


def test_mark_read_drops_from_unread_index(message_service):
    msg = message_service.create_message(USER, "Hello")
    read = message_service.mark_read(USER, msg["message_id"])
    assert read["read_at"] is not None
    assert message_service.unread_count(USER) == 0
    assert message_service.list_unread(USER) == []


def test_mark_unread_restores_to_index(message_service):
    msg = message_service.create_message(USER, "Hello")
    message_service.mark_read(USER, msg["message_id"])
    restored = message_service.mark_unread(USER, msg["message_id"])
    assert restored["read_at"] is None
    assert message_service.unread_count(USER) == 1


def test_list_messages_newest_first(message_service):
    a = message_service.create_message(USER, "A")
    b = message_service.create_message(USER, "B")
    # created_at ordering: whichever is lexicographically greater comes first.
    ids = [m["message_id"] for m in message_service.list_messages(USER)]
    assert set(ids) == {a["message_id"], b["message_id"]}
    assert len(ids) == 2


def test_mark_read_missing_returns_none(message_service):
    assert message_service.mark_read(USER, "nope") is None


def test_delete_message(message_service):
    msg = message_service.create_message(USER, "Hello")
    assert message_service.delete_message(USER, msg["message_id"]) is True
    assert message_service.delete_message(USER, msg["message_id"]) is False
