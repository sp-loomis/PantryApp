"""Unit tests for ReportGenerator (rendering + next_run advance)."""

from datetime import datetime, timezone

USER = "user-1"

DAILY = {"frequency": "daily", "time_of_day": "09:00", "tz": "UTC"}


def _dt(s: str) -> datetime:
    return datetime.fromisoformat(s).replace(tzinfo=timezone.utc)


def test_generate_snapshots_sections_and_creates_message(report_generator):
    report_generator.task_service.create_task(USER, "Fix gate", tz="UTC")
    report = report_generator.report_service.create_report(
        USER, "Digest", DAILY,
        sections=[
            {"type": "custom_message", "heading": "Note", "config": {"text": "morning!"}},
            {"type": "task_query", "heading": "Chores", "config": {"status": "active"}},
        ],
        now=_dt("2026-09-12T08:00:00"),
    )

    message = report_generator.generate(report, tz="UTC", now=_dt("2026-09-12T09:00:00"))

    assert message["title"] == "Digest"
    assert message["report_id"] == report["report_id"]
    assert message["read_at"] is None
    assert [s["type"] for s in message["sections"]] == ["custom_message", "task_query"]
    assert message["sections"][0]["content"] == {"text": "morning!"}
    assert message["sections"][1]["content"]["count"] == 1

    # Message persisted and unread.
    assert report_generator.message_service.unread_count(USER) == 1


def test_generate_advances_next_run(report_generator):
    report = report_generator.report_service.create_report(
        USER, "Digest", DAILY,
        sections=[{"type": "custom_message", "config": {"text": "hi"}}],
        now=_dt("2026-09-12T08:00:00"),
    )
    assert report["next_run"] == "2026-09-12T09:00:00+00:00"

    report_generator.generate(report, tz="UTC", now=_dt("2026-09-12T09:00:00"))

    refreshed = report_generator.report_service.get_report(USER, report["report_id"])
    assert refreshed["next_run"] == "2026-09-13T09:00:00+00:00"
    assert refreshed["last_run_at"] is not None


def test_generate_snapshot_is_frozen(report_generator):
    """A later data change must not alter an already-generated message."""
    report_generator.task_service.create_task(USER, "First", tz="UTC")
    report = report_generator.report_service.create_report(
        USER, "Digest", DAILY,
        sections=[{"type": "task_query", "config": {"status": "active"}}],
        now=_dt("2026-09-12T08:00:00"),
    )
    message = report_generator.generate(report, tz="UTC", now=_dt("2026-09-12T09:00:00"))
    assert message["sections"][0]["content"]["count"] == 1

    # Add another task after generation; the stored message is unaffected.
    report_generator.task_service.create_task(USER, "Second", tz="UTC")
    stored = report_generator.message_service.get_message(USER, message["message_id"])
    assert stored["sections"][0]["content"]["count"] == 1
