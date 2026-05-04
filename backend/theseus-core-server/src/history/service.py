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
    try:
        project_id = int(session.project_id)
    except ValueError:
        logger.warning(
            "User history save skipped because project_id is not numeric: %s",
            session.project_id,
        )
        return settings.AUTH_MODE == "mock"

    request = HistoryMessageCreateRequest(
        project_id=project_id,
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

    try:
        project_id = int(session.project_id)
    except ValueError:
        logger.warning(
            "Assistant history save skipped because project_id is not numeric: %s",
            session.project_id,
        )
        return settings.AUTH_MODE == "mock"

    request = HistoryMessageCreateRequest(
        project_id=project_id,
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
