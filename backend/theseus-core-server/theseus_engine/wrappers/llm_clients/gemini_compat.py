"""Gemini API compatibility utilities.

Handles Gemini 3.1 Pro's non-standard `extra_content` / `thought_signature`
field that must be preserved and re-injected across multi-turn tool-calling
conversations.

Architecture:
    Gemini attaches a cryptographic `thought_signature` to every tool call
    it makes.  When the conversation is sent back to the API for the next
    turn, the signature **must** be present on the assistant message's
    tool_calls — otherwise the API returns a 400 error.

    The OpenAI Python SDK's Pydantic models do NOT define this field, so
    it lands in `ChoiceDeltaToolCall.model_extra['extra_content']` during
    streaming.  This module provides helpers to extract, stash, and
    re-inject the field transparently.
"""

from __future__ import annotations

from typing import Any

# ---------------------------------------------------------------------------
# Default placeholder for sessions reloaded from disk where the original
# thought_signature was lost (not serialised in session JSON).
#
# Per official Gemini 3 developer guide
# (https://ai.google.dev/gemini-api/docs/gemini-3):
# "When transferring from a different model or injecting a custom function
# call without a valid signature, fill the field with this specific dummy
# string to bypass strict validation."
# ---------------------------------------------------------------------------
# 공식 문서 출처:
# https://ai.google.dev/gemini-api/docs/thought-signatures?hl=ko (1240번 라인)
# "context_engineering_is_the_way_to_go" 또는 "skip_thought_signature_validator"
_FALLBACK_THOUGHT_SIGNATURE = "skip_thought_signature_validator"

_FALLBACK_EXTRA_CONTENT: dict[str, Any] = {
    "google": {
        "thought_signature": _FALLBACK_THOUGHT_SIGNATURE,
    }
}


def extract_extra_content(tc_delta: Any) -> dict[str, Any] | None:
    """Extract ``extra_content`` from a streaming ``ChoiceDeltaToolCall``.

    The field lives in ``tc_delta.model_extra['extra_content']``.

    Args:
        tc_delta: A single ``ChoiceDeltaToolCall`` object from the
            OpenAI streaming response.

    Returns:
        The ``extra_content`` dict if present, otherwise ``None``.
    """
    extras = getattr(tc_delta, "model_extra", {}) or {}
    return extras.get("extra_content")


def rebuild_tool_call_dict(
    tc_id: str,
    name: str,
    arguments: str,
    extra_content: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Build a tool_call dict suitable for re-injection into the API.

    Args:
        tc_id: The tool call ID.
        name: The function name.
        arguments: The raw JSON arguments string.
        extra_content: The ``extra_content`` dict captured from the
            original streaming response.  If ``None``, no
            ``extra_content`` key is added.

    Returns:
        A dict matching the Gemini-expected tool_call schema.
    """
    rebuilt: dict[str, Any] = {
        "id": tc_id,
        "type": "function",
        "function": {
            "name": name,
            "arguments": arguments,
        },
    }
    if extra_content is not None:
        rebuilt["extra_content"] = extra_content
    return rebuilt


def patch_assistant_tool_calls(
    openai_messages: list[dict[str, Any]],
    original_messages: list[Any],
) -> None:
    """Patch assistant messages in-place to include ``extra_content``.

    When the conversation is sent back to Gemini, each assistant
    message's ``tool_calls`` must include the original
    ``extra_content.google.thought_signature``.  This function
    re-injects them from the stashed ``_raw_tool_calls`` attribute,
    or provides a fallback placeholder for reloaded sessions.

    Args:
        openai_messages: The list of OpenAI-formatted message dicts
            (mutated in place).
        original_messages: The original ``ConversationMessage`` list
            from the request (used to look up ``_raw_tool_calls``).
    """
    original_assistant_msgs = [
        m for m in original_messages if m.role == "assistant"
    ]
    assistant_idx = 0
    import sys

    for o_msg in openai_messages:
        if o_msg["role"] != "assistant":
            continue

        if assistant_idx < len(original_assistant_msgs):
            orig_msg = original_assistant_msgs[assistant_idx]
            raw_tool_calls = getattr(orig_msg, "_raw_tool_calls", {})

            if "tool_calls" in o_msg:
                for j, tc in enumerate(o_msg["tool_calls"]):
                    tc_id = tc.get("id")
                    if raw_tool_calls and tc_id in raw_tool_calls:
                        raw_tc = dict(raw_tool_calls[tc_id])
                        # extra_content 없으면 공식 Fallback 주입
                        # 공식 OpenAI 호환 형식:
                        # {"extra_content": {"google": {"thought_signature": "..."}}}
                        if "extra_content" not in raw_tc:
                            raw_tc["extra_content"] = _FALLBACK_EXTRA_CONTENT
                        o_msg["tool_calls"][j] = raw_tc
                    else:
                        # _raw_tool_calls 자체가 없는 경우 (세션 재로드 등)
                        if "extra_content" not in tc:
                            tc["extra_content"] = _FALLBACK_EXTRA_CONTENT
                            print(f"[DEBUG] Patched fallback thought_signature for tool {tc.get('id')} at pos {j}", file=sys.stderr)

        assistant_idx += 1
