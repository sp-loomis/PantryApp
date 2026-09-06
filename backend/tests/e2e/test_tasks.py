"""E2E route tests for the task endpoints.

Each test drives a whole HTTP request through ``app.lambda_handler`` via the
``api`` fixture. Requests pass ``tz=UTC`` so computed windows are deterministic
regardless of where the tests run.
"""

from datetime import datetime, timedelta, timezone

UTC = {"tz": "UTC"}


def _utc_today():
    """Today's date in UTC (requests pass tz=UTC, so windows are UTC-based)."""
    return datetime.now(timezone.utc).date()


def _iso_in(days: int) -> str:
    """An ISO date ``days`` from UTC today (negative for the past)."""
    return (_utc_today() + timedelta(days=days)).isoformat()


# ---------------------------------------------------------------------------
# POST /tasks
# ---------------------------------------------------------------------------

def test_create_one_shot_task_happy(api):
    resp = api.call("POST", "/tasks", body={"name": "Fix the fence", "due_date": _iso_in(3)}, query=UTC)

    assert resp.status_code == 201
    task = resp.body["task"]
    assert task["name"] == "Fix the fence"
    assert task["recurrence_type"] == "none"
    assert task["graceful"] is True
    assert task["done"] is False
    assert task["computed_status"] == "due_soon"
    assert "task_id" in task


def test_create_daily_task_defaults_and_status(api):
    resp = api.call("POST", "/tasks", body={"name": "Water plants", "recurrence_type": "daily"}, query=UTC)

    assert resp.status_code == 201
    task = resp.body["task"]
    assert task["recurrence_type"] == "daily"
    assert task["computed_status"] == "due_today"
    assert task["active"] is True


def test_create_interval_task_defaults_anchor_to_today(api):
    resp = api.call(
        "POST", "/tasks",
        body={"name": "Deep clean coop", "recurrence_type": "interval", "recurrence_interval": 3},
        query=UTC,
    )

    assert resp.status_code == 201
    assert resp.body["task"]["anchor_date"] == _utc_today().isoformat()


def test_create_task_missing_name_returns_400(api):
    resp = api.call("POST", "/tasks", body={"recurrence_type": "daily"}, query=UTC)

    assert resp.status_code == 400
    assert "name" in resp.body["error"]


def test_create_interval_without_positive_interval_returns_400(api):
    resp = api.call(
        "POST", "/tasks",
        body={"name": "bad", "recurrence_type": "interval", "recurrence_interval": 0},
        query=UTC,
    )

    assert resp.status_code == 400
    assert "recurrence_interval" in resp.body["error"]


def test_create_task_invalid_recurrence_type_returns_400(api):
    resp = api.call("POST", "/tasks", body={"name": "bad", "recurrence_type": "hourly"}, query=UTC)

    assert resp.status_code == 400
    assert "recurrence_type" in resp.body["error"]


# ---------------------------------------------------------------------------
# GET /tasks (+ status/tag filters)
# ---------------------------------------------------------------------------

def test_list_tasks_active_filter_hides_done(api):
    daily = api.call("POST", "/tasks", body={"name": "Feed chickens", "recurrence_type": "daily"}, query=UTC).body["task"]
    api.call("POST", "/tasks", body={"name": "One-off", "due_date": _iso_in(2)}, query=UTC)

    api.call("POST", f"/tasks/{daily['task_id']}/complete", query=UTC)

    active = api.call("GET", "/tasks", query={"tz": "UTC", "status": "active"}).body["tasks"]
    names = {t["name"] for t in active}
    assert "Feed chickens" not in names  # completed for today
    assert "One-off" in names


def test_list_tasks_hides_graceful_overdue_one_shot(api):
    api.call("POST", "/tasks", body={"name": "Missed chore", "due_date": _iso_in(-2), "graceful": True}, query=UTC)
    api.call("POST", "/tasks", body={"name": "Nagging chore", "due_date": _iso_in(-2), "graceful": False}, query=UTC)

    active = api.call("GET", "/tasks", query={"tz": "UTC", "status": "active"}).body["tasks"]
    names = {t["name"] for t in active}
    assert "Missed chore" not in names  # graceful -> disappears
    assert "Nagging chore" in names  # non-graceful -> still overdue


