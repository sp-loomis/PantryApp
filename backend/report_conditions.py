"""Category-condition trigger engine for reports.

A report may carry an optional ``trigger`` that gates generation: the scheduled
sweep renders the report only when the trigger evaluates true against live data.
This keeps the schedule as the *check cadence* while the trigger decides whether
there is anything worth sending (e.g. "notify when my beef is below 10 lb").

Trigger shape (also documented on :class:`models.Report`)::

    {
      "match": "all" | "any",          # join across conditions (default "all")
      "conditions": [
        {
          # same shape as item_query (incl. optional expiry filter)
          "query": { "location_id", "tags", "name",
                     "expires_within_days", "use_by_date_end" },
          "match": "all" | "any",       # join across inequalities (default "all")
          "inequalities": [
            { "category_id", "operator": "below"|"above", "threshold": <number> }
          ]
        }
      ]
    }

Each inequality compares a category's aggregate value — over the items matched by
its condition's query — against ``threshold`` in the category's own unit (item
count for a ``count`` category; summed measure in ``preferred_unit`` otherwise). A
category with no matching items aggregates to 0. An empty/absent trigger passes.
"""

from typing import Any, Dict, List

from dimensions import aggregate_by_category
from report_sections import resolve_use_by_end, _validate_expiry

_MATCH_MODES = ("all", "any")
_OPERATORS = ("below", "above")


def _join(results: List[bool], match: str) -> bool:
    """Combine boolean results with AND (``all``) or OR (``any``)."""
    return any(results) if match == "any" else all(results)


def _condition_aggregates(
    condition: Dict[str, Any], user_id: str, services: Any
) -> Dict[str, float]:
    """Run a condition's query and return {category_id: aggregate value}."""
    query = condition.get("query") or {}
    items = services.item_service.search_items(
        user_id,
        name=query.get("name") or None,
        location_id=query.get("location_id") or None,
        tags=query.get("tags") or None,
        use_by_date_end=resolve_use_by_end(query),
    )
    categories = services.category_service.list_categories(user_id)
    return {
        agg["category_id"]: agg["value"]
        for agg in aggregate_by_category(items, categories)
    }


def _evaluate_inequality(ineq: Dict[str, Any], aggregates: Dict[str, float]) -> bool:
    """Evaluate one inequality against pre-computed category aggregates."""
    value = aggregates.get(ineq.get("category_id"), 0)
    threshold = float(ineq.get("threshold", 0))
    if ineq.get("operator") == "above":
        return value > threshold
    return value < threshold  # "below"


def _evaluate_condition(condition: Dict[str, Any], user_id: str, services: Any) -> bool:
    """Evaluate one condition: run its query, join its inequalities."""
    inequalities = condition.get("inequalities") or []
    if not inequalities:
        # No constraints -> AND is vacuously true, OR is vacuously false.
        return _join([], condition.get("match", "all"))
    aggregates = _condition_aggregates(condition, user_id, services)
    results = [_evaluate_inequality(i, aggregates) for i in inequalities]
    return _join(results, condition.get("match", "all"))


def evaluate_trigger(trigger: Dict[str, Any], user_id: str, services: Any) -> bool:
    """Return whether a report's trigger passes against live data.

    ``services`` exposes ``.item_service`` and ``.category_service`` (the
    :class:`ReportGenerator` satisfies this). An empty/absent trigger passes.
    """
    if not trigger:
        return True
    conditions = trigger.get("conditions") or []
    if not conditions:
        return True
    results = [_evaluate_condition(c, user_id, services) for c in conditions]
    return _join(results, trigger.get("match", "all"))


def validate_trigger(trigger: Any, valid_category_ids: Any = None) -> None:
    """Validate a report's optional trigger, raising ValueError on any problem.

    When ``valid_category_ids`` is provided, every referenced ``category_id`` must
    appear in it (so a trigger cannot point at a deleted/foreign category).
    """
    if not trigger:
        return
    if not isinstance(trigger, dict):
        raise ValueError("trigger must be an object")

    match = trigger.get("match", "all")
    if match not in _MATCH_MODES:
        raise ValueError(f"trigger.match must be one of {list(_MATCH_MODES)}")

    conditions = trigger.get("conditions")
    if conditions is None:
        return
    if not isinstance(conditions, list):
        raise ValueError("trigger.conditions must be a list")

    for i, cond in enumerate(conditions):
        if not isinstance(cond, dict):
            raise ValueError(f"trigger.conditions[{i}] must be an object")
        cond_match = cond.get("match", "all")
        if cond_match not in _MATCH_MODES:
            raise ValueError(
                f"trigger.conditions[{i}].match must be one of {list(_MATCH_MODES)}"
            )
        query = cond.get("query")
        if query is not None and not isinstance(query, dict):
            raise ValueError(f"trigger.conditions[{i}].query must be an object")
        if isinstance(query, dict):
            _validate_expiry(query, f"trigger.conditions[{i}].query")

        inequalities = cond.get("inequalities")
        if inequalities is not None and not isinstance(inequalities, list):
            raise ValueError(f"trigger.conditions[{i}].inequalities must be a list")
        for j, ineq in enumerate(inequalities or []):
            where = f"trigger.conditions[{i}].inequalities[{j}]"
            if not isinstance(ineq, dict):
                raise ValueError(f"{where} must be an object")
            category_id = ineq.get("category_id")
            if not category_id or not isinstance(category_id, str):
                raise ValueError(f"{where} requires a non-empty 'category_id'")
            if valid_category_ids is not None and category_id not in valid_category_ids:
                raise ValueError(f"{where} references unknown category {category_id!r}")
            if ineq.get("operator") not in _OPERATORS:
                raise ValueError(f"{where}.operator must be one of {list(_OPERATORS)}")
            threshold = ineq.get("threshold")
            if isinstance(threshold, bool) or not isinstance(threshold, (int, float)):
                raise ValueError(f"{where}.threshold must be a number")
