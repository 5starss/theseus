"""Theseus Anthropic API 클라이언트 — OpenHarness 완전 독립.

OH AnthropicApiClient를 Theseus-native로 재구현합니다.
OAuth/Claude Code 전용 기능은 제거하고, 표준 API 키 인증만 지원합니다.
"""

from __future__ import annotations

import asyncio
import json
import logging
from typing import Any, AsyncIterator
from uuid import uuid4

from anthropic import APIError, APIStatusError, AsyncAnthropic

from theseus_engine.models.messages import (
    ConversationMessage,
    TextBlock,
    ToolUseBlock,
    assistant_message_from_api,
)
from theseus_engine.wrappers.llm_clients.api_types import (
    ApiMessageCompleteEvent,
    ApiMessageRequest,
    ApiRetryEvent,
    ApiStreamEvent,
    ApiTextDeltaEvent,
    AuthenticationFailure,
    RateLimitFailure,
    RequestFailure,
    TheseusApiError,
    UsageSnapshot,
)

log = logging.getLogger(__name__)

MAX_RETRIES = 3
BASE_DELAY = 1.0
MAX_DELAY = 30.0
RETRYABLE_STATUS_CODES = {429, 500, 502, 503, 529}


def _is_retryable(exc: Exception) -> bool:
    if isinstance(exc, APIStatusError):
        return exc.status_code in RETRYABLE_STATUS_CODES
    if isinstance(exc, APIError):
        return True
    if isinstance(exc, (ConnectionError, TimeoutError, OSError)):
        return True
    return False


def _get_retry_delay(attempt: int, exc: Exception | None = None) -> float:
    import random
    if isinstance(exc, APIStatusError):
        headers = getattr(exc, "headers", {})
        if hasattr(headers, "get"):
            val = headers.get("retry-after")
            if val:
                try:
                    return min(float(val), MAX_DELAY)
                except (ValueError, TypeError):
                    pass
    delay = min(BASE_DELAY * (2 ** attempt), MAX_DELAY)
    return delay + random.uniform(0, delay * 0.25)


def _translate_api_error(exc: APIError) -> TheseusApiError:
    name = exc.__class__.__name__
    if name in {"AuthenticationError", "PermissionDeniedError"}:
        return AuthenticationFailure(str(exc))
    if name == "RateLimitError":
        return RateLimitFailure(str(exc))
    return RequestFailure(str(exc))


class TheseusAnthropicClient:
    """Thin wrapper around the Anthropic async SDK with retry logic.

    표준 API 키 인증만 지원합니다. OAuth/Claude Code 전용 기능은 제외됩니다.
    """

    def __init__(
        self,
        api_key: str | None = None,
        *,
        base_url: str | None = None,
    ) -> None:
        kwargs: dict[str, Any] = {}
        if api_key:
            kwargs["api_key"] = api_key
        if base_url:
            kwargs["base_url"] = base_url
        self._client = AsyncAnthropic(**kwargs)

    async def stream_message(
        self, request: ApiMessageRequest
    ) -> AsyncIterator[ApiStreamEvent]:
        """Yield text deltas and the final assistant message with retry."""
        last_error: Exception | None = None

        for attempt in range(MAX_RETRIES + 1):
            try:
                async for event in self._stream_once(request):
                    yield event
                return
            except TheseusApiError:
                raise
            except Exception as exc:
                last_error = exc
                if attempt >= MAX_RETRIES or not _is_retryable(exc):
                    if isinstance(exc, APIError):
                        raise _translate_api_error(exc) from exc
                    raise RequestFailure(str(exc)) from exc

                delay = _get_retry_delay(attempt, exc)
                status = getattr(exc, "status_code", "?")
                log.warning(
                    "Anthropic API failed (attempt %d/%d, status=%s), "
                    "retrying in %.1fs: %s",
                    attempt + 1, MAX_RETRIES + 1, status, delay, exc,
                )
                yield ApiRetryEvent(
                    message=str(exc),
                    attempt=attempt + 1,
                    max_attempts=MAX_RETRIES + 1,
                    delay_seconds=delay,
                )
                await asyncio.sleep(delay)

        if last_error is not None:
            if isinstance(last_error, APIError):
                raise _translate_api_error(last_error) from last_error
            raise RequestFailure(str(last_error)) from last_error
        # 이론상 도달 불가 — 루프가 return 없이 완료된 경우 방어
        raise RequestFailure("Exhausted retries without result or error.")

    async def _stream_once(
        self, request: ApiMessageRequest
    ) -> AsyncIterator[ApiStreamEvent]:
        params: dict[str, Any] = {
            "model": request.model,
            "messages": [msg.to_api_param() for msg in request.messages],
            "max_tokens": request.max_tokens,
        }
        if request.system_prompt:
            params["system"] = request.system_prompt
        if request.tools:
            params["tools"] = request.tools

        try:
            async with self._client.messages.stream(**params) as stream:
                async for event in stream:
                    if getattr(event, "type", None) != "content_block_delta":
                        continue
                    delta = getattr(event, "delta", None)
                    if getattr(delta, "type", None) != "text_delta":
                        continue
                    text = getattr(delta, "text", "")
                    if text:
                        yield ApiTextDeltaEvent(text=text)
                final_message = await stream.get_final_message()
        except APIError as exc:
            if isinstance(exc, APIStatusError) and exc.status_code in RETRYABLE_STATUS_CODES:
                raise
            raise _translate_api_error(exc) from exc

        usage = getattr(final_message, "usage", None)
        yield ApiMessageCompleteEvent(
            message=assistant_message_from_api(final_message),
            usage=UsageSnapshot(
                input_tokens=int(getattr(usage, "input_tokens", 0) or 0),
                output_tokens=int(getattr(usage, "output_tokens", 0) or 0),
            ),
            stop_reason=getattr(final_message, "stop_reason", None),
        )
