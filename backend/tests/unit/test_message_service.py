"""Unit tests for MessageService bulk operations."""


def _create(message_service, n):
    """Create ``n`` messages and return their ids (all start unread)."""
    ids = []
    for i in range(n):
        msg = message_service.create_message(user_id="u1", title=f"m{i}")
        ids.append(msg["message_id"])
    return ids


def test_mark_read_bulk_marks_and_counts(message_service):
    ids = _create(message_service, 3)
    updated = message_service.mark_read_bulk("u1", ids)
    assert updated == 3
    assert message_service.unread_count("u1") == 0
    for mid in ids:
        assert message_service.get_message("u1", mid)["read_at"] is not None


def test_mark_read_bulk_scoped_to_ids(message_service):
    a, b = _create(message_service, 2)
    updated = message_service.mark_read_bulk("u1", [a])
    assert updated == 1
    assert message_service.get_message("u1", a)["read_at"] is not None
    assert message_service.get_message("u1", b)["read_at"] is None


def test_mark_read_bulk_skips_missing(message_service):
    (a,) = _create(message_service, 1)
    assert message_service.mark_read_bulk("u1", [a, "missing"]) == 1


def test_mark_read_bulk_empty(message_service):
    assert message_service.mark_read_bulk("u1", []) == 0


def test_delete_bulk_removes_and_counts(message_service):
    ids = _create(message_service, 3)
    deleted = message_service.delete_bulk("u1", ids)
    assert deleted == 3
    assert message_service.list_messages("u1") == []


def test_delete_bulk_scoped_to_ids(message_service):
    a, b = _create(message_service, 2)
    deleted = message_service.delete_bulk("u1", [a])
    assert deleted == 1
    remaining = [m["message_id"] for m in message_service.list_messages("u1")]
    assert remaining == [b]


def test_delete_bulk_skips_missing(message_service):
    (a,) = _create(message_service, 1)
    assert message_service.delete_bulk("u1", [a, "missing"]) == 1


def test_delete_bulk_empty(message_service):
    assert message_service.delete_bulk("u1", []) == 0
