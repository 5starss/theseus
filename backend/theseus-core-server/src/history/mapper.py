import json
import logging
from typing import Any

from src.history.schemas import HistoryMessageRecord

logger = logging.getLogger(__name__)

_TOOL_BUILD_FAILED_NOTICE_PREFIX = "Tool build에 실패했습니다"
_TOOL_PLAN_FAILED_NOTICE_PREFIX = "Tool PLAN 생성에 실패했습니다"
_FAILURE_CODE_MARKER = "code="
_FAILURE_MESSAGE_MARKER = ", message="
_FAILURE_ALTERNATIVES_MARKER = "가능한 대안:"
_FAILURE_LAST_ERROR_MARKER = "마지막 오류:"
_FAILURE_CONTEXT_LIMIT = 700
_TOOL_HISTORY_CONTEXT_LIMIT = 1000
_TOOL_CALL_MESSAGE_TYPES = {
    "TOOL_CALL",
    "TOOL_USE",
    "TOOL_EXECUTION_STARTED",
}
_TOOL_RESULT_MESSAGE_TYPES = {
    "TOOL_RESULT",
    "TOOL_EXECUTION_RESULT",
    "TOOL_EXECUTION_COMPLETED",
}
_TOOL_NOTICE_PREFIXES = (
    "Tool execution:",
    "Tool result:",
    "Tool completed:",
    "도구 실행:",
    "툴 실행:",
    "툴 결과:",
)


def _normalize_role(sender_type: str) -> str | None:
    normalized = sender_type.upper()
    if normalized == "USER":
        return "user"
    if normalized == "ASSISTANT":
        return "assistant"
    return None


def _normalize_role_for_record(record: HistoryMessageRecord) -> str | None:
    if _project_failure_notice(record) is not None:
        return "assistant"
    if _project_tool_history_notice(record) is not None:
        return "assistant"
    return _normalize_role(record.sender_type)


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


def _project_failure_notice(record: HistoryMessageRecord) -> str | None:
    if (
        record.sender_type.upper() != "SYSTEM"
        or (record.message_type or "").upper() != "SYSTEM_NOTICE"
        or (record.content_type or "TEXT").upper() != "TEXT"
    ):
        return None

    content = record.content or ""
    if content.startswith(_TOOL_BUILD_FAILED_NOTICE_PREFIX):
        return _summarize_failure_notice("Tool build", content)
    if content.startswith(_TOOL_PLAN_FAILED_NOTICE_PREFIX):
        return _summarize_failure_notice("Tool PLAN", content)
    return None


def _project_tool_history_notice(record: HistoryMessageRecord) -> str | None:
    message_type = (record.message_type or "").upper()
    content_type = (record.content_type or "TEXT").upper()
    content = record.content or ""

    if message_type in _TOOL_CALL_MESSAGE_TYPES:
        return _summarize_tool_history_record("이전 도구 호출", content, content_type)
    if message_type in _TOOL_RESULT_MESSAGE_TYPES:
        return _summarize_tool_history_record("이전 도구 실행 결과", content, content_type)
    if (
        record.sender_type.upper() == "SYSTEM"
        and message_type == "SYSTEM_NOTICE"
        and any(content.startswith(prefix) for prefix in _TOOL_NOTICE_PREFIXES)
    ):
        return _limit_tool_history_context(content)
    return None


def _summarize_tool_history_record(prefix: str, content: str, content_type: str) -> str:
    payload: Any = None
    if content_type == "JSON":
        try:
            payload = json.loads(content)
        except ValueError:
            payload = None

    if isinstance(payload, dict):
        tool_name = (
            payload.get("toolName")
            or payload.get("tool_name")
            or payload.get("name")
            or payload.get("tool")
            or "unknown"
        )
        is_error = payload.get("isError", payload.get("is_error"))
        status = payload.get("status")
        output = (
            payload.get("output")
            or payload.get("toolOutput")
            or payload.get("tool_output")
            or payload.get("result")
            or payload.get("content")
            or ""
        )
        input_payload = (
            payload.get("input")
            or payload.get("toolInput")
            or payload.get("tool_input")
            or {}
        )
        parts = [f"tool={tool_name}"]
        if status is not None:
            parts.append(f"status={status}")
        if is_error is not None:
            parts.append(f"is_error={is_error}")
        if input_payload:
            parts.append(
                "input="
                + _limit_tool_history_context(
                    json.dumps(input_payload, ensure_ascii=False)
                )
            )
        if output:
            parts.append(f"output={_limit_tool_history_context(str(output))}")
        return f"{prefix}: {', '.join(parts)}"

    return f"{prefix}: {_limit_tool_history_context(content)}"


