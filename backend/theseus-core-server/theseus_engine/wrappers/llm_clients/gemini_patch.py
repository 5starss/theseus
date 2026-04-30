"""Gemini thought_signature monkey-patch for OpenAICompatibleClient.

OpenHarness 코어를 수정하지 않고, 런타임에 OpenAICompatibleClient._stream_once 를
Gemini thought_signature 를 처리하는 버전으로 교체합니다.

Architecture:
    1. 원본 _stream_once 를 저장해 둡니다.
    2. Gemini 모델이면 thought_signature 를 캡처하고 패치하는 로직이 포함된
       새로운 _stream_once 를 사용합니다.
    3. Gemini 가 아니면 원본을 그대로 실행합니다.
"""

from __future__ import annotations

import json
import sys
from typing import Any, AsyncIterator

from openharness.api.client import (
    ApiMessageCompleteEvent,
    ApiMessageRequest,
    ApiStreamEvent,
    ApiTextDeltaEvent,
)
from openharness.api.openai_client import (
    OpenAICompatibleClient,
    _convert_messages_to_openai,
    _convert_tools_to_openai,
    _strip_think_blocks,
    _token_limit_param_for_model,
)
from openharness.api.usage import UsageSnapshot
from openharness.engine.messages import (
    ContentBlock,
    ConversationMessage,
    TextBlock,
    ToolUseBlock,
)

from theseus_engine.wrappers.llm_clients.gemini_compat import (
    extract_extra_content,
    patch_assistant_tool_calls,
    rebuild_tool_call_dict,
)

# 원본 메서드 백업
_original_stream_once = OpenAICompatibleClient._stream_once


def _is_gemini_model(model_name: str) -> bool:
    """모델명에 'gemini'가 포함되어 있는지 확인합니다."""
    return "gemini" in model_name.lower()


async def _patched_stream_once(
    self: OpenAICompatibleClient,
    request: ApiMessageRequest,
) -> AsyncIterator[ApiStreamEvent]:
    """Gemini 모델일 때 thought_signature 를 캡처/패치하는 _stream_once.

    Gemini 가 아닌 모델에서는 원본 _stream_once 를 그대로 실행합니다.
    """
    if not _is_gemini_model(request.model):
        async for event in _original_stream_once(self, request):
            yield event
        return

    # --- Gemini 전용 경로: thought_signature 처리 포함 ---
    print(
        f"[GEMINI_PATCH] Gemini model detected: {request.model}",
        file=sys.stderr,
    )

    # 1. Convert messages and patch thought_signatures
    openai_messages = _convert_messages_to_openai(
        request.messages, request.system_prompt,
    )
    patch_assistant_tool_calls(openai_messages, request.messages)

    openai_tools = (
        _convert_tools_to_openai(request.tools)
        if request.tools
        else None
    )

    params: dict[str, Any] = {
        "model": request.model,
        "messages": openai_messages,
        "stream": True,
        "stream_options": {"include_usage": True},
    }
    params.update(
        _token_limit_param_for_model(
            request.model, request.max_tokens,
        ),
    )
    if openai_tools:
        params["tools"] = openai_tools
        params.pop("stream_options", None)

    # 2. Stream and collect response
    collected_content = ""
    collected_reasoning = ""
    collected_tool_calls: dict[int, dict[str, Any]] = {}
    finish_reason: str | None = None
    usage_data: dict[str, int] = {}
    _think_buf = ""

    stream = await self._client.chat.completions.create(**params)
    async for chunk in stream:
        if not chunk.choices:
            if chunk.usage:
                usage_data = {
                    "input_tokens": (
                        chunk.usage.prompt_tokens or 0
                    ),
                    "output_tokens": (
                        chunk.usage.completion_tokens or 0
                    ),
                }
            continue

        delta = chunk.choices[0].delta
        chunk_finish = chunk.choices[0].finish_reason

        if chunk_finish:
            finish_reason = chunk_finish

        reasoning_piece = (
            getattr(delta, "reasoning_content", None) or ""
        )
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
                        "id": getattr(tc_delta, "id", "") or "",
                        "name": "",
                        "arguments": "",
                        "extra_content": None,
                    }
                entry = collected_tool_calls[idx]
                if getattr(tc_delta, "id", None):
                    entry["id"] = tc_delta.id
                if getattr(tc_delta, "function", None):
                    if tc_delta.function.name:
                        entry["name"] = tc_delta.function.name
                    if tc_delta.function.arguments:
                        entry["arguments"] += (
                            tc_delta.function.arguments
                        )

                # Capture Gemini extra_content (thought_signature)
                ec = extract_extra_content(tc_delta)
                if ec is not None:
                    entry["extra_content"] = ec

        if chunk.usage:
            usage_data = {
                "input_tokens": chunk.usage.prompt_tokens or 0,
                "output_tokens": (
                    chunk.usage.completion_tokens or 0
                ),
            }

    # 3. Build final ConversationMessage
    content: list[ContentBlock] = []
    if collected_content:
        content.append(TextBlock(text=collected_content))

    raw_tool_calls_dict: dict[str, dict[str, Any]] = {}
    for _idx in sorted(collected_tool_calls.keys()):
        tc = collected_tool_calls[_idx]
        if not tc["name"]:
            continue
        try:
            args = json.loads(tc["arguments"])
        except (json.JSONDecodeError, TypeError):
            args = {}
        content.append(
            ToolUseBlock(
                id=tc["id"], name=tc["name"], input=args,
            ),
        )

        raw_tool_calls_dict[tc["id"]] = rebuild_tool_call_dict(
            tc_id=tc["id"],
            name=tc["name"],
            arguments=tc["arguments"],
            extra_content=tc["extra_content"],
        )

    final_message = ConversationMessage(
        role="assistant", content=content,
    )
    if raw_tool_calls_dict:
        object.__setattr__(
            final_message, "_raw_tool_calls", raw_tool_calls_dict,
        )

    if collected_reasoning:
        object.__setattr__(
            final_message, "_reasoning", collected_reasoning,
        )

    yield ApiMessageCompleteEvent(
        message=final_message,
        usage=UsageSnapshot(
            input_tokens=usage_data.get("input_tokens", 0),
            output_tokens=usage_data.get("output_tokens", 0),
        ),
        stop_reason=finish_reason,
    )


def apply_gemini_patch() -> None:
    """OpenAICompatibleClient._stream_once 를 몽키패치합니다.

    앱 시작 시 한 번만 호출하면 됩니다.
    어떤 코드 경로를 타든 Gemini 모델 사용 시
    thought_signature 가 자동으로 처리됩니다.
    """
    OpenAICompatibleClient._stream_once = _patched_stream_once
    print(
        "[GEMINI_PATCH] ✅ OpenAICompatibleClient._stream_once "
        "successfully patched for Gemini thought_signature support.",
        file=sys.stderr,
    )
