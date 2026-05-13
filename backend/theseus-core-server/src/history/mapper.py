import json
import logging
from typing import Any

from src.history.schemas import HistoryMessageRecord

logger = logging.getLogger(__name__)


def _normalize_role(sender_type: str) -> str | None:
    normalized = sender_type.upper()
    if normalized == "USER":
        return "user"
    if normalized == "ASSISTANT":
        return "assistant"
    return None


def _summarize_feedback_json(content: str) -> str:
    try:
        payload = json.loads(content)
    except ValueError:
        return content

    feedback_items = payload.get("feedbackItems", [])
    if not isinstance(feedback_items, list) or not feedback_items:
        return "Requested PLAN draft feedback changes."

    lines = [f"Requested {len(feedback_items)} PLAN draft revisions:"]
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
        from theseus_engine.models.messages import ConversationMessage, TextBlock
    except ImportError:
        logger.warning(
            "Theseus message types unavailable while mapping history; "
            "falling back to dict messages."
        )
        return [
            {
                "role": role,
                "content": _render_record_content(record),
            }
            for record in records
            for role in [_normalize_role(record.sender_type)]
            if role is not None
            if _render_record_content(record).strip()
        ]

    messages: list[Any] = []
    for record in records:
        role = _normalize_role(record.sender_type)
        if role is None:
            logger.debug(
                "Skipping non-conversational history senderType=%s messageType=%s",
                record.sender_type,
                record.message_type,
            )
            continue
        rendered_content = _render_record_content(record)
        if not rendered_content.strip():
            continue
        messages.append(
            ConversationMessage(
                role=role,
                content=[TextBlock(text=rendered_content)],
            )
        )
    return messages
