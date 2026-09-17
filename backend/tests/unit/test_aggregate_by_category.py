"""Unit tests for category-grouped aggregation and category measure validation."""

import pytest

from dimensions import aggregate_by_category, validate_category_measure


def _cat(cid, name, measure_type, unit=None):
    return {"category_id": cid, "name": name, "measure_type": measure_type, "preferred_unit": unit}


def _item(cid, dims):
    return {"category_id": cid, "dimensions": dims}


def test_count_category_counts_items_ignoring_dimensions():
    cats = [_cat("c1", "eggs", "count")]
    items = [
        _item("c1", [{"dimension_type": "count", "value": 12, "unit": "units"}]),
        _item("c1", [{"dimension_type": "count", "value": 6, "unit": "units"}]),
    ]
    result = aggregate_by_category(items, cats)
    assert result == [{
        "category_id": "c1", "name": "eggs", "measure_type": "count",
        "value": 2.0, "unit": "items",
    }]


def test_weight_category_sums_and_converts_to_preferred_unit():
    cats = [_cat("c1", "beef", "weight", "lb")]
    items = [
        _item("c1", [{"dimension_type": "weight", "value": 500, "unit": "g"}]),
        _item("c1", [{"dimension_type": "weight", "value": 1, "unit": "kg"}]),
    ]
    result = aggregate_by_category(items, cats)
    # 1500 g -> pounds
    assert result[0]["unit"] == "lb"
    assert result[0]["value"] == pytest.approx(1500 / 453.59237)


def test_volume_category_sums_in_preferred_unit():
    cats = [_cat("c1", "milk", "volume", "l")]
    items = [
        _item("c1", [{"dimension_type": "volume", "value": 500, "unit": "ml"}]),
        _item("c1", [{"dimension_type": "volume", "value": 1, "unit": "l"}]),
    ]
    result = aggregate_by_category(items, cats)
    assert result[0]["unit"] == "l"
    assert result[0]["value"] == pytest.approx(1.5)


def test_uncategorized_and_unknown_category_items_excluded():
    cats = [_cat("c1", "beef", "weight", "lb")]
    items = [
        _item("c1", [{"dimension_type": "weight", "value": 1, "unit": "lb"}]),
        _item(None, [{"dimension_type": "weight", "value": 9, "unit": "lb"}]),
        _item("ghost", [{"dimension_type": "weight", "value": 9, "unit": "lb"}]),
    ]
    result = aggregate_by_category(items, cats)
    assert len(result) == 1
    assert result[0]["value"] == pytest.approx(1.0)


def test_results_sorted_by_name():
    cats = [_cat("c1", "zucchini", "count"), _cat("c2", "apples", "count")]
    items = [_item("c1", []), _item("c2", [])]
    names = [r["name"] for r in aggregate_by_category(items, cats)]
    assert names == ["apples", "zucchini"]


# --- validate_category_measure -------------------------------------------------

def test_count_category_rejects_preferred_unit():
    with pytest.raises(ValueError):
        validate_category_measure("count", "lb")


def test_count_category_allows_no_unit():
    validate_category_measure("count", None)  # no raise


def test_weight_category_requires_valid_unit():
    validate_category_measure("weight", "lb")  # no raise
    with pytest.raises(ValueError):
        validate_category_measure("weight", None)
    with pytest.raises(ValueError):
        validate_category_measure("weight", "gallon")


def test_invalid_measure_type_rejected():
    with pytest.raises(ValueError):
        validate_category_measure("length", "m")
