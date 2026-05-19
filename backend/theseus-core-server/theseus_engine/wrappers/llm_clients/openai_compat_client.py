"""Theseus OpenAI-compatible 클라이언트.

OpenAI-compatible streaming/client 변환을 Theseus-native로 구현합니다.
DashScope, Gemini(OpenAI 호환), DeepSeek, Ollama, vLLM, OpenAI 등
OpenAI Chat Completions 포맷을 지원하는 모든 제공자에 사용합니다.
"""

from __future__ import annotations

import asyncio
import json
import logging
import re
from typing import Any, AsyncIterator
from urllib.parse import urlsplit, urlunsplit

from openai import AsyncOpenAI

from theseus_engine.models.messages import (
    ContentBlock,
    ConversationMessage,
    ImageBlock,
    TextBlock,
    ToolResultBlock,
    ToolUseBlock,
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
from theseus_engine.wrappers.llm_clients.debug_dump import (
    dump_debug_payload,
    summarize_openai_params,
)

log = logging.getLogger(__name__)

MAX_RETRIES = 3
BASE_DELAY = 1.0
MAX_DELAY = 30.0
_MAX_COMPLETION_TOKEN_MODEL_PREFIXES = ("gpt-5", "o1", "o3", "o4")

# Matches complete <think>…</think> blocks (DOTALL so newlines are included).
_THINK_RE = re.compile(r"<think>.*?</think>", re.DOTALL)
_THINK_OPEN_TAG = "<think>"


# ── 변환 함수 (Anthropic 포맷 → OpenAI 포맷) ─────────────────


def _token_limit_param_for_model(model: str, max_tokens: int) -> dict[str, int]:
    """Return the correct token limit field for the target OpenAI model."""
    normalized = model.strip().lower()
    if "/" in normalized:
        normalized = normalized.rsplit("/", 1)[-1]
    if normalized.startswith(_MAX_COMPLETION_TOKEN_MODEL_PREFIXES):
        return {"max_completion_tokens": max_tokens}
    return {"max_tokens": max_tokens}


def _convert_tools_to_openai(tools: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Convert Anthropic tool schemas to OpenAI function-calling format."""
    return [
        {
            "type": "function",
            "function": {
                "name": tool["name"],
                "description": tool.get("description", ""),
                "parameters": tool.get("input_schema", {}),
            },
        }
        for tool in tools
    ]


def _convert_user_content_to_openai(
    blocks: list[ContentBlock],
) -> str | list[dict[str, Any]]:
    """Convert user text/image blocks into OpenAI chat content."""
    has_image = any(isinstance(b, ImageBlock) for b in blocks)
    if not has_image:
        return "".join(b.text for b in blocks if isinstance(b, TextBlock))
    content: list[dict[str, Any]] = []
    for block in blocks:
        if isinstance(block, TextBlock) and block.text:
            content.append({"type": "text", "text": block.text})
        elif isinstance(block, ImageBlock):
            content.append({
                "type": "image_url",
                "image_url": {"url": f"data:{block.media_type};base64,{block.data}"},
            })
    return content


def _convert_assistant_message(msg: ConversationMessage) -> dict[str, Any]:
    """Convert an assistant ConversationMessage to OpenAI format."""
    text_parts = [b.text for b in msg.content if isinstance(b, TextBlock)]
    tool_uses = [b for b in msg.content if isinstance(b, ToolUseBlock)]

    openai_msg: dict[str, Any] = {
        "role": "assistant",
        "content": "".join(text_parts) or None,
    }

    reasoning = getattr(msg, "_reasoning", None)
    if reasoning:
        openai_msg["reasoning_content"] = reasoning
    elif tool_uses:
        openai_msg["reasoning_content"] = ""

    if tool_uses:
        openai_msg["tool_calls"] = [
            {
                "id": tu.id,
                "type": "function",
                "function": {"name": tu.name, "arguments": json.dumps(tu.input)},
            }
            for tu in tool_uses
        ]
    return openai_msg


def _convert_messages_to_openai(
    messages: list[ConversationMessage],
    system_prompt: str | None,
) -> list[dict[str, Any]]:
    """Convert Anthropic-style messages to OpenAI chat format."""
    openai_messages: list[dict[str, Any]] = []

    if system_prompt:
        openai_messages.append({"role": "system", "content": system_prompt})

    for msg in messages:
        if msg.role == "assistant":
            openai_messages.append(_convert_assistant_message(msg))
        elif msg.role == "user":
            tool_results = [b for b in msg.content if isinstance(b, ToolResultBlock)]
            user_blocks = [b for b in msg.content if isinstance(b, (TextBlock, ImageBlock))]

            if tool_results:
                for tr in tool_results:
                    openai_messages.append({
                        "role": "tool",
                        "tool_call_id": tr.tool_use_id,
                        "content": tr.content,
                    })
            if user_blocks:
                content = _convert_user_content_to_openai(user_blocks)
                if isinstance(content, str):
                    if content.strip():
                        openai_messages.append({"role": "user", "content": content})
                elif content:
                    openai_messages.append({"role": "user", "content": content})
            if not tool_results and not user_blocks:
                openai_messages.append({"role": "user", "content": ""})

    return openai_messages


def _strip_think_blocks(buf: str) -> tuple[str, str]:
    """Strip complete ``<think>…</think>`` blocks.

    Returns ``(visible_text, leftover)`` where leftover holds any unclosed
    ``<think>`` tag for the next streaming chunk.
    """
    cleaned = _THINK_RE.sub("", buf)

    open_idx = cleaned.find(_THINK_OPEN_TAG)
    if open_idx != -1:
        return cleaned[:open_idx], cleaned[open_idx:]

    max_prefix = min(len(cleaned), len(_THINK_OPEN_TAG) - 1)
    for prefix_len in range(max_prefix, 0, -1):
        if _THINK_OPEN_TAG.startswith(cleaned[-prefix_len:]):
            return cleaned[:-prefix_len], cleaned[-prefix_len:]

    return cleaned, ""


# ── URL normalizer ────────────────────────────────────────────


def _normalize_openai_base_url(base_url: str | None) -> str | None:
    if not base_url:
        return None
    trimmed = base_url.strip()
    if not trimmed:
        return None
    parts = urlsplit(trimmed)
    if not parts.scheme or not parts.netloc:
        return trimmed.rstrip("/")
    path = parts.path.rstrip("/") or "/v1"
    return urlunsplit((parts.scheme, parts.netloc, path, parts.query, parts.fragment))


def _extract_model_ids(model_list_response: Any) -> list[str]:
    data = (
        model_list_response.get("data")
        if isinstance(model_list_response, dict)
        else getattr(model_list_response, "data", None)
    )
    if not data:
        return []
    ids: list[str] = []
    for item in data:
        model_id = (
            item.get("id")
            if isinstance(item, dict)
            else getattr(item, "id", None)
        )
        if isinstance(model_id, str) and model_id.strip():
            ids.append(model_id.strip())
    return ids


def _select_served_model(
    requested_model: str,
    served_model_ids: list[str],
    preferred_model: str | None = None,
) -> str:
    if not served_model_ids:
        raise RuntimeError("OpenAI-compatible server returned no served models.")

    requested = requested_model.strip()
    if requested in served_model_ids:
        return requested

    preferred = (preferred_model or "").strip()
    if preferred and preferred in served_model_ids:
        return preferred

    return served_model_ids[0]


# ── Client ────────────────────────────────────────────────────


class TheseusOpenAICompatClient:
    """Client for OpenAI-compatible APIs (DashScope, DeepSeek, Ollama, vLLM, etc.).

    Implements the same SupportsStreamingMessages protocol as TheseusAnthropicClient.
    """

    def __init__(
        self,
        api_key: str,
        *,
        base_url: str | None = None,
        timeout: float | None = None,
        auto_discover_model: bool = False,
        preferred_model: str | None = None,
    ) -> None:
        kwargs: dict[str, Any] = {"api_key": api_key}
        normalized = _normalize_openai_base_url(base_url)
        if normalized:
            kwargs["base_url"] = normalized
        if timeout is not None:
            kwargs["timeout"] = timeout
        self._client = AsyncOpenAI(**kwargs)
        self._auto_discover_model = auto_discover_model
        self._preferred_model = preferred_model
        self._discovered_model: str | None = None

    async def stream_message(
        self, request: ApiMessageRequest
    ) -> AsyncIterator[ApiStreamEvent]:
        """Yield text deltas and the final message with retry."""
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
                if attempt >= MAX_RETRIES or not self._is_retryable(exc):
                    raise self._translate_error(exc) from exc

                delay = min(BASE_DELAY * (2 ** attempt), MAX_DELAY)
                log.warning(
                    "OpenAI-compat API failed (attempt %d/%d), "
                    "retrying in %.1fs: %s",
                    attempt + 1, MAX_RETRIES + 1, delay, exc,
                )
                yield ApiRetryEvent(
                    message=str(exc),
                    attempt=attempt + 1,
                    max_attempts=MAX_RETRIES + 1,
                    delay_seconds=delay,
                )
                await asyncio.sleep(delay)

        if last_error is not None:
            raise self._translate_error(last_error) from last_error

    async def _stream_once(
        self, request: ApiMessageRequest
    ) -> AsyncIterator[ApiStreamEvent]:
        openai_messages = _convert_messages_to_openai(
            request.messages, request.system_prompt
        )
        openai_tools = _convert_tools_to_openai(request.tools) if request.tools else None
        resolved_model = await self._resolve_served_model(request.model)

        params: dict[str, Any] = {
            "model": resolved_model,
            "messages": openai_messages,
            "stream": True,
            "stream_options": {"include_usage": True},
        }
        params.update(_token_limit_param_for_model(resolved_model, request.max_tokens))
        if openai_tools:
            params["tools"] = openai_tools
            params.pop("stream_options", None)

        dump_debug_payload(
            "openai_compat_final_params_summary",
            summarize_openai_params(params),
            debug_context=request.debug_context,
        )

        collected_content = ""
        collected_reasoning = ""
        collected_tool_calls: dict[int, dict[str, Any]] = {}
        finish_reason: str | None = None
        usage_data: dict[str, int] = {}
        _think_buf = ""

        try:
            stream = await self._client.chat.completions.create(**params)
        except Exception as exc:
            if not self._auto_discover_model or not self._is_model_not_found(exc):
                raise
            self._discovered_model = None
            refreshed_model = await self._resolve_served_model(request.model)
            if refreshed_model == resolved_model:
                raise
            params["model"] = refreshed_model
            params.pop("max_tokens", None)
            params.pop("max_completion_tokens", None)
            params.update(_token_limit_param_for_model(refreshed_model, request.max_tokens))
            stream = await self._client.chat.completions.create(**params)
        async for chunk in stream:
            if not chunk.choices:
                if chunk.usage:
                    usage_data = {
                        "input_tokens": chunk.usage.prompt_tokens or 0,
                        "output_tokens": chunk.usage.completion_tokens or 0,
                    }
                continue

            delta = chunk.choices[0].delta
            chunk_finish = chunk.choices[0].finish_reason
            if chunk_finish:
                finish_reason = chunk_finish

            reasoning_piece = getattr(delta, "reasoning_content", None) or ""
            if reasoning_piece:
                collected_reasoning += reasoning_piece

            if delta.content:
                _think_buf += delta.content
                visible, _think_buf = _strip_think_blocks(_think_buf)
                if visible:
                    collected_content += visible
                    yield ApiTextDeltaEvent(text=visible)

            if getattr(delta, "tool_calls", None):
                for tc_delta in delta.tool_calls:
                    idx = tc_delta.index
                    if idx not in collected_tool_calls:
                        collected_tool_calls[idx] = {
                            "id": tc_delta.id or "",
                            "name": "",
                            "arguments": "",
                        }
                    entry = collected_tool_calls[idx]
                    if tc_delta.id:
                        entry["id"] = tc_delta.id
                    if tc_delta.function:
                        if tc_delta.function.name:
                            entry["name"] = tc_delta.function.name
                        if tc_delta.function.arguments:
                            entry["arguments"] += tc_delta.function.arguments

            if chunk.usage:
                usage_data = {
                    "input_tokens": chunk.usage.prompt_tokens or 0,
                    "output_tokens": chunk.usage.completion_tokens or 0,
                }

        content: list[ContentBlock] = []
        if collected_content:
            content.append(TextBlock(text=collected_content))
        for _idx in sorted(collected_tool_calls.keys()):
            tc = collected_tool_calls[_idx]
            if not tc["name"]:
                continue
            try:
                args = json.loads(tc["arguments"])
            except (json.JSONDecodeError, TypeError) as parse_err:
                raw_args = str(tc.get("arguments") or "")
                log.warning(
                    "OpenAI-compatible tool arguments could not be parsed: "
                    "tool=%s id=%s error=%s",
                    tc["name"],
                    tc["id"],
                    parse_err,
                )
                dump_debug_payload(
                    "openai_compat_tool_arg_parse_error",
                    {
                        "tool_name": tc["name"],
                        "tool_call_id": tc["id"],
                        "error": str(parse_err),
                        "raw_arguments_preview": raw_args[:500],
                    },
                    debug_context=request.debug_context,
                )
                args = {"_parse_error": str(parse_err), "_raw": raw_args[:200]}
            content.append(ToolUseBlock(id=tc["id"], name=tc["name"], input=args))

        final_message = ConversationMessage(role="assistant", content=content)
        if collected_reasoning:
            object.__setattr__(final_message, "_reasoning", collected_reasoning)

        yield ApiMessageCompleteEvent(
            message=final_message,
            usage=UsageSnapshot(
                input_tokens=usage_data.get("input_tokens", 0),
                output_tokens=usage_data.get("output_tokens", 0),
            ),
            stop_reason=finish_reason,
        )

    async def _resolve_served_model(self, requested_model: str) -> str:
        if not self._auto_discover_model:
            return requested_model
        if self._discovered_model:
            return self._discovered_model

        model_list = await self._client.models.list()
        served_model_ids = _extract_model_ids(model_list)
        selected = _select_served_model(
            requested_model,
            served_model_ids,
            self._preferred_model,
        )
        self._discovered_model = selected
        log.info(
            "Resolved OpenAI-compatible served model: requested=%s selected=%s available=%s",
            requested_model,
            selected,
            served_model_ids,
        )
        return selected

    @staticmethod
    def _is_retryable(exc: Exception) -> bool:
        status = getattr(exc, "status_code", None)
        if status and status in {429, 500, 502, 503}:
            return True
        return isinstance(exc, (ConnectionError, TimeoutError, OSError))

    @staticmethod
    def _is_model_not_found(exc: Exception) -> bool:
        status = getattr(exc, "status_code", None)
        if status != 404:
            return False
        message = str(exc).lower()
        return "model" in message and (
            "not found" in message
            or "does not exist" in message
            or "not served" in message
        )

    @staticmethod
    def _translate_error(exc: Exception) -> TheseusApiError:
        status = getattr(exc, "status_code", None)
        msg = str(exc)
        if "API_KEY_INVALID" in msg or "API key not valid" in msg:
            return AuthenticationFailure(msg)
        if status in (401, 403):
            return AuthenticationFailure(msg)
        if status == 429:
            return RateLimitFailure(msg)
        return RequestFailure(msg)
