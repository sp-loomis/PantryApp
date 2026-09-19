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


def test_list_tasks_name_partial_match(task_service):
    task_service.create_task(USER, "Clean the coop", tags=["animals"], tz="UTC")
    task_service.create_task(USER, "Water garden", tags=["garden"], tz="UTC")

    # Partial/fuzzy name match (same matcher as inventory search).
    names = [t["name"] for t in task_service.list_tasks(USER, tz="UTC", status="all", name="clean")]
    assert names == ["Clean the coop"]


def test_list_tasks_tags_and_filter(task_service):
    task_service.create_task(USER, "A", tags=["kitchen", "urgent"], tz="UTC")
    task_service.create_task(USER, "B", tags=["kitchen"], tz="UTC")

    # tags is an AND filter: only the task carrying BOTH tags matches.
    both = task_service.list_tasks(USER, tz="UTC", status="all", tags=["kitchen", "urgent"])
    assert [t["name"] for t in both] == ["A"]


def test_list_tasks_legacy_scalar_tag_still_filters(task_service):
    task_service.create_task(USER, "A", tags=["kitchen"], tz="UTC")
    task_service.create_task(USER, "B", tags=["garden"], tz="UTC")
    got = task_service.list_tasks(USER, tz="UTC", status="all", tag="garden")
    assert [t["name"] for t in got] == ["B"]


# ---------------------------------------------------------------------------
# Decision paths: decision tasks + triggers
# ---------------------------------------------------------------------------

def test_decision_task_requires_yes_or_no(task_service):
    t = task_service.create_task(USER, "Let horses out?", answer_mode="yesno",
                                 recurrence_type="daily", tz="UTC")
    tid = t["task_id"]
    with pytest.raises(ValueError):
        task_service.complete_task(USER, tid, tz="UTC", now=DAY1)  # no decision
    answered = task_service.complete_task(USER, tid, decision="yes", tz="UTC", now=DAY1)
    assert answered["done"] is True
    assert answered["last_decision"] == "yes"


def test_yes_branch_activates_dependent(task_service):
    # One-shot decision keeps the test date-stable (list_tasks uses the real clock).
    src = task_service.create_task(USER, "Let horses out?", answer_mode="yesno", tz="UTC")
    dep = task_service.create_task(
        USER, "Clean stalls", tz="UTC",
        trigger={"source_task_id": src["task_id"], "on": "yes", "deadline": "same_day"},
    )
    # Dormant until the decision is made.
    assert task_service.get_task(USER, dep["task_id"], tz="UTC")["active"] is False

    task_service.complete_task(USER, src["task_id"], decision="yes", tz="UTC")
    active = [t["task_id"] for t in task_service.list_tasks(USER, tz="UTC", status="active")]
    assert dep["task_id"] in active


def test_no_branch_leaves_yes_dependent_dormant(task_service):
    src = task_service.create_task(USER, "Let horses out?", answer_mode="yesno", tz="UTC")
    yes_dep = task_service.create_task(
        USER, "Clean stalls", tz="UTC",
        trigger={"source_task_id": src["task_id"], "on": "yes", "deadline": "same_day"})
    no_dep = task_service.create_task(
        USER, "Give lunch", tz="UTC",
        trigger={"source_task_id": src["task_id"], "on": "no", "deadline": "same_day"})

    task_service.complete_task(USER, src["task_id"], decision="no", tz="UTC")
    active = {t["task_id"] for t in task_service.list_tasks(USER, tz="UTC", status="active")}
    assert no_dep["task_id"] in active
    assert yes_dep["task_id"] not in active


def test_trigger_source_must_exist(task_service):
    with pytest.raises(ValueError):
        task_service.create_task(USER, "orphan", tz="UTC",
                                 trigger={"source_task_id": "nope", "on": "any",
                                          "deadline": "same_day"})


def test_yesno_trigger_requires_decision_source(task_service):
    plain = task_service.create_task(USER, "plain checkbox", tz="UTC")
    with pytest.raises(ValueError):
        task_service.create_task(USER, "dep", tz="UTC",
                                 trigger={"source_task_id": plain["task_id"], "on": "yes",
                                          "deadline": "same_day"})


def test_offset_deadline_requires_offset_days(task_service):
    src = task_service.create_task(USER, "decide?", answer_mode="yesno",
                                   recurrence_type="daily", tz="UTC")
    with pytest.raises(ValueError):
        task_service.create_task(USER, "dep", tz="UTC",
                                 trigger={"source_task_id": src["task_id"], "on": "yes",
                                          "deadline": "offset"})


def test_trigger_cycle_rejected_on_update(task_service):
    a = task_service.create_task(USER, "A", answer_mode="yesno",
                                 recurrence_type="daily", tz="UTC")
    b = task_service.create_task(
        USER, "B", answer_mode="yesno", tz="UTC",
        trigger={"source_task_id": a["task_id"], "on": "yes", "deadline": "same_day"})
    # Point A at B -> cycle A->B->A.
    with pytest.raises(ValueError):
        task_service.update_task(
            USER, a["task_id"],
            {"trigger": {"source_task_id": b["task_id"], "on": "yes", "deadline": "same_day"}},
            tz="UTC")
