"""
OpenHarness 외부 모듈을 직접 수정하지 않고 런타임에 동적으로 로직을 덮어쓰는(Monkey-patch) 파일입니다.
"""

import json
from typing import Any, AsyncIterator
import openharness.api.openai_client as openai_client
from openharness.engine.messages import ConversationMessage, ToolUseBlock, TextBlock, ContentBlock
from openharness.api.client import (
    ApiTextDeltaEvent,
    ApiMessageCompleteEvent,
    ApiStreamEvent,
    ApiMessageRequest
)
from openharness.api.usage import UsageSnapshot
from openharness.api.openai_client import (
    _convert_messages_to_openai, 
    _strip_think_blocks, 
    _parse_assistant_response, 
    _convert_assistant_message,
    _convert_tools_to_openai,
    _token_limit_param_for_model
)

_original_stream_once = openai_client.OpenAICompatibleClient._stream_once
_original_convert_assistant_message = openai_client._convert_assistant_message
_original_parse_assistant_response = openai_client._parse_assistant_response

async def patched_stream_once(
    self,
    request: ApiMessageRequest
) -> AsyncIterator[ApiStreamEvent]:
    openai_messages = _convert_messages_to_openai(request.messages, request.system_prompt)
    openai_tools = _convert_tools_to_openai(request.tools) if request.tools else None
    
    params: dict[str, Any] = {
        "model": request.model,
        "messages": openai_messages,
        "stream": True,
        "stream_options": {"include_usage": True},
    }
    params.update(_token_limit_param_for_model(request.model, request.max_tokens))
    if openai_tools:
        params["tools"] = openai_tools
        params.pop("stream_options", None)

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
                        "id": getattr(tc_delta, "id", "") or "",
                        "name": "",
                        "arguments": "",
                        "raw_tool_call": {}
                    }
                entry = collected_tool_calls[idx]
                if getattr(tc_delta, "id", None):
                    entry["id"] = tc_delta.id
                if getattr(tc_delta, "function", None):
                    if tc_delta.function.name:
                        entry["name"] = tc_delta.function.name
                    if tc_delta.function.arguments:
                        entry["arguments"] += tc_delta.function.arguments
                
                # Gemini thought_signature 추출 (extra_content 보존)
                raw_delta = getattr(tc_delta, "model_dump", lambda: None)()
                if not raw_delta and hasattr(tc_delta, "dict"):
                    raw_delta = tc_delta.dict()
                if raw_delta and "extra_content" in raw_delta:
                    entry["raw_tool_call"]["extra_content"] = raw_delta["extra_content"]

        if chunk.usage:
            usage_data = {
                "input_tokens": chunk.usage.prompt_tokens or 0,
                "output_tokens": chunk.usage.completion_tokens or 0,
            }

    content: list[ContentBlock] = []
    if collected_content:
        content.append(TextBlock(text=collected_content))

    raw_tool_calls_dict = {}

    for _idx in sorted(collected_tool_calls.keys()):
        tc = collected_tool_calls[_idx]
        if not tc["name"]:
            continue
        try:
            args = json.loads(tc["arguments"])
        except (json.JSONDecodeError, TypeError):
            args = {}
        content.append(ToolUseBlock(
            id=tc["id"],
            name=tc["name"],
            input=args,
        ))
        
        # Stash raw_tool_call mapping for later convert
        if tc["raw_tool_call"].get("extra_content"):
            raw_tool_calls_dict[tc["id"]] = {
                "id": tc["id"],
                "type": "function",
                "function": {
                    "name": tc["name"],
                    "arguments": tc["arguments"]
                },
                "extra_content": tc["raw_tool_call"]["extra_content"]
            }

    final_message = ConversationMessage(role="assistant", content=content)
    if raw_tool_calls_dict:
        object.__setattr__(final_message, "_raw_tool_calls", raw_tool_calls_dict)

    if collected_reasoning:
        final_message._reasoning = collected_reasoning

    yield ApiMessageCompleteEvent(
        message=final_message,
        usage=UsageSnapshot(
            input_tokens=usage_data.get("input_tokens", 0),
            output_tokens=usage_data.get("output_tokens", 0),
        ),
        stop_reason=finish_reason,
    )

def patched_convert_assistant_message(msg: ConversationMessage) -> dict[str, Any]:
    openai_msg = _original_convert_assistant_message(msg)
    raw_tool_calls = getattr(msg, "_raw_tool_calls", {})
    if raw_tool_calls and "tool_calls" in openai_msg:
        for i, tc in enumerate(openai_msg["tool_calls"]):
            tc_id = tc.get("id")
            if tc_id in raw_tool_calls:
                openai_msg["tool_calls"][i] = raw_tool_calls[tc_id]
    return openai_msg

def patched_parse_assistant_response(response: Any) -> ConversationMessage:
    msg = _original_parse_assistant_response(response)
    choice = response.choices[0]
    raw_message = choice.message
    if getattr(raw_message, "tool_calls", None):
        raw_tool_calls = {}
        for tc in raw_message.tool_calls:
            raw_tc = getattr(tc, "model_dump", lambda: None)()
            if not raw_tc and hasattr(tc, "dict"):
                raw_tc = tc.dict()
            if not raw_tc:
                raw_tc = {}
            raw_tool_calls[tc.id] = raw_tc
        object.__setattr__(msg, "_raw_tool_calls", raw_tool_calls)
    return msg

def apply_patches():
    openai_client.OpenAICompatibleClient._stream_once = patched_stream_once
    openai_client._convert_assistant_message = patched_convert_assistant_message
    openai_client._parse_assistant_response = patched_parse_assistant_response
    print("🩹 [System] OpenHarness Monkey Patches Applied (Gemini Stream Tool Calling Fix)")