def _summarize_failure_notice(failure_kind: str, content: str) -> str:
    code = _extract_failure_code(content)
    message = _extract_failure_message(content)
    alternatives = _extract_marked_section(
        message,
        _FAILURE_ALTERNATIVES_MARKER,
    )
    reason = _trim_marked_section(message, _FAILURE_ALTERNATIVES_MARKER)
    reason = _trim_marked_section(reason, _FAILURE_LAST_ERROR_MARKER)
    if not reason:
        reason = content

    details: list[str] = []
    if code:
        details.append(f"code={code}")
    if reason:
        details.append(f"원인={_limit_failure_context(reason)}")
    if alternatives:
        details.append(f"가능한 대안={_limit_failure_context(alternatives)}")
    if details:
        return f"이전 {failure_kind} 실패: {', '.join(details)}"
    return f"이전 {failure_kind} 실패:"


def _extract_failure_code(content: str) -> str:
    code_start = content.find(_FAILURE_CODE_MARKER)
    if code_start < 0:
        return ""

    value_start = code_start + len(_FAILURE_CODE_MARKER)
    value_end = content.find(_FAILURE_MESSAGE_MARKER, value_start)
    if value_end < 0:
        value_end = len(content)
    return content[value_start:value_end].strip()


def _extract_failure_message(content: str) -> str:
    marker_index = content.find(_FAILURE_MESSAGE_MARKER)
    if marker_index < 0:
        return content.strip()
    return content[marker_index + len(_FAILURE_MESSAGE_MARKER) :].strip()


def _extract_marked_section(content: str, marker: str) -> str:
    marker_index = content.find(marker)
    if marker_index < 0:
        return ""
    section = content[marker_index + len(marker) :].strip()
    return _trim_marked_section(section, _FAILURE_LAST_ERROR_MARKER)


def _trim_marked_section(content: str, marker: str) -> str:
    marker_index = content.find(marker)
    if marker_index < 0:
        return content.strip()
    return content[:marker_index].strip()


def _limit_failure_context(content: str) -> str:
    if len(content) <= _FAILURE_CONTEXT_LIMIT:
        return content
    return f"{content[:_FAILURE_CONTEXT_LIMIT].strip()}..."


def _limit_tool_history_context(content: str) -> str:
    if len(content) <= _TOOL_HISTORY_CONTEXT_LIMIT:
        return content
    return f"{content[:_TOOL_HISTORY_CONTEXT_LIMIT].strip()}..."


def _render_record_content(record: HistoryMessageRecord) -> str:
    projected_failure_notice = _project_failure_notice(record)
    if projected_failure_notice is not None:
        return projected_failure_notice
    projected_tool_history = _project_tool_history_notice(record)
    if projected_tool_history is not None:
        return projected_tool_history

    message_type = (record.message_type or "CHAT").upper()
    content_type = (record.content_type or "TEXT").upper()

    if message_type == "TOOL_FEEDBACK" and content_type == "JSON":
        return _summarize_feedback_json(record.content)

    if message_type == "TOOL_APPROVAL_REQUEST":
        return "Requested tool approval."

    return record.content


def _to_dict_messages(records: list[HistoryMessageRecord]) -> list[dict[str, str]]:
    messages: list[dict[str, str]] = []
    for record in records:
        role = _normalize_role_for_record(record)
        if role is None:
            continue
        rendered_content = _render_record_content(record)
        if not rendered_content.strip():
            continue
        messages.append(
            {
                "role": role,
                "content": rendered_content,
            }
        )
    return messages


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
        return _to_dict_messages(records)

    messages: list[Any] = []
    for record in records:
        role = _normalize_role_for_record(record)
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
