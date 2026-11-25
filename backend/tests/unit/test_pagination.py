"""Unit tests for the DynamoDB pagination helper (``services._paginate``)."""

from services import _paginate


def test_paginate_follows_last_evaluated_key():
    """Multiple pages are concatenated; ExclusiveStartKey chains the pages."""
    pages = [
        {"Items": [{"id": 1}, {"id": 2}], "LastEvaluatedKey": {"id": 2}},
        {"Items": [{"id": 3}], "LastEvaluatedKey": {"id": 3}},
        {"Items": [{"id": 4}]},  # last page: no LastEvaluatedKey
    ]
    calls = []

    def fake_op(**kwargs):
        calls.append(kwargs)
        return pages[len(calls) - 1]

    result = _paginate(fake_op, KeyConditionExpression="dummy")

    assert [r["id"] for r in result] == [1, 2, 3, 4]
    # First call carries no ExclusiveStartKey; later calls chain the prior key.
    assert "ExclusiveStartKey" not in calls[0]
    assert calls[1]["ExclusiveStartKey"] == {"id": 2}
    assert calls[2]["ExclusiveStartKey"] == {"id": 3}
    assert all(c["KeyConditionExpression"] == "dummy" for c in calls)


def test_paginate_single_page():
    def fake_op(**kwargs):
        return {"Items": [{"id": 1}]}

    assert _paginate(fake_op) == [{"id": 1}]


def test_paginate_empty():
    def fake_op(**kwargs):
        return {}

    assert _paginate(fake_op) == []
