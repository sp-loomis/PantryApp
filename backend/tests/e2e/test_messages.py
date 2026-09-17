"""End-to-end tests for the message-log endpoints."""

DAILY = {"frequency": "daily", "time_of_day": "09:00", "tz": "UTC"}
UTC = {"tz": "UTC"}


def _make_message(api, text="hello"):
    """Create a message by running a one-section report (the only creation path)."""
    report = api.call("POST", "/reports", body={
        "name": "R",
        "schedule": DAILY,
        "sections": [{"type": "custom_message", "config": {"text": text}}],
    }).body["report"]
    return api.call("POST", f"/reports/{report['report_id']}/run", query=UTC).body["message"]


def test_list_messages_empty(api):
    resp = api.call("GET", "/messages")
    assert resp.status_code == 200
    assert resp.body["messages"] == []


def test_unread_flow(api):
    msg = _make_message(api)

    unread = api.call("GET", "/messages/unread")
    assert unread.status_code == 200
    assert unread.body["unread_count"] == 1
    assert unread.body["messages"][0]["message_id"] == msg["message_id"]

    # Mark read -> disappears from unread + count drops.
    read = api.call("POST", f"/messages/{msg['message_id']}/read")
    assert read.status_code == 200
    assert read.body["message"]["read_at"] is not None
    assert api.call("GET", "/messages/unread").body["unread_count"] == 0

    # Mark unread -> restored.
    api.call("POST", f"/messages/{msg['message_id']}/unread")
    assert api.call("GET", "/messages/unread").body["unread_count"] == 1


def test_get_message(api):
    msg = _make_message(api, text="deep link me")
    got = api.call("GET", f"/messages/{msg['message_id']}")
    assert got.status_code == 200
    assert got.body["message"]["sections"][0]["content"] == {"text": "deep link me"}


def test_get_missing_message_404(api):
    assert api.call("GET", "/messages/nope").status_code == 404


def test_unread_not_shadowed_by_parametric_route(api):
    # /messages/unread must resolve to the unread handler, not GET /messages/<id>.
    resp = api.call("GET", "/messages/unread")
    assert resp.status_code == 200
    assert "unread_count" in resp.body


def test_delete_message(api):
    msg = _make_message(api)
    assert api.call("DELETE", f"/messages/{msg['message_id']}").status_code == 200
    assert api.call("GET", f"/messages/{msg['message_id']}").status_code == 404


def test_mark_all_read_bulk(api):
    a = _make_message(api, text="a")
    b = _make_message(api, text="b")
    assert api.call("GET", "/messages/unread").body["unread_count"] == 2

    resp = api.call("POST", "/messages/read-all", body={
        "message_ids": [a["message_id"], b["message_id"]],
    })
    assert resp.status_code == 200
    assert resp.body["updated"] == 2
    assert api.call("GET", "/messages/unread").body["unread_count"] == 0


def test_mark_all_read_bulk_scoped_to_ids(api):
    # Only the passed id is marked read; the other stays unread.
    a = _make_message(api, text="a")
    b = _make_message(api, text="b")
    resp = api.call("POST", "/messages/read-all", body={"message_ids": [a["message_id"]]})
    assert resp.body["updated"] == 1
    unread = api.call("GET", "/messages/unread")
    assert unread.body["unread_count"] == 1
    assert unread.body["messages"][0]["message_id"] == b["message_id"]


def test_mark_all_read_skips_missing_ids(api):
    a = _make_message(api, text="a")
    resp = api.call("POST", "/messages/read-all", body={
        "message_ids": [a["message_id"], "does-not-exist"],
    })
    assert resp.body["updated"] == 1


def test_read_all_bad_body_400(api):
    assert api.call("POST", "/messages/read-all", body={"message_ids": "nope"}).status_code == 400


def test_delete_all_bulk(api):
    a = _make_message(api, text="a")
    b = _make_message(api, text="b")
    resp = api.call("DELETE", "/messages", body={
        "message_ids": [a["message_id"], b["message_id"]],
    })
    assert resp.status_code == 200
    assert resp.body["deleted"] == 2
    assert api.call("GET", "/messages").body["messages"] == []


def test_delete_all_scoped_to_ids(api):
    a = _make_message(api, text="a")
    b = _make_message(api, text="b")
    resp = api.call("DELETE", "/messages", body={"message_ids": [a["message_id"]]})
    assert resp.body["deleted"] == 1
    remaining = api.call("GET", "/messages").body["messages"]
    assert [m["message_id"] for m in remaining] == [b["message_id"]]


def test_delete_all_bad_body_400(api):
    assert api.call("DELETE", "/messages", body={}).status_code == 400


def test_messages_scoped_per_user(api):
    msg = _make_message(api)
    # A non-admin requesting another user's data is blocked by the auth guard.
    other = api.call("GET", f"/messages/{msg['message_id']}", query={"user_id": "other"})
    assert other.status_code == 403
