import json
import logging
from typing import Any

from src.auth.schemas import SessionContext
from src.config import settings
from src.history.client import HistoryClientError, history_client
from src.history.mapper import to_engine_messages
from src.history.schemas import HistoryMessageCreateRequest
from theseus_engine.core.context_compressor import maybe_compress

logger = logging.getLogger(__name__)


async def load_history_messages(
    session: SessionContext,
    chat_session_id: int,
) -> list[Any]:
    try:
        records = await history_client.fetch_messages(session, chat_session_id)
    except HistoryClientError as exc:
        logger.warning(
            "History load failed for project=%s session=%s: %s",
            session.project_id,
            chat_session_id,
            exc,
        )
        return []

    messages = to_engine_messages(records)
    compressed_messages, did_compress = await maybe_compress(messages)
    if did_compress:
        logger.info(
            "Compressed history for project=%s session=%s from %d to %d messages",
            session.project_id,
            chat_session_id,
            len(messages),
            len(compressed_messages),
        )
    return compressed_messages


async def persist_user_message(
    session: SessionContext,
    chat_session_id: int,
    content: str,
) -> bool:
    request = HistoryMessageCreateRequest(
        project_id=session.project_id,
        chat_session_id=chat_session_id,
        sender_type="USER",
        content=content,
        message_type="CHAT",
        content_type="TEXT",
    )

    try:
        await history_client.save_message(session, request)
        return True
    except HistoryClientError as exc:
        logger.warning(
            "User history save failed for project=%s session=%s: %s",
            session.project_id,
            chat_session_id,
            exc,
        )
        return False


async def persist_assistant_message(
    session: SessionContext,
    chat_session_id: int,
    content: str,
) -> bool:
    if not content.strip():
        return True

    request = HistoryMessageCreateRequest(
        project_id=session.project_id,
        chat_session_id=chat_session_id,
        sender_type="ASSISTANT",
        content=content,
        message_type="CHAT",
        content_type="TEXT",
    )

    try:
        await history_client.save_message(session, request)
        return True
    except HistoryClientError as exc:
        logger.warning(
            "Assistant history save failed for project=%s session=%s: %s",
            session.project_id,
            chat_session_id,
            exc,
        )
        return False


async def persist_tool_call_message(
    session: SessionContext,
    chat_session_id: int,
    *,
    tool_name: str,
    tool_input: dict[str, Any] | None,
    tool_use_id: str | None = None,
) -> bool:
    payload = {
        "noticeType": "TOOL_EXECUTION_STARTED",
        "toolName": tool_name,
        "toolUseId": tool_use_id,
        "toolInput": tool_input or {},
        "status": "started",
    }
    return await _persist_tool_history_message(
        session,
        chat_session_id,
        payload=payload,
    )


async def persist_tool_result_message(
    session: SessionContext,
    chat_session_id: int,
    *,
    tool_name: str,
    output: str,
    is_error: bool,
    tool_use_id: str | None = None,
    tool_input: dict[str, Any] | None = None,
    metadata: dict[str, Any] | None = None,
) -> bool:
    payload = {
        "noticeType": "TOOL_EXECUTION_COMPLETED",
        "toolName": tool_name,
        "toolUseId": tool_use_id,
        "toolInput": tool_input or {},
        "output": output,
        "isError": is_error,
        "status": "completed",
        "metadata": metadata or {},
    }
    return await _persist_tool_history_message(
        session,
        chat_session_id,
        payload=payload,
    )


async def _persist_tool_history_message(
    session: SessionContext,
    chat_session_id: int,
    *,
    payload: dict[str, Any],
) -> bool:
    request = HistoryMessageCreateRequest(
        project_id=session.project_id,
        chat_session_id=chat_session_id,
        sender_type="SYSTEM",
        content=json.dumps(payload, ensure_ascii=False, default=str),
        message_type="SYSTEM_NOTICE",
        content_type="JSON",
    )

    try:
        await history_client.save_message(session, request)
        return True
    except HistoryClientError as exc:
        logger.warning(
            "Tool history save failed for project=%s session=%s type=%s tool=%s: %s",
            session.project_id,
            chat_session_id,
            payload.get("noticeType"),
            payload.get("toolName"),
            exc,
        )
        return False
