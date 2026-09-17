"""Render a generated report/message into Slack Block Kit blocks.

Consumes the SAME rendered message sections the in-app log stores —
``{ type, heading, content }`` as produced by
``report_sections.render_section`` — and maps them to Slack blocks, so Slack
delivery and the message log show the same snapshot. This is the "Slack block
renderer" anticipated in ``report_sections`` docstring.

Task/item entries link back to the web app (when an ``app_base_url`` is given)
and render deadlines with Slack's native date token so each viewer sees them in
their own timezone/locale. The only entry point is ``render_message_blocks``.
"""

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

# Slack hard limits: a message carries at most 50 blocks, header plain_text is
# 150 chars, a section mrkdwn text is 3000 chars, and each field in a section's
# ``fields`` array is 2000 chars with at most 10 fields per block. We stay well
# under these and truncate defensively rather than letting Slack reject the post.
MAX_BLOCKS = 50
HEADER_MAX = 150
SECTION_TEXT_MAX = 3000
FIELD_TEXT_MAX = 2000
# A section's ``fields`` render as a 2-column grid; 10 fields = 5 two-column rows.
FIELDS_PER_BLOCK = 10
# Cap how many item/task names we list per query section (keeps blocks readable
# and the message under the block/char limits).
LIST_ITEMS_MAX = 20

# Task computed_status -> leading emoji. Anything else falls back to a bullet.
STATUS_EMOJI = {
    "overdue": "⚠️",    # warning
    "due_today": "\U0001f4c5",    # calendar
    "due_soon": "\U0001f550",     # clock
    "done": "✅",             # check
}
DEFAULT_BULLET = "•"


def _truncate(text: str, limit: int) -> str:
    text = text or ""
    return text if len(text) <= limit else text[: limit - 1] + "…"


def _escape(text: str) -> str:
    """Escape the three characters Slack mrkdwn treats specially."""
    return (text or "").replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def _slack_date(iso: Optional[str]) -> Optional[str]:
    """Render an ISO date/datetime as a Slack date token (viewer-local).

    Returns ``<!date^<epoch>^{date_short}|<fallback>>`` so Slack localizes it, or
    None when there is no parseable date.
    """
    if not iso:
        return None
    try:
        dt = datetime.fromisoformat(iso)
    except (ValueError, TypeError):
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    epoch = int(dt.timestamp())
    fallback = _escape(iso[:10])
    return f"<!date^{epoch}^{{date_short}}|{fallback}>"


def _header(title: str) -> Dict[str, Any]:
    return {
        "type": "header",
        "text": {"type": "plain_text", "text": _truncate(title or "Report", HEADER_MAX)},
    }


def _section(text: str) -> Dict[str, Any]:
    return {"type": "section", "text": {"type": "mrkdwn", "text": _truncate(text, SECTION_TEXT_MAX)}}


def _field(text: str) -> Dict[str, Any]:
    return {"type": "mrkdwn", "text": _truncate(text, FIELD_TEXT_MAX)}


def _fields_section(fields: List[Dict[str, Any]]) -> Dict[str, Any]:
    return {"type": "section", "fields": fields}


def _context(text: str) -> Dict[str, Any]:
    return {"type": "context", "elements": [{"type": "mrkdwn", "text": _truncate(text, SECTION_TEXT_MAX)}]}


def _divider() -> Dict[str, Any]:
    return {"type": "divider"}


def _link(name: str, path: Optional[str], app_base_url: str) -> str:
    """A mrkdwn link back to the app, or the escaped name when no URL is set."""
    label = _escape(str(name).strip() or "(unnamed)")
    if app_base_url and path:
        return f"<{app_base_url}{path}|{label}>"
    return label


def _entry_fields(section: Dict[str, Any], app_base_url: str) -> List[Dict[str, Any]]:
    """Two mrkdwn fields per task/item — a name column (emoji + link) and a date
    column — laid out by Slack as a 2-column grid.

    The em dash marks a missing deadline so both columns stay aligned.
    """
    content = section.get("content") or {}
    section_type = section.get("type")
    items = content.get("items") or []
    fields: List[Dict[str, Any]] = []

    for it in items[:LIST_ITEMS_MAX]:
        if section_type == "task_query":
            emoji = STATUS_EMOJI.get(it.get("computed_status"), DEFAULT_BULLET)
            link = _link(it.get("name"), f"/tasks/{it.get('task_id')}", app_base_url)
            when = _slack_date(it.get("current_due"))
            date_text = f"due {when}" if when else "—"
        else:  # item_query
            emoji = DEFAULT_BULLET
            link = _link(it.get("name"), f"/items/{it.get('item_id')}", app_base_url)
            when = _slack_date(it.get("use_by_date"))
            date_text = f"use by {when}" if when else "—"
        fields.append(_field(f"{emoji} {link}"))
        fields.append(_field(date_text))

    return fields


def _render_section_blocks(section: Dict[str, Any], app_base_url: str) -> List[Dict[str, Any]]:
    """Render one report section into its (divider-led) block group."""
    blocks: List[Dict[str, Any]] = [_divider()]
    heading = (section.get("heading") or "").strip()
    if heading:
        blocks.append(_section(f"*{_escape(heading)}*"))

    section_type = section.get("type")
    content = section.get("content") or {}

    if section_type == "custom_message":
        text = content.get("text", "")
        if text:
            blocks.append(_section(_escape(text)))
        return blocks

    if section_type in ("task_query", "item_query"):
        count = content.get("count", len(content.get("items") or []))
        noun = "task" if section_type == "task_query" else "item"
        if not (content.get("items") or []):
            blocks.append(_context(f"_No {noun}s_"))
            return blocks
        fields = _entry_fields(section, app_base_url)
        # A section block holds at most 10 fields; split longer lists across
        # consecutive section blocks so the 2-column grid keeps flowing.
        for start in range(0, len(fields), FIELDS_PER_BLOCK):
            blocks.append(_fields_section(fields[start : start + FIELDS_PER_BLOCK]))
        more = count - LIST_ITEMS_MAX
        summary = f"{count} {noun}{'' if count == 1 else 's'}"
        if more > 0:
            summary += f" · showing first {LIST_ITEMS_MAX}"
        blocks.append(_context(summary))
        return blocks

    # Unknown/future section type: heading only (best-effort, no crash).
    return blocks


def render_message_blocks(
    title: str, sections: List[Dict[str, Any]], app_base_url: str = ""
) -> List[Dict[str, Any]]:
    """Render a report title + its rendered sections into Slack blocks.

    ``app_base_url`` (e.g. https://app.example.com) makes task/item entries link
    back to the app; empty renders plain names. Never raises on odd input; the
    result is capped at Slack's 50-block limit with a trailing note when
    sections had to be dropped.
    """
    app_base_url = (app_base_url or "").rstrip("/")
    blocks: List[Dict[str, Any]] = [_header(title)]

    for section in sections or []:
        blocks.extend(_render_section_blocks(section, app_base_url))

    if len(blocks) > MAX_BLOCKS:
        blocks = blocks[: MAX_BLOCKS - 1]
        blocks.append(_context("_Report truncated — open it in the app for the full view._"))

    return blocks
