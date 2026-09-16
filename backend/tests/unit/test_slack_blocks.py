"""Unit tests for the Slack Block Kit renderer (slack_blocks)."""

from slack_blocks import render_message_blocks, MAX_BLOCKS, LIST_ITEMS_MAX

APP = "https://app.example.com"


def test_header_always_first():
    blocks = render_message_blocks("Daily Digest", [])
    assert blocks[0]["type"] == "header"
    assert blocks[0]["text"]["text"] == "Daily Digest"


def test_custom_message_renders_text():
    blocks = render_message_blocks("T", [
        {"type": "custom_message", "heading": "Note", "content": {"text": "good morning"}},
    ])
    flat = str(blocks)
    assert "*Note*" in flat
    assert "good morning" in flat


def test_custom_message_escapes_mrkdwn():
    blocks = render_message_blocks("T", [
        {"type": "custom_message", "content": {"text": "a < b & c > d"}},
    ])
    flat = str(blocks)
    assert "&lt;" in flat and "&amp;" in flat and "&gt;" in flat


def test_task_section_links_and_deadline():
    blocks = render_message_blocks("T", [
        {"type": "task_query", "heading": "Chores", "content": {
            "items": [
                {"name": "Feed goats", "task_id": "t1", "current_due": "2026-09-20",
                 "computed_status": "overdue"},
            ],
            "count": 1,
        }},
    ], app_base_url=APP)
    flat = str(blocks)
    # Deep link back to the task.
    assert "https://app.example.com/tasks/t1|Feed goats" in flat
    # Slack native date token for the deadline (viewer-localized).
    assert "<!date^" in flat and "due" in flat
    # Overdue emoji present.
    assert "⚠️" in flat
    # Count rendered as a muted context block.
    assert any(b["type"] == "context" and "1 task" in str(b) for b in blocks)


def test_task_without_app_url_shows_plain_name():
    blocks = render_message_blocks("T", [
        {"type": "task_query", "content": {"items": [{"name": "Solo", "task_id": "t1"}], "count": 1}},
    ])
    flat = str(blocks)
    assert "Solo" in flat
    assert "/tasks/t1|" not in flat  # no link without a base URL


def test_item_section_links_and_use_by():
    blocks = render_message_blocks("T", [
        {"type": "item_query", "heading": "Low", "content": {
            "items": [{"name": "Milk", "item_id": "i1", "use_by_date": "2026-09-18"}], "count": 1,
        }},
    ], app_base_url=APP)
    flat = str(blocks)
    assert "/items/i1|Milk" in flat
    assert "use by" in flat and "<!date^" in flat


def test_empty_query_section_renders_context_none():
    blocks = render_message_blocks("T", [
        {"type": "item_query", "heading": "Low stock", "content": {"items": [], "count": 0}},
    ])
    assert any(b["type"] == "context" and "No items" in str(b) for b in blocks)


def test_long_list_capped_with_showing_first_note():
    items = [{"name": f"item {i}", "item_id": str(i)} for i in range(LIST_ITEMS_MAX + 5)]
    blocks = render_message_blocks("T", [
        {"type": "item_query", "heading": "All", "content": {"items": items, "count": len(items)}},
    ])
    assert "showing first" in str(blocks)


def test_sections_separated_by_dividers():
    blocks = render_message_blocks("T", [
        {"type": "custom_message", "content": {"text": "one"}},
        {"type": "custom_message", "content": {"text": "two"}},
    ])
    assert sum(1 for b in blocks if b["type"] == "divider") == 2


def test_block_count_capped_at_slack_limit():
    many = [
        {"type": "custom_message", "heading": f"H{i}", "content": {"text": f"body {i}"}}
        for i in range(60)
    ]
    blocks = render_message_blocks("T", many)
    assert len(blocks) <= MAX_BLOCKS
    assert "truncated" in str(blocks[-1]).lower()


def test_unknown_section_type_is_skipped_gracefully():
    blocks = render_message_blocks("T", [
        {"type": "mystery", "heading": "Odd", "content": {"foo": "bar"}},
    ])
    assert "*Odd*" in str(blocks)
