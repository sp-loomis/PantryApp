"""Render a generated report/message into Slack Block Kit blocks.

Consumes the SAME rendered message sections the in-app log stores —
``{ type, heading, content }`` as produced by
``report_sections.render_section`` — and maps them to Slack blocks, so Slack
delivery and the message log show the same snapshot. This is the "Slack block
renderer" anticipated in ``report_sections`` docstring.

The only entry point is ``render_message_blocks(title, sections)``.
"""

from typing import Any, Dict, List

# Slack hard limits: a message carries at most 50 blocks, header plain_text is
# 150 chars, a section mrkdwn field is 3000 chars. We stay well under these and
# truncate defensively rather than letting Slack reject the whole post.
MAX_BLOCKS = 50
HEADER_MAX = 150
SECTION_TEXT_MAX = 3000
# Cap how many item/task names we list per query section (keeps blocks readable
# and the message under the block limit).
LIST_ITEMS_MAX = 20


def _truncate(text: str, limit: int) -> str:
    text = text or ""
    return text if len(text) <= limit else text[: limit - 1] + "…"


def _header(title: str) -> Dict[str, Any]:
    return {
        "type": "header",
        "text": {"type": "plain_text", "text": _truncate(title or "Report", HEADER_MAX)},
    }


def _mrkdwn_section(text: str) -> Dict[str, Any]:
    return {"type": "section", "text": {"type": "mrkdwn", "text": _truncate(text, SECTION_TEXT_MAX)}}


def _content_text(section: Dict[str, Any]) -> str:
    """Turn one rendered section's content into a mrkdwn body string."""
    content = section.get("content") or {}
    section_type = section.get("type")

    if section_type == "custom_message":
        return content.get("text", "")

    if section_type in ("task_query", "item_query"):
        items = content.get("items") or []
        count = content.get("count", len(items))
        if not items:
            return "_None_"
        names = [str(it.get("name", "")).strip() or "(unnamed)" for it in items[:LIST_ITEMS_MAX]]
        lines = "\n".join(f"• {n}" for n in names)
        if count > LIST_ITEMS_MAX:
            lines += f"\n_…and {count - LIST_ITEMS_MAX} more_"
        return f"{lines}\n_{count} total_"

    # Unknown/future section type: best-effort, render nothing extra.
    return ""


def render_message_blocks(title: str, sections: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Render a report title + its rendered sections into Slack blocks.

    Never raises on odd input — unknown section types contribute no body. The
    result is capped at Slack's 50-block limit (with a trailing note when
    sections had to be dropped).
    """
    blocks: List[Dict[str, Any]] = [_header(title)]

    for section in sections or []:
        heading = (section.get("heading") or "").strip()
        body = _content_text(section)
        if heading:
            blocks.append(_mrkdwn_section(f"*{heading}*"))
        if body:
            blocks.append(_mrkdwn_section(body))
        # A section with neither heading nor body contributes nothing.

    if len(blocks) > MAX_BLOCKS:
        # Keep room for a truncation note within the limit.
        blocks = blocks[: MAX_BLOCKS - 1]
        blocks.append(_mrkdwn_section("_Report truncated — open it in the app for the full view._"))

    return blocks
