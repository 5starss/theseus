import json
import logging
from typing import Any

from src.history.schemas import HistoryMessageRecord

logger = logging.getLogger(__name__)


def _normalize_role(sender_type: str) -> str:
    normalized = sender_type.upper()
    if normalized == "USER":
        return "user"
    if normalized == "ASSISTANT":
        return "assistant"
    return "system"


def _summarize_feedback_json(content: str) -> str:
    try:
        payload = json.loads(content)
    except ValueError:
        return content

    feedback_items = payload.get("feedbackItems", [])
    if not isinstance(feedback_items, list) or not feedback_items:
        return "Requested tool-plan feedback changes."

    lines = [f"Requested {len(feedback_items)} tool-plan revisions:"]
    for item in feedback_items:
        if not isinstance(item, dict):
            continue
        block_id = item.get("blockId", "unknown-block")
        comment = item.get("comment", "")
        lines.append(f"- {block_id}: {comment}")
    return "\n".join(lines)


def _render_record_content(record: HistoryMessageRecord) -> str:
    message_type = (record.message_type or "CHAT").upper()
    content_type = (record.content_type or "TEXT").upper()

    if message_type == "TOOL_FEEDBACK" and content_type == "JSON":
        return _summarize_feedback_json(record.content)

    if message_type == "TOOL_APPROVAL_REQUEST":
        return "Requested tool approval."

    return record.content


def to_engine_messages(records: list[HistoryMessageRecord]) -> list[Any]:
    if not records:
        return []

    try:
        from openharness.engine.messages import ConversationMessage, TextBlock
    except ImportError:
        logger.warning(
            "OpenHarness message types unavailable while mapping history; "
            "falling back to dict messages."
        )
        return [
            {
                "role": _normalize_role(record.sender_type),
                "content": _render_record_content(record),
            }
            for record in records
            if _render_record_content(record).strip()
        ]

    messages: list[Any] = []
    for record in records:
        rendered_content = _render_record_content(record)
        if not rendered_content.strip():
            continue
        messages.append(
            ConversationMessage(
                role=_normalize_role(record.sender_type),
                content=[TextBlock(text=rendered_content)],
            )
        )
    return messages
