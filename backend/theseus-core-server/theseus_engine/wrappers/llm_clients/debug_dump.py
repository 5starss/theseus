"""Debug dump helpers for Theseus LLM requests.

This module intentionally contains no provider client code so OpenAI-compatible
and router clients can share the same observability payloads without circular
imports.
"""

from __future__ import annotations

import json
import os
import re
import sys
from pathlib import Path
from typing import Any

from theseus_engine.models.messages import ToolResultBlock, ToolUseBlock


DEBUG_DUMP_ENABLED: bool = os.getenv("THESEUS_DEBUG_DUMP", "false").lower() == "true"
DEBUG_DUMP_DIR = Path(
    os.getenv("THESEUS_DEBUG_DUMP_DIR", Path.home() / ".theseus" / "debug_dumps")
)


def sanitize_debug_path_part(value: Any, *, default: str) -> str:
    text = str(value).strip() if value is not None else ""
    if not text:
        text = default
    text = re.sub(r"[^A-Za-z0-9._=-]+", "_", text).strip("._")
    return (text or default)[:120]


def debug_scope_name(debug_context: dict[str, Any] | None) -> str:
    context = debug_context if isinstance(debug_context, dict) else {}
    explicit = context.get("debug_dump_scope")
    if explicit:
        return sanitize_debug_path_part(explicit, default="session_unscoped")

    project_id = context.get("project_id")
    chat_session_id = context.get("chat_session_id")
    session_id = context.get("session_id")
    run_id = context.get("run_id")

    if project_id is not None and chat_session_id is not None:
        return sanitize_debug_path_part(
            f"project_{project_id}_chat_{chat_session_id}",
            default="session_unscoped",
        )
    if session_id is not None:
        return sanitize_debug_path_part(f"session_{session_id}", default="session_unscoped")
    if run_id is not None:
        return sanitize_debug_path_part(f"run_{run_id}", default="session_unscoped")
    return "session_unscoped"


def dump_debug_payload(
    name: str,
    data: Any,
    *,
    debug_context: dict[str, Any] | None = None,
) -> None:
    """Dump one JSON debug payload when THESEUS_DEBUG_DUMP=true."""

    if not DEBUG_DUMP_ENABLED:
        return
    try:
        scope_name = debug_scope_name(debug_context)
        dump_dir = DEBUG_DUMP_DIR / scope_name
        dump_dir.mkdir(parents=True, exist_ok=True)
        file_name = f"{sanitize_debug_path_part(name, default='payload')}.json"
        dump_path = dump_dir / file_name
        tmp_path = dump_path.with_name(f".{dump_path.stem}.{os.getpid()}.{id(data)}.tmp")

        def _serializer(obj: Any) -> Any:
            if hasattr(obj, "model_dump"):
                return obj.model_dump()
            if hasattr(obj, "__dict__"):
                return obj.__dict__
            return str(obj)

        with open(tmp_path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2, default=_serializer)
        tmp_path.replace(dump_path)
        print(f"\n[DEBUG] Dumped {name} to {dump_path}\n", file=sys.stderr)
    except Exception as exc:
        print(f"\n[DEBUG] Failed to dump {name}: {exc}\n", file=sys.stderr)


def summarize_api_message_request(request: Any) -> dict[str, Any]:
    """Summarize tool schema availability separately from actual tool history."""

    tools = list(getattr(request, "tools", None) or [])
    tool_names = [_tool_schema_name(tool) for tool in tools]
    tool_names = [name for name in tool_names if name]

    history_tool_names: list[str] = []
    tool_use_count = 0
    tool_result_count = 0
    tool_history_messages: list[dict[str, Any]] = []

    for index, message in enumerate(getattr(request, "messages", []) or []):
        role = getattr(message, "role", None)
        message_tool_uses = []
        message_tool_results = []
        for block in getattr(message, "content", []) or []:
            if isinstance(block, ToolUseBlock):
                tool_use_count += 1
                history_tool_names.append(block.name)
                message_tool_uses.append({"id": block.id, "name": block.name})
            elif isinstance(block, ToolResultBlock):
                tool_result_count += 1
                message_tool_results.append(
                    {
                        "tool_use_id": block.tool_use_id,
                        "is_error": block.is_error,
                        "content_length": len(block.content or ""),
                    }
                )
        if message_tool_uses or message_tool_results:
            tool_history_messages.append(
                {
                    "index": index,
                    "role": role,
                    "toolUses": message_tool_uses,
                    "toolResults": message_tool_results,
                }
            )

    return {
        "availableToolNames": sorted(set(tool_names)),
        "toolSchemaCount": len(tool_names),
        "historyToolUseCount": tool_use_count,
        "historyToolResultCount": tool_result_count,
        "historyToolNames": sorted(set(history_tool_names)),
        "toolHistoryMessages": tool_history_messages,
        "hasResponseFormat": bool(getattr(request, "response_format", None)),
        "hasExtraBody": bool(getattr(request, "extra_body", None)),
    }


def summarize_openai_params(params: dict[str, Any]) -> dict[str, Any]:
    """Summarize the final OpenAI-compatible wire payload."""

    messages = list(params.get("messages") or [])
    tools = list(params.get("tools") or [])
    available_tool_names = [_openai_tool_name(tool) for tool in tools]
    available_tool_names = [name for name in available_tool_names if name]

    provider_tool_names: list[str] = []
    provider_tool_call_count = 0
    provider_tool_result_count = 0
    roles: dict[str, int] = {}

    for message in messages:
        if not isinstance(message, dict):
            continue
        role = str(message.get("role") or "")
        roles[role] = roles.get(role, 0) + 1
        if role == "tool":
            provider_tool_result_count += 1
        for tool_call in message.get("tool_calls") or []:
            if not isinstance(tool_call, dict):
                continue
            provider_tool_call_count += 1
            function = tool_call.get("function")
            if isinstance(function, dict) and function.get("name"):
                provider_tool_names.append(str(function["name"]))

    return {
        "model": params.get("model"),
        "messageCount": len(messages),
        "messageRoles": roles,
        "availableToolNames": sorted(set(available_tool_names)),
        "toolSchemaCount": len(available_tool_names),
        "providerToolCallCount": provider_tool_call_count,
        "providerToolResultCount": provider_tool_result_count,
        "providerToolNames": sorted(set(provider_tool_names)),
        "hasTools": bool(tools),
        "hasResponseFormat": bool(params.get("response_format")),
        "hasExtraBody": bool(params.get("extra_body")),
    }


def _tool_schema_name(tool: Any) -> str:
    if isinstance(tool, dict):
        return str(tool.get("name") or tool.get("function", {}).get("name") or "")
    return str(getattr(tool, "name", "") or "")


def _openai_tool_name(tool: Any) -> str:
    if not isinstance(tool, dict):
        return ""
    function = tool.get("function")
    if isinstance(function, dict):
        return str(function.get("name") or "")
    return str(tool.get("name") or "")