def test_list_tasks_filters_by_tag(api):
    api.call("POST", "/tasks", body={"name": "Garden task", "tags": ["garden"], "recurrence_type": "daily"}, query=UTC)
    api.call("POST", "/tasks", body={"name": "Kitchen task", "tags": ["kitchen"], "recurrence_type": "daily"}, query=UTC)

    tasks = api.call("GET", "/tasks", query={"tz": "UTC", "tag": "garden"}).body["tasks"]
    assert [t["name"] for t in tasks] == ["Garden task"]


# ---------------------------------------------------------------------------
# Complete / uncomplete cycle
# ---------------------------------------------------------------------------

def test_complete_then_uncomplete_daily_task(api):
    task = api.call("POST", "/tasks", body={"name": "Sweep porch", "recurrence_type": "daily"}, query=UTC).body["task"]

    completed = api.call("POST", f"/tasks/{task['task_id']}/complete", query=UTC).body["task"]
    assert completed["done"] is True
    assert completed["computed_status"] == "done"

    uncompleted = api.call("POST", f"/tasks/{task['task_id']}/uncomplete", query=UTC).body["task"]
    assert uncompleted["done"] is False
    assert uncompleted["computed_status"] == "due_today"


def test_complete_missing_task_returns_404(api):
    resp = api.call("POST", "/tasks/nope/complete", query=UTC)
    assert resp.status_code == 404


# ---------------------------------------------------------------------------
# GET / PUT / DELETE /tasks/<id>
# ---------------------------------------------------------------------------

def test_get_task_happy(api):
    task = api.call("POST", "/tasks", body={"name": "Split firewood", "due_date": _iso_in(1)}, query=UTC).body["task"]

    resp = api.call("GET", f"/tasks/{task['task_id']}", query=UTC)
    assert resp.status_code == 200
    assert resp.body["task"]["task_id"] == task["task_id"]


def test_get_task_not_found_returns_404(api):
    assert api.call("GET", "/tasks/does-not-exist", query=UTC).status_code == 404


def test_update_task_changes_recurrence(api):
    task = api.call("POST", "/tasks", body={"name": "Chore", "recurrence_type": "daily"}, query=UTC).body["task"]

    resp = api.call(
        "PUT", f"/tasks/{task['task_id']}",
        body={"recurrence_type": "weekly", "name": "Weekly chore"},
        query=UTC,
    )
    assert resp.status_code == 200
    assert resp.body["task"]["recurrence_type"] == "weekly"
    assert resp.body["task"]["name"] == "Weekly chore"


def test_update_task_clearing_due_date_removes_sparse_key(api):
    task = api.call("POST", "/tasks", body={"name": "Dated", "due_date": _iso_in(5)}, query=UTC).body["task"]

    resp = api.call("PUT", f"/tasks/{task['task_id']}", body={"due_date": None}, query=UTC)
    assert resp.status_code == 200
    assert resp.body["task"]["due_date"] is None


def test_delete_task_happy(api):
    task = api.call("POST", "/tasks", body={"name": "Temp", "recurrence_type": "daily"}, query=UTC).body["task"]

    resp = api.call("DELETE", f"/tasks/{task['task_id']}")
    assert resp.status_code == 200
    assert "deleted" in resp.body["message"].lower()
    assert api.call("GET", f"/tasks/{task['task_id']}", query=UTC).status_code == 404


def test_delete_task_not_found_returns_404(api):
    assert api.call("DELETE", "/tasks/does-not-exist").status_code == 404


# ---------------------------------------------------------------------------
# Admin override + auth
# ---------------------------------------------------------------------------

def test_tasks_scoped_per_user(api):
    api.call("POST", "/tasks", body={"name": "Mine", "recurrence_type": "daily"}, user="user-1", query=UTC)

    other = api.call("GET", "/tasks", user="user-2", query=UTC)
    assert other.body["tasks"] == []


def test_unauthenticated_request_returns_401(api):
    resp = api.call("GET", "/tasks", user=None, query=UTC)
    assert resp.status_code == 401
