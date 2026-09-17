"""Unit tests for the report section renderer registry."""

from datetime import date, timedelta

import pytest

from report_sections import (
    render_section,
    validate_sections,
    resolve_use_by_end,
    SECTION_TYPES,
)


class _FakeServices:
    """Stand-in exposing the service methods renderers call."""

    def __init__(self, tasks=None, items=None, categories=None):
        self.task_service = self
        self.item_service = self
        self.category_service = self
        self._tasks = tasks or []
        self._items = items or []
        self._categories = categories or []

    def list_tasks(self, user_id, tz=None, status=None, tag=None, tags=None, name=None):
        self.last_task_query = {
            "status": status, "tag": tag, "tags": tags, "name": name, "tz": tz,
        }
        return self._tasks

    def search_items(self, user_id, name=None, location_id=None, tags=None, use_by_date_end=None):
        self.last_item_query = {
            "name": name, "location_id": location_id, "tags": tags,
            "use_by_date_end": use_by_date_end,
        }
        return self._items

    def list_categories(self, user_id):
        return self._categories


def test_custom_message_renders_text():
    section = {"type": "custom_message", "heading": "Note", "config": {"text": "hello"}}
    result = render_section(section, "u1", _FakeServices())
    assert result == {"type": "custom_message", "heading": "Note", "content": {"text": "hello"}}


def test_task_query_passes_filters_and_counts():
    services = _FakeServices(tasks=[{"name": "a"}, {"name": "b"}])
    section = {
        "type": "task_query", "heading": "Chores",
        "config": {"status": "active", "tags": ["kitchen"], "name": "clean"},
    }
    result = render_section(section, "u1", services, tz="UTC")
    assert result["content"] == {"items": [{"name": "a"}, {"name": "b"}], "count": 2}
    assert services.last_task_query == {
        "status": "active", "tag": None, "tags": ["kitchen"], "name": "clean", "tz": "UTC",
    }


def test_task_query_legacy_scalar_tag_still_works():
    services = _FakeServices(tasks=[])
    section = {"type": "task_query", "config": {"tag": "kitchen"}}
    render_section(section, "u1", services, tz="UTC")
    # _tags() folds a stored scalar tag into the tags list.
    assert services.last_task_query["tags"] == ["kitchen"]


def test_item_query_routes_through_search_items():
    services = _FakeServices(items=[{"name": "milk"}])
    section = {
        "type": "item_query", "heading": "Low stock",
        "config": {"tags": ["dairy"], "name": "mil", "location_id": "loc-1"},
    }
    result = render_section(section, "u1", services)
    assert result["content"] == {
        "items": [{"name": "milk"}], "count": 1, "category_totals": [],
    }
    assert services.last_item_query == {
        "name": "mil", "location_id": "loc-1", "tags": ["dairy"], "use_by_date_end": None,
    }


def test_item_query_includes_category_totals():
    services = _FakeServices(
        items=[
            {"name": "ribeye", "category_id": "c-beef",
             "dimensions": [{"dimension_type": "weight", "value": 2, "unit": "lb"}]},
            {"name": "chuck", "category_id": "c-beef",
             "dimensions": [{"dimension_type": "weight", "value": 3, "unit": "lb"}]},
        ],
        categories=[
            {"category_id": "c-beef", "name": "beef",
             "measure_type": "weight", "preferred_unit": "lb"},
        ],
    )
    section = {"type": "item_query", "config": {}}
    totals = render_section(section, "u1", services)["content"]["category_totals"]
    assert len(totals) == 1
    assert totals[0]["category_id"] == "c-beef"
    assert totals[0]["value"] == pytest.approx(5.0)
    assert totals[0]["unit"] == "lb"


def test_item_query_empty_filters_pass_none():
    # No filters -> search_items called with all None.
    s = _FakeServices()
    render_section({"type": "item_query", "config": {}}, "u1", s)
    assert s.last_item_query == {
        "name": None, "location_id": None, "tags": None, "use_by_date_end": None,
    }


def test_item_query_passes_resolved_expiry_end():
    # A relative span resolves to an absolute date-only bound at render time.
    s = _FakeServices()
    render_section({"type": "item_query", "config": {"expires_within_days": 7}}, "u1", s)
    assert s.last_item_query["use_by_date_end"] == (date.today() + timedelta(days=7)).isoformat()


def test_item_query_passes_absolute_expiry_end():
    s = _FakeServices()
    render_section(
        {"type": "item_query", "config": {"use_by_date_end": "2030-01-01"}}, "u1", s
    )
    assert s.last_item_query["use_by_date_end"] == "2030-01-01"


def test_resolve_use_by_end():
    assert resolve_use_by_end({}) is None
    assert resolve_use_by_end({"use_by_date_end": "2030-01-01"}) == "2030-01-01"
    assert resolve_use_by_end({"expires_within_days": 3}) == (
        date.today() + timedelta(days=3)
    ).isoformat()
    # A relative span wins over an absolute date if both are present.
    assert resolve_use_by_end({"expires_within_days": 1, "use_by_date_end": "2030-01-01"}) == (
        date.today() + timedelta(days=1)
    ).isoformat()


def test_unknown_section_type_raises():
    with pytest.raises(ValueError):
        render_section({"type": "nope"}, "u1", _FakeServices())


def test_validate_sections_accepts_valid():
    validate_sections([
        {"type": "custom_message", "config": {"text": "hi"}},
        {"type": "task_query", "config": {"status": "active", "tags": ["a", "b"], "name": "clean"}},
        {"type": "item_query", "config": {"location_id": "loc-1", "tags": ["dairy"]}},
        {"type": "item_query", "config": {"expires_within_days": 7}},
        {"type": "item_query", "config": {"use_by_date_end": "2030-01-01"}},
    ])


@pytest.mark.parametrize("bad", [
    "notalist",
    [{"type": "bogus"}],
    [{"type": "custom_message", "config": {}}],       # missing text
    [{"type": "custom_message", "config": {"text": ""}}],
    [{"type": "task_query", "config": "notdict"}],
    [{"type": "task_query", "config": {"tags": "notalist"}}],
    [{"type": "task_query", "config": {"tags": [1, 2]}}],
    [{"type": "item_query", "config": {"name": 5}}],
    [{"type": "item_query", "config": {"location_id": 5}}],
    [{"type": "item_query", "config": {"expires_within_days": 0}}],
    [{"type": "item_query", "config": {"expires_within_days": -1}}],
    [{"type": "item_query", "config": {"expires_within_days": True}}],
    [{"type": "item_query", "config": {"use_by_date_end": 5}}],
    [{"type": "item_query", "config": {"use_by_date_end": "not-a-date"}}],
])
def test_validate_sections_rejects_bad(bad):
    with pytest.raises(ValueError):
        validate_sections(bad)


def test_registry_exposes_v1_types():
    assert SECTION_TYPES == {"custom_message", "task_query", "item_query"}
