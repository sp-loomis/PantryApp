"""End-to-end tests for the report endpoints and the scheduled sweep."""

UTC = {"tz": "UTC"}

DAILY = {"frequency": "daily", "time_of_day": "09:00", "tz": "UTC"}


def _report_body(name="Digest", sections=None):
    return {
        "name": name,
        "schedule": DAILY,
        "sections": sections if sections is not None else [
            {"type": "custom_message", "heading": "Note", "config": {"text": "morning!"}},
        ],
    }


def test_create_report_happy(api):
    resp = api.call("POST", "/reports", body=_report_body())
    assert resp.status_code == 201
    report = resp.body["report"]
    assert report["name"] == "Digest"
    assert report["enabled"] is True
    assert report["next_run"] is not None


def test_create_report_requires_name(api):
    resp = api.call("POST", "/reports", body={"schedule": DAILY})
    assert resp.status_code == 400


def test_create_report_requires_schedule(api):
    resp = api.call("POST", "/reports", body={"name": "x"})
    assert resp.status_code == 400


def test_create_report_rejects_bad_section(api):
    resp = api.call("POST", "/reports", body=_report_body(sections=[{"type": "bogus"}]))
    assert resp.status_code == 400


def test_list_and_get_report(api):
    created = api.call("POST", "/reports", body=_report_body()).body["report"]
    listed = api.call("GET", "/reports")
    assert listed.status_code == 200
    assert any(r["report_id"] == created["report_id"] for r in listed.body["reports"])

    got = api.call("GET", f"/reports/{created['report_id']}")
    assert got.status_code == 200
    assert got.body["report"]["report_id"] == created["report_id"]


def test_get_missing_report_404(api):
    assert api.call("GET", "/reports/nope").status_code == 404


def test_update_report(api):
    created = api.call("POST", "/reports", body=_report_body()).body["report"]
    resp = api.call("PUT", f"/reports/{created['report_id']}", body={"name": "Renamed"})
    assert resp.status_code == 200
    assert resp.body["report"]["name"] == "Renamed"


def test_delete_report(api):
    created = api.call("POST", "/reports", body=_report_body()).body["report"]
    assert api.call("DELETE", f"/reports/{created['report_id']}").status_code == 200
    assert api.call("GET", f"/reports/{created['report_id']}").status_code == 404


def test_run_report_now_creates_message(api):
    created = api.call("POST", "/reports", body=_report_body()).body["report"]
    resp = api.call("POST", f"/reports/{created['report_id']}/run", query=UTC)
    assert resp.status_code == 201
    message = resp.body["message"]
    assert message["title"] == "Digest"
    assert message["report_id"] == created["report_id"]
    assert message["sections"][0]["content"] == {"text": "morning!"}

    # The message now appears in the log.
    listed = api.call("GET", "/messages")
    assert any(m["message_id"] == message["message_id"] for m in listed.body["messages"])


def test_run_missing_report_404(api):
    assert api.call("POST", "/reports/nope/run").status_code == 404


def test_run_weekly_report_survives_decimal_roundtrip(api):
    # DynamoDB returns numeric schedule fields (weekday/day_of_month) as Decimal;
    # running a report reads it back and advances next_run, which re-validates the
    # schedule. Regression: Decimal weekday must not fail the int check.
    created = api.call("POST", "/reports", body={
        "name": "Weekly review",
        "schedule": {"frequency": "weekly", "weekday": 2, "time_of_day": "18:00", "tz": "UTC"},
        "sections": [{"type": "custom_message", "config": {"text": "hi"}}],
    }).body["report"]
    assert created["schedule"]["weekday"] == 2

    resp = api.call("POST", f"/reports/{created['report_id']}/run", query=UTC)
    assert resp.status_code == 201

    # And the schedule reads back with a plain int, not a Decimal string.
    got = api.call("GET", f"/reports/{created['report_id']}").body["report"]
    assert got["schedule"]["weekday"] == 2


def test_run_monthly_report_survives_decimal_roundtrip(api):
    created = api.call("POST", "/reports", body={
        "name": "Monthly review",
        "schedule": {"frequency": "monthly", "day_of_month": 15, "time_of_day": "09:00", "tz": "UTC"},
        "sections": [{"type": "custom_message", "config": {"text": "hi"}}],
    }).body["report"]
    resp = api.call("POST", f"/reports/{created['report_id']}/run", query=UTC)
    assert resp.status_code == 201


def test_report_scoped_per_user(api):
    mine = api.call("POST", "/reports", body=_report_body("mine")).body["report"]
    # A non-admin requesting another user's data is blocked by the auth guard.
    other = api.call("GET", f"/reports/{mine['report_id']}", query={"user_id": "other"})
    assert other.status_code == 403


def test_scheduled_sweep_generates_due_reports(api):
    # A report whose next_run is already in the past is due.
    api.call("POST", "/reports", body={
        "name": "Overdue digest",
        "schedule": {"frequency": "daily", "time_of_day": "09:00", "tz": "UTC"},
        "sections": [{"type": "custom_message", "config": {"text": "swept"}}],
    })

    import app
    from datetime import datetime, timezone
    # Sweep with a "now" far in the future so the report is due.
    result = app.run_report_sweep(now=datetime(2030, 1, 1, tzinfo=timezone.utc))
    assert result["generated"] >= 1

    listed = api.call("GET", "/messages")
    assert any(m["title"] == "Overdue digest" for m in listed.body["messages"])


def test_handler_routes_scheduled_event_to_sweep(api):
    import app
    from tests.conftest import FakeLambdaContext
    api.call("POST", "/reports", body=_report_body("Sweep me"))
    # A far-future next_run guarantees due; but default next_run is today 09:00.
    # Use the EventBridge-shaped event to exercise the handler branch.
    result = app.lambda_handler({"source": "aws.events", "detail-type": "Scheduled Event"}, FakeLambdaContext())
    assert "generated" in result


def test_report_with_slack_delivery_runs(api):
    """A report with a Slack destination generates + delivers (local canned)."""
    conn = api.call("POST", "/slack/connections/dev-stub", body={"team_name": "Acme"}).body["connection"]
    body = _report_body("Slack digest")
    body["delivery"] = {"slack": {"connection_id": conn["connection_id"], "channel_id": "C_LOCAL_GENERAL"}}
    created = api.call("POST", "/reports", body=body)
    assert created.status_code == 201
    assert created.body["report"]["delivery"]["slack"]["channel_id"] == "C_LOCAL_GENERAL"

    run = api.call("POST", f"/reports/{created.body['report']['report_id']}/run", query=UTC)
    assert run.status_code == 201
    assert run.body["message"]["title"] == "Slack digest"


def test_report_delivery_survives_bad_connection(api):
    """Best-effort: an unknown connection doesn't fail report generation."""
    body = _report_body("Broken delivery")
    body["delivery"] = {"slack": {"connection_id": "nope", "channel_id": "C_LOCAL_GENERAL"}}
    created = api.call("POST", "/reports", body=body)
    assert created.status_code == 201
    run = api.call("POST", f"/reports/{created.body['report']['report_id']}/run", query=UTC)
    assert run.status_code == 201  # in-app message still created


def test_create_report_rejects_bad_delivery(api):
    body = _report_body("Bad")
    body["delivery"] = {"slack": {"connection_id": ""}}
    resp = api.call("POST", "/reports", body=body)
    assert resp.status_code == 400
