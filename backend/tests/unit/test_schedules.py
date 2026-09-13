"""Unit tests for report schedule -> next_run computation."""

from datetime import datetime, timezone

import pytest

from schedules import compute_next_run, validate_schedule


def _dt(s: str) -> datetime:
    dt = datetime.fromisoformat(s)
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)


def test_daily_before_time_fires_today():
    schedule = {"frequency": "daily", "time_of_day": "09:00", "tz": "UTC"}
    assert compute_next_run(schedule, _dt("2026-09-12T08:00:00+00:00")) == "2026-09-12T09:00:00+00:00"


def test_daily_after_time_fires_tomorrow():
    schedule = {"frequency": "daily", "time_of_day": "09:00", "tz": "UTC"}
    assert compute_next_run(schedule, _dt("2026-09-12T10:00:00+00:00")) == "2026-09-13T09:00:00+00:00"


def test_daily_exactly_at_time_fires_next_day():
    # A report generated at its firing time must schedule the following occurrence.
    schedule = {"frequency": "daily", "time_of_day": "09:00", "tz": "UTC"}
    assert compute_next_run(schedule, _dt("2026-09-12T09:00:00+00:00")) == "2026-09-13T09:00:00+00:00"


def test_daily_respects_timezone():
    # 09:00 America/New_York on 2026-09-12 == 13:00 UTC (EDT, UTC-4).
    schedule = {"frequency": "daily", "time_of_day": "09:00", "tz": "America/New_York"}
    assert compute_next_run(schedule, _dt("2026-09-12T00:00:00+00:00")) == "2026-09-12T13:00:00+00:00"


def test_weekly_picks_next_weekday():
    # 2026-09-12 is a Saturday (weekday 5). Target Monday (0).
    schedule = {"frequency": "weekly", "weekday": 0, "time_of_day": "09:00", "tz": "UTC"}
    assert compute_next_run(schedule, _dt("2026-09-12T12:00:00+00:00")) == "2026-09-14T09:00:00+00:00"


def test_weekly_same_day_before_time_fires_today():
    # 2026-09-14 is a Monday.
    schedule = {"frequency": "weekly", "weekday": 0, "time_of_day": "09:00", "tz": "UTC"}
    assert compute_next_run(schedule, _dt("2026-09-14T06:00:00+00:00")) == "2026-09-14T09:00:00+00:00"


def test_monthly_before_day_fires_this_month():
    schedule = {"frequency": "monthly", "day_of_month": 15, "time_of_day": "09:00", "tz": "UTC"}
    assert compute_next_run(schedule, _dt("2026-09-12T09:00:00+00:00")) == "2026-09-15T09:00:00+00:00"


def test_monthly_after_day_rolls_to_next_month():
    schedule = {"frequency": "monthly", "day_of_month": 5, "time_of_day": "09:00", "tz": "UTC"}
    assert compute_next_run(schedule, _dt("2026-09-12T09:00:00+00:00")) == "2026-10-05T09:00:00+00:00"


def test_monthly_year_rollover():
    schedule = {"frequency": "monthly", "day_of_month": 5, "time_of_day": "09:00", "tz": "UTC"}
    assert compute_next_run(schedule, _dt("2026-12-12T09:00:00+00:00")) == "2027-01-05T09:00:00+00:00"


@pytest.mark.parametrize("bad", [
    {},
    {"frequency": "hourly"},
    {"frequency": "daily", "time_of_day": "9am"},
    {"frequency": "daily", "time_of_day": "25:00"},
    {"frequency": "weekly", "weekday": 9},
    {"frequency": "monthly", "day_of_month": 31},
])
def test_validate_schedule_rejects_bad(bad):
    with pytest.raises(ValueError):
        validate_schedule(bad)
