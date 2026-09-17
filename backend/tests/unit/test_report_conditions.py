"""Unit tests for the report trigger engine (evaluate_trigger / validate_trigger)."""

import pytest

from report_conditions import evaluate_trigger, validate_trigger


class _FakeServices:
    """Exposes item_service.search_items + category_service.list_categories."""

    def __init__(self, items, categories):
        self.item_service = self
        self.category_service = self
        self._items = items
        self._categories = categories

    def search_items(self, user_id, name=None, location_id=None, tags=None, use_by_date_end=None):
        self.last_end = use_by_date_end
        return self._items

    def list_categories(self, user_id):
        return self._categories


def _services(beef_lb):
    """A world with a single 'beef' weight category holding ``beef_lb`` pounds."""
    items = [{"category_id": "c-beef",
              "dimensions": [{"dimension_type": "weight", "value": beef_lb, "unit": "lb"}]}]
    categories = [{"category_id": "c-beef", "name": "beef",
                   "measure_type": "weight", "preferred_unit": "lb"}]
    return _FakeServices(items, categories)


def _trigger(operator, threshold, match="all", outer="all"):
    return {
        "match": outer,
        "conditions": [{
            "query": {},
            "match": match,
            "inequalities": [{"category_id": "c-beef", "operator": operator, "threshold": threshold}],
        }],
    }


def test_empty_trigger_passes():
    assert evaluate_trigger({}, "u1", _services(5)) is True
    assert evaluate_trigger({"conditions": []}, "u1", _services(5)) is True


def test_below_threshold_fires_when_under():
    assert evaluate_trigger(_trigger("below", 10), "u1", _services(8)) is True
    assert evaluate_trigger(_trigger("below", 10), "u1", _services(12)) is False


def test_above_threshold_fires_when_over():
    assert evaluate_trigger(_trigger("above", 10), "u1", _services(12)) is True
    assert evaluate_trigger(_trigger("above", 10), "u1", _services(8)) is False


def test_missing_category_aggregates_to_zero():
    # A category the query yields no items for reads as 0 -> below any positive threshold.
    services = _FakeServices(items=[], categories=[
        {"category_id": "c-beef", "name": "beef", "measure_type": "weight", "preferred_unit": "lb"},
    ])
    assert evaluate_trigger(_trigger("below", 10), "u1", services) is True
    assert evaluate_trigger(_trigger("above", 10), "u1", services) is False


def test_inner_match_all_vs_any():
    # Two inequalities: beef below 10 (True at 8) AND beef above 100 (False at 8).
    def two(match):
        return {"conditions": [{
            "query": {}, "match": match,
            "inequalities": [
                {"category_id": "c-beef", "operator": "below", "threshold": 10},
                {"category_id": "c-beef", "operator": "above", "threshold": 100},
            ],
        }]}
    assert evaluate_trigger(two("all"), "u1", _services(8)) is False
    assert evaluate_trigger(two("any"), "u1", _services(8)) is True


def test_outer_match_all_vs_any():
    # Two conditions on the same world: one True (below 10), one False (above 100).
    def two(outer):
        return {
            "match": outer,
            "conditions": [
                {"query": {}, "match": "all",
                 "inequalities": [{"category_id": "c-beef", "operator": "below", "threshold": 10}]},
                {"query": {}, "match": "all",
                 "inequalities": [{"category_id": "c-beef", "operator": "above", "threshold": 100}]},
            ],
        }
    assert evaluate_trigger(two("all"), "u1", _services(8)) is False
    assert evaluate_trigger(two("any"), "u1", _services(8)) is True


# --- validate_trigger ----------------------------------------------------------

def test_validate_accepts_empty_and_well_formed():
    validate_trigger({})
    validate_trigger(_trigger("below", 10))


def test_validate_rejects_bad_match():
    with pytest.raises(ValueError):
        validate_trigger({"match": "some", "conditions": []})


def test_validate_rejects_bad_operator():
    t = _trigger("between", 10)
    with pytest.raises(ValueError):
        validate_trigger(t)


def test_validate_rejects_non_numeric_threshold():
    t = _trigger("below", "ten")
    with pytest.raises(ValueError):
        validate_trigger(t)


def test_validate_rejects_unknown_category_when_ids_supplied():
    with pytest.raises(ValueError):
        validate_trigger(_trigger("below", 10), valid_category_ids={"other"})
    # Passes when the id is known.
    validate_trigger(_trigger("below", 10), valid_category_ids={"c-beef"})


def test_validate_accepts_expiry_in_condition_query():
    t = _trigger("below", 10)
    t["conditions"][0]["query"] = {"expires_within_days": 7}
    validate_trigger(t)
    t["conditions"][0]["query"] = {"use_by_date_end": "2030-01-01"}
    validate_trigger(t)


@pytest.mark.parametrize("query", [
    {"expires_within_days": 0},
    {"expires_within_days": -5},
    {"use_by_date_end": "not-a-date"},
    {"use_by_date_end": 5},
])
def test_validate_rejects_bad_expiry_in_condition_query(query):
    t = _trigger("below", 10)
    t["conditions"][0]["query"] = query
    with pytest.raises(ValueError):
        validate_trigger(t)


def test_condition_passes_resolved_expiry_end():
    # The condition query's relative span reaches search_items as a resolved bound.
    from datetime import date, timedelta

    services = _services(5)
    trigger = _trigger("below", 10)
    trigger["conditions"][0]["query"] = {"expires_within_days": 3}
    evaluate_trigger(trigger, "u1", services)
    assert services.item_service.last_end == (date.today() + timedelta(days=3)).isoformat()
