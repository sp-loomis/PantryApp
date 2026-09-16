"""Unit tests for the Slack Block Kit renderer (slack_blocks)."""

from slack_blocks import render_message_blocks, MAX_BLOCKS, LIST_ITEMS_MAX


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


def test_query_section_lists_names_and_count():
    blocks = render_message_blocks("T", [
        {"type": "task_query", "heading": "Chores", "content": {
            "items": [{"name": "Feed goats"}, {"name": "Water beds"}], "count": 2,
        }},
    ])
    flat = str(blocks)
    assert "Feed goats" in flat and "Water beds" in flat
    assert "2 total" in flat


def test_empty_query_section_renders_none():
    blocks = render_message_blocks("T", [
        {"type": "item_query", "heading": "Low stock", "content": {"items": [], "count": 0}},
    ])
    assert "_None_" in str(blocks)


def test_long_list_is_capped_with_more_note():
    items = [{"name": f"item {i}"} for i in range(LIST_ITEMS_MAX + 5)]
    blocks = render_message_blocks("T", [
        {"type": "item_query", "heading": "All", "content": {"items": items, "count": len(items)}},
    ])
    flat = str(blocks)
    assert "and 5 more" in flat


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
    # Heading still shows; unknown content contributes no body, and no crash.
    assert "*Odd*" in str(blocks)
