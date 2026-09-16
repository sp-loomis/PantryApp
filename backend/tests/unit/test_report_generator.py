"""Unit tests for ReportGenerator (rendering + next_run advance + Slack delivery)."""

from datetime import datetime, timezone

from services import ReportGenerator

USER = "user-1"

DAILY = {"frequency": "daily", "time_of_day": "09:00", "tz": "UTC"}

SLACK_DELIVERY = {"slack": {"connection_id": "conn-1", "channel_id": "C123"}}


def _dt(s: str) -> datetime:
    return datetime.fromisoformat(s).replace(tzinfo=timezone.utc)


class _FakeSlack:
    """Records post_message calls; optionally raises to test best-effort."""

    def __init__(self, raises=False):
        self.calls = []
        self.raises = raises

    def post_message(self, user_id, connection_id, channel_id, blocks=None, text=None):
        self.calls.append({
            "user_id": user_id, "connection_id": connection_id,
            "channel_id": channel_id, "blocks": blocks, "text": text,
        })
        if self.raises:
            raise RuntimeError("boom")
        return {"ok": True}


def _generator_with_slack(report_generator, slack):
    """Rebuild the generator with a Slack sink, reusing its wired services."""
    return ReportGenerator(
        report_generator.report_service,
        report_generator.message_service,
        report_generator.task_service,
        report_generator.item_service,
        slack_service=slack,
    )


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


def test_generate_delivers_to_slack_when_target_set(report_generator):
    slack = _FakeSlack()
    gen = _generator_with_slack(report_generator, slack)
    report = gen.report_service.create_report(
        USER, "Digest", DAILY,
        sections=[{"type": "custom_message", "heading": "Note", "config": {"text": "hi"}}],
        delivery=SLACK_DELIVERY,
        now=_dt("2026-09-12T08:00:00"),
    )

    gen.generate(report, tz="UTC", now=_dt("2026-09-12T09:00:00"))

    assert len(slack.calls) == 1
    call = slack.calls[0]
    assert call["connection_id"] == "conn-1"
    assert call["channel_id"] == "C123"
    assert call["text"] == "Digest"
    # Block Kit payload: a header block plus rendered section blocks.
    assert call["blocks"][0]["type"] == "header"
    assert any("hi" in str(b) for b in call["blocks"])


def test_generate_no_slack_call_without_target(report_generator):
    slack = _FakeSlack()
    gen = _generator_with_slack(report_generator, slack)
    report = gen.report_service.create_report(
        USER, "Digest", DAILY,
        sections=[{"type": "custom_message", "config": {"text": "hi"}}],
        now=_dt("2026-09-12T08:00:00"),
    )

    gen.generate(report, tz="UTC", now=_dt("2026-09-12T09:00:00"))

    assert slack.calls == []


def test_generate_slack_failure_is_best_effort(report_generator):
    """A Slack failure must not break generation; the message still persists."""
    slack = _FakeSlack(raises=True)
    gen = _generator_with_slack(report_generator, slack)
    report = gen.report_service.create_report(
        USER, "Digest", DAILY,
        sections=[{"type": "custom_message", "config": {"text": "hi"}}],
        delivery=SLACK_DELIVERY,
        now=_dt("2026-09-12T08:00:00"),
    )

    message = gen.generate(report, tz="UTC", now=_dt("2026-09-12T09:00:00"))

    assert len(slack.calls) == 1  # attempted
    # Message was still created despite the Slack error.
    assert gen.message_service.get_message(USER, message["message_id"]) is not None
