"""Service-layer tests for the ledger, consume, and soft-delete behavior."""

from conftest import USER
from models import (
    EVENT_ITEM_CREATED, EVENT_ITEM_ADJUSTED, EVENT_ITEM_CONSUMED,
    EVENT_ITEM_REMOVED, EVENT_TASK_COMPLETED, EVENT_TASK_UNCOMPLETED,
    ENTITY_ITEM, ENTITY_TASK,
)


def _event_types(ledger, entity_type, entity_id):
    return [
        e["event_type"]
        for e in ledger.list_entity_history(USER, entity_type, entity_id)
    ]


# --- LedgerService primitives ------------------------------------------------

def test_append_and_entity_history_ordered(ledger_service):
    from models import LedgerEvent

    for et in ("item_created", "item_adjusted", "item_consumed"):
        ledger_service.append(
            LedgerEvent.create(USER, ENTITY_ITEM, "item-1", et)
        )
    # A second entity's events must not bleed into the first's history.
    ledger_service.append(LedgerEvent.create(USER, ENTITY_ITEM, "item-2", "item_created"))

    history = ledger_service.list_entity_history(USER, ENTITY_ITEM, "item-1")
    assert [e["event_type"] for e in history] == [
        "item_created", "item_adjusted", "item_consumed"
    ]
    # entity_sk / event_sk are populated and time-ordered (oldest first).
    assert all(h["entity_sk"].startswith("item#item-1#") for h in history)


def test_payload_decimals_round_trip(ledger_service):
    from models import LedgerEvent

    ledger_service.append(
        LedgerEvent.create(
            USER, ENTITY_ITEM, "item-9", "item_consumed",
            payload={"consumed": {"value": 2.5, "unit": "kg"}},
        )
    )
    hist = ledger_service.list_entity_history(USER, ENTITY_ITEM, "item-9")
    # Floats survive the Decimal storage round-trip as floats.
    assert hist[0]["payload"]["consumed"]["value"] == 2.5


# --- Item lifecycle emits ----------------------------------------------------

def test_create_emits_item_created(services):
    item_service, _, _ = services
    item = item_service.create_item(USER, "Milk", "fridge")
    assert _event_types(item_service.ledger_service, ENTITY_ITEM, item["item_id"]) == [
        EVENT_ITEM_CREATED
    ]


def test_dimensions_edit_emits_adjusted(services):
    item_service, _, _ = services
    item = item_service.create_item(
        USER, "Flour", "pantry",
        dimensions=[{"dimension_type": "weight", "value": 1000, "unit": "g"}],
    )
    item_service.update_item(
        USER, item["item_id"],
        {"dimensions": [{"dimension_type": "weight", "value": 800, "unit": "g"}]},
    )
    assert _event_types(item_service.ledger_service, ENTITY_ITEM, item["item_id"]) == [
        EVENT_ITEM_CREATED, EVENT_ITEM_ADJUSTED
    ]


def test_delete_is_soft_and_emits_removed(services):
    item_service, _, _ = services
    item = item_service.create_item(USER, "Eggs", "fridge")
    iid = item["item_id"]

    assert item_service.delete_item(USER, iid) is True
    # Soft delete: gone from reads (404), excluded from lists.
    assert item_service.get_item(USER, iid) is None
    assert all(i["item_id"] != iid for i in item_service.list_all_items(USER))
    # Recorded as a removal, NOT a consumption.
    assert _event_types(item_service.ledger_service, ENTITY_ITEM, iid) == [
        EVENT_ITEM_CREATED, EVENT_ITEM_REMOVED
    ]


# --- Consume -----------------------------------------------------------------

def test_consume_partial_decrements_and_emits_consumed(services):
    item_service, _, _ = services
    item = item_service.create_item(
        USER, "Rice", "pantry",
        dimensions=[{"dimension_type": "weight", "value": 2, "unit": "kg"}],
    )
    iid = item["item_id"]

    result = item_service.consume_item(
        USER, iid, {"dimension_type": "weight", "value": 500, "unit": "g"}
    )
    # 2 kg - 500 g = 1.5 kg remaining, item still active.
    assert result["dimensions"][0]["value"] == 1.5
    assert item_service.get_item(USER, iid) is not None
    assert _event_types(item_service.ledger_service, ENTITY_ITEM, iid) == [
        EVENT_ITEM_CREATED, EVENT_ITEM_CONSUMED
    ]


def test_consume_to_zero_depletes_and_soft_deletes(services):
    item_service, _, _ = services
    item = item_service.create_item(
        USER, "Butter", "fridge",
        dimensions=[{"dimension_type": "weight", "value": 250, "unit": "g"}],
    )
    iid = item["item_id"]

    result = item_service.consume_item(
        USER, iid, {"dimension_type": "weight", "value": 250, "unit": "g"}
    )
    assert result["depleted"] is True
    assert item_service.get_item(USER, iid) is None  # depleted → soft-deleted
    events = item_service.ledger_service.list_entity_history(USER, ENTITY_ITEM, iid)
    assert events[-1]["event_type"] == EVENT_ITEM_CONSUMED
    assert events[-1]["payload"]["depleted"] is True
    # Depletion is a consumption, not a removal.
    assert EVENT_ITEM_REMOVED not in [e["event_type"] for e in events]


def test_consume_all_depletes(services):
    item_service, _, _ = services
    item = item_service.create_item(USER, "Snack", "pantry")
    result = item_service.consume_item(USER, item["item_id"], None)
    assert result["depleted"] is True


def test_consume_missing_item_returns_none(services):
    item_service, _, _ = services
    assert item_service.consume_item(USER, "nope", None) is None


def test_consume_wrong_dimension_raises(services):
    item_service, _, _ = services
    item = item_service.create_item(
        USER, "Water", "pantry",
        dimensions=[{"dimension_type": "volume", "value": 1, "unit": "l"}],
    )
    import pytest
    with pytest.raises(ValueError):
        item_service.consume_item(
            USER, item["item_id"], {"dimension_type": "weight", "value": 1, "unit": "kg"}
        )


# --- Task completion history -------------------------------------------------

def test_complete_and_uncomplete_emit_events(task_service):
    task = task_service.create_task(USER, "Water plants")
    tid = task["task_id"]

    task_service.complete_task(USER, tid)
    task_service.uncomplete_task(USER, tid)

    assert _event_types(task_service.ledger_service, ENTITY_TASK, tid) == [
        EVENT_TASK_COMPLETED, EVENT_TASK_UNCOMPLETED
    ]


def test_decision_recorded_in_completion_event(task_service):
    task = task_service.create_task(USER, "Order feed?", answer_mode="yesno")
    task_service.complete_task(USER, task["task_id"], decision="yes")
    hist = task_service.ledger_service.list_entity_history(USER, ENTITY_TASK, task["task_id"])
    assert hist[0]["event_type"] == EVENT_TASK_COMPLETED
    assert hist[0]["payload"]["decision"] == "yes"


def test_task_delete_is_soft(task_service):
    task = task_service.create_task(USER, "Temp task")
    tid = task["task_id"]
    assert task_service.delete_task(USER, tid) is True
    assert task_service.get_task(USER, tid) is None
    # No ledger event for task deletion (ledger tracks completions, not CRUD).
    assert _event_types(task_service.ledger_service, ENTITY_TASK, tid) == []
