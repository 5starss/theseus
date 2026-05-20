"""Theseus-native QueryEngine.

기존 QueryEngine 호환 인터페이스를 Theseus 자체 구현으로 제공합니다.

설계 원칙:
- QueryEngine public 인터페이스 유지 (duck-typing 호환)
- Theseus-native 타입만 사용 (messages, api_types, stream_events, base_tools)
- Auto-compact는 theseus_engine.core.context_compressor 위임
- Tool artifact 오프로드, permission 체크, hook 실행 파이프라인 자체 구현
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import re
import time
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Any, AsyncGenerator, AsyncIterator, Awaitable, Callable
from uuid import uuid4

from theseus_engine.models.messages import (
    ConversationMessage,
    ImageBlock,
    TextBlock,
    ToolResultBlock,
)
from theseus_engine.wrappers.llm_clients.api_types import (
    ApiMessageCompleteEvent,
    ApiMessageRequest,
    ApiRetryEvent,
    ApiStreamEvent,
    ApiTextDeltaEvent,
    SupportsStreamingMessages,
    UsageSnapshot,
)
from theseus_engine.engine.stream_events import (
    AgentLoopStatus,
    AssistantTextDelta,
    AssistantTurnComplete,
    ErrorEvent,
    PlanDraftedEvent,
    StatusEvent,
    StreamEvent,
    ToolExecutionCompleted,
    ToolExecutionStarted,
    extract_plan_json,
)
from theseus_engine.engine.loop_decision import (
    AGENT_AUTO_CONTINUE_MAX,
    AUTO_CONTINUE_PROMPT,
    LoopContinuationDecision,
    LoopDecisionContext,
    decide_loop_continuation,
    parse_semantic_decision_payload,
)
from theseus_engine.engine.tool_execution_state import is_remote_workspace_tool
from theseus_engine.skills.injection import (
    SkillInjectionConfig,
    apply_skill_injection,
)
from theseus_engine.tools.core.base_tools import (
    ToolExecutionContext,
    ToolRegistry,
    ToolResult,
    stringify_tool_output,
)
from theseus_engine.wrappers.hooks.theseus_hook_executor import HookEvent

log = logging.getLogger(__name__)

_DIFF_SNAPSHOT_MAX_BYTES = 1_000_000
_DEFAULT_NESTED_TOOL_MAX_DEPTH = 3
_DEFAULT_NESTED_TOOL_MAX_CALLS_PER_PARENT = 5
_DEFAULT_NESTED_TOOL_MAX_TOTAL_CALLS = 20
_NESTED_TOOL_BLOCKED_NAMES = frozenset(
    {
        "bash",
        "write_file",
        "edit_file",
        "local_write_report",
        "remote_write_file",
        "remote_edit_file",
        "remote_run_command",
        "system_reboot",
    }
)


@dataclass(frozen=True)
class ExecutedToolCall:
    result: ToolResultBlock
    metadata: dict[str, object]

PermissionPrompt = Callable[[str, str], Awaitable[bool]]
AskUserPrompt = Callable[[str], Awaitable[str]]

# Tool output 오프로드 임계값
_TOOL_OUTPUT_INLINE_CHARS = int(os.getenv("THESEUS_TOOL_OUTPUT_INLINE_CHARS", "8000"))
_TOOL_OUTPUT_PREVIEW_CHARS = int(os.getenv("THESEUS_TOOL_OUTPUT_PREVIEW_CHARS", "3000"))

# 안전한 최대 completion token 수
MAX_SAFE_COMPLETION_TOKENS = 128_000

# Auto-compact 기본 임계값 (메시지 수)
DEFAULT_AUTO_COMPACT_MESSAGES = 30
DEFAULT_KEEP_RECENT = 10


class MaxTurnsExceeded(RuntimeError):
    """에이전트 턴 한도 초과."""
    def __init__(self, max_turns: int) -> None:
        super().__init__(f"Exceeded maximum turn limit ({max_turns})")
        self.max_turns = max_turns


# ── 내부 유틸 ─────────────────────────────────────────────────

def _is_prompt_too_long_error(exc: Exception) -> bool:
    text = str(exc).lower()
    return any(
        needle in text for needle in (
            "prompt too long", "context_length_exceeded", "context length",
            "maximum context", "context window", "input tokens exceed",
            "messages resulted in", "reduce the length of the messages",
            "configured limit", "too many tokens", "too large for the model",
            "maximum context length", "exceed_context",
            "exceeds the available context size", "available context size",
        )
    )


def _is_completion_token_limit_error(exc: Exception) -> bool:
    text = str(exc).lower()
    return (
        ("max_tokens" in text or "max_completion_tokens" in text)
        and ("too large" in text or "at most" in text or "completion tokens" in text)
    )


def _extract_completion_token_limit(exc: Exception) -> int | None:
    text = str(exc).lower().replace(",", "")
    patterns = (
        r"supports at most\s+(\d+)\s+completion tokens",
        r"at most\s+(\d+)\s+completion tokens",
        r"max(?:imum)?(?:_completion)?[_\s-]tokens.*?(?:<=|less than or equal to|at most)\s+(\d+)",
    )
    for pattern in patterns:
        m = re.search(pattern, text)
        if m:
            try:
                return max(1, int(m.group(1)))
            except ValueError:
                return None
    return None


def _bounded_completion_tokens(
    max_tokens: int,
    context_window_tokens: int | None = None,
) -> int:
    limit = MAX_SAFE_COMPLETION_TOKENS
    if context_window_tokens and context_window_tokens > 0:
        limit = min(limit, int(context_window_tokens))
    return max(1, min(int(max_tokens), limit))


def _tool_artifact_dir() -> Path:
    data_dir = Path(os.getenv("THESEUS_DATA_DIR", Path.home() / ".theseus" / "data"))
    artifact_dir = data_dir / "tool_artifacts"
    artifact_dir.mkdir(parents=True, exist_ok=True)
    return artifact_dir


def _safe_tool_artifact_name(tool_name: str) -> str:
    return (re.sub(r"[^A-Za-z0-9_.-]+", "_", tool_name.strip()) or "tool")[:80]


def _offload_tool_output_if_needed(
    *,
    tool_name: str,
    tool_use_id: str,
    output: str,
) -> tuple[str, Path | None]:
    if len(output) <= _TOOL_OUTPUT_INLINE_CHARS:
        return output, None

    artifact_path = (
        _tool_artifact_dir()
        / f"{time.strftime('%Y%m%d-%H%M%S')}-{_safe_tool_artifact_name(tool_name)}-{uuid4().hex[:12]}.txt"
    )
    artifact_path.write_text(output, encoding="utf-8", errors="replace")
    preview = output[:_TOOL_OUTPUT_PREVIEW_CHARS]
    omitted = max(0, len(output) - len(preview))
    inline = (
        "[Tool output truncated]\n"
        f"Tool: {tool_name}\n"
        f"Tool use id: {tool_use_id}\n"
        f"Original size: {len(output)} chars\n"
        f"Full output saved to: {artifact_path}\n"
        f"Inline preview: first {len(preview)} chars"
    )
    if omitted:
        inline += f" ({omitted} chars omitted)"
    if preview:
        inline += f"\n\nPreview:\n{preview}"
    return inline, artifact_path


def _nested_tool_signature(tool_name: str, tool_input: dict[str, object]) -> str:
    try:
        payload = json.dumps(tool_input, ensure_ascii=False, sort_keys=True, default=str)
    except TypeError:
        payload = str(tool_input)
    return f"{tool_name}:{payload}"


def _metadata_int(
    metadata: dict[str, object],
    key: str,
    default: int,
) -> int:
    try:
        return int(metadata.get(key, default))
    except (TypeError, ValueError):
        return default


def _limit_preview(text: str, limit: int) -> str:
    if len(text) <= limit:
        return text
    return text[:limit].rstrip() + "\n... [truncated]"


def _resolve_permission_file_path(
    cwd: Path,
    raw_input: dict[str, object],
    parsed_input: object,
) -> str | None:
    for key in ("file_path", "path", "root"):
        value = raw_input.get(key)
        if isinstance(value, str) and value.strip():
            p = Path(value).expanduser()
            if not p.is_absolute():
                p = cwd / p
            return str(p.resolve())
    for attr in ("file_path", "path", "root"):
        value = getattr(parsed_input, attr, None)
        if isinstance(value, str) and value.strip():
            p = Path(value).expanduser()
            if not p.is_absolute():
                p = cwd / p
            return str(p.resolve())
    return None


def _extract_permission_command(
    raw_input: dict[str, object],
    parsed_input: object,
) -> str | None:
    value = raw_input.get("command")
    if isinstance(value, str) and value.strip():
        return value
    value = getattr(parsed_input, "command", None)
    if isinstance(value, str) and value.strip():
        return value
    return None


# tool_metadata 추적 헬퍼 ─────────────────────────────────────

MAX_TRACKED_USER_GOALS = 5
MAX_TRACKED_ACTIVE_ARTIFACTS = 8
MAX_TRACKED_VERIFIED_WORK = 10
MAX_TRACKED_WORK_LOG = 10
MAX_TRACKED_READ_FILES = 6


def _append_capped_unique(bucket: list[Any], value: Any, *, limit: int) -> None:
    if value in bucket:
        bucket.remove(value)
    bucket.append(value)
    if len(bucket) > limit:
        del bucket[:-limit]


def _tool_metadata_bucket(meta: dict | None, key: str) -> list:
    if meta is None:
        return []
    value = meta.setdefault(key, [])
    if not isinstance(value, list):
        meta[key] = []
        return meta[key]
    return value


def _task_focus_state(meta: dict | None) -> dict:
    if meta is None:
        return {}
    value = meta.setdefault("task_focus_state", {
        "goal": "", "recent_goals": [],
        "active_artifacts": [], "verified_state": [], "next_step": "",
    })
    if not isinstance(value, dict):
        meta["task_focus_state"] = {
            "goal": "", "recent_goals": [],
            "active_artifacts": [], "verified_state": [], "next_step": "",
        }
        return meta["task_focus_state"]
    for k, v in [("goal", ""), ("recent_goals", []), ("active_artifacts", []),
                 ("verified_state", []), ("next_step", "")]:
        value.setdefault(k, v)
    return value


def remember_user_goal(meta: dict | None, prompt: str) -> None:
    normalized = " ".join(prompt.split())[:240]
    if not normalized:
        return
    state = _task_focus_state(meta)
    recent = state.setdefault("recent_goals", [])
    if isinstance(recent, list):
        _append_capped_unique(recent, normalized, limit=MAX_TRACKED_USER_GOALS)
    state["goal"] = normalized


def _remember_active_artifact(meta: dict | None, artifact: str) -> None:
    normalized = artifact.strip()[:240]
    if not normalized:
        return
    state = _task_focus_state(meta)
    artifacts = state.setdefault("active_artifacts", [])
    if isinstance(artifacts, list):
        _append_capped_unique(artifacts, normalized, limit=MAX_TRACKED_ACTIVE_ARTIFACTS)


def _remember_verified_work(meta: dict | None, entry: str) -> None:
    normalized = entry.strip()[:320]
    if not normalized:
        return
    bucket = _tool_metadata_bucket(meta, "recent_verified_work")
    _append_capped_unique(bucket, normalized, limit=MAX_TRACKED_VERIFIED_WORK)
    state = _task_focus_state(meta)
    verified = state.setdefault("verified_state", [])
    if isinstance(verified, list):
        _append_capped_unique(verified, normalized, limit=MAX_TRACKED_VERIFIED_WORK)


def _remember_work_log(meta: dict | None, *, entry: str) -> None:
    bucket = _tool_metadata_bucket(meta, "recent_work_log")
    normalized = entry.strip()[:320]
    if not normalized:
        return
    bucket.append(normalized)
    if len(bucket) > MAX_TRACKED_WORK_LOG:
        del bucket[:-MAX_TRACKED_WORK_LOG]


def _remember_read_file(
    meta: dict | None, *, path: str, offset: int, limit: int, output: str,
) -> None:
    bucket = _tool_metadata_bucket(meta, "read_file_state")
    preview = " | ".join(l.strip() for l in output.splitlines()[:6] if l.strip())[:320]
    entry = {
        "path": path,
        "span": f"lines {offset + 1}-{offset + limit}",
        "preview": preview,
        "timestamp": time.time(),
    }
    if isinstance(bucket, list):
        bucket[:] = [e for e in bucket if not (isinstance(e, dict) and str(e.get("path")) == path)]
        bucket.append(entry)
        if len(bucket) > MAX_TRACKED_READ_FILES:
            del bucket[:-MAX_TRACKED_READ_FILES]


def _record_tool_carryover(
    meta: dict | None,
    *,
    tool_name: str,
    tool_input: dict,
    tool_output: str,
    is_error: bool,
    resolved_file_path: str | None,
) -> None:
    if is_error:
        return
    if resolved_file_path:
        _remember_active_artifact(meta, resolved_file_path)
    if tool_name == "remote_read_file":
        remote_path = str(tool_input.get("path") or "").strip()
        if remote_path:
            _remember_verified_work(meta, f"Inspected remote file {remote_path}")
            _remember_work_log(meta, entry=f"Read remote file {remote_path}")
    elif tool_name == "remote_grep":
        pattern = str(tool_input.get("query") or tool_input.get("pattern") or "").strip()
        _remember_verified_work(meta, f"Checked remote matches for pattern {pattern[:180]}")
        _remember_work_log(meta, entry=f"Searched remote pattern={pattern[:160]}")
    elif tool_name == "remote_glob":
        pattern = str(tool_input.get("pattern") or "").strip()
        _remember_verified_work(meta, f"Expanded remote glob pattern {pattern[:180]}")
        _remember_work_log(meta, entry=f"Expanded remote glob pattern={pattern[:160]}")
    elif tool_name == "remote_run_command":
        command = str(tool_input.get("command") or "").strip()
        command_name = command.split(maxsplit=1)[0] if command else "unknown"
        summary = (tool_output.splitlines()[0].strip() if tool_output.strip() else "no output")
        _remember_verified_work(meta, f"Ran remote command {command_name} [{summary[:120]}]")
        _remember_work_log(meta, entry=f"Ran remote command: {command_name} [{summary[:120]}]")
    elif tool_name.startswith("remote_check_"):
        summary = (tool_output.splitlines()[0].strip() if tool_output.strip() else "no output")
        _remember_verified_work(meta, f"Checked remote resource state with {tool_name} [{summary[:120]}]")
        _remember_work_log(meta, entry=f"Checked remote resource: {tool_name}")
    elif tool_name == "read_file" and resolved_file_path:
        offset = int(tool_input.get("offset") or 0)
        limit = int(tool_input.get("limit") or 200)
        _remember_read_file(meta, path=resolved_file_path,
                            offset=offset, limit=limit, output=tool_output)
        _remember_verified_work(meta, f"Inspected file {resolved_file_path} (lines {offset+1}-{offset+limit})")
        _remember_work_log(meta, entry=f"Read file {resolved_file_path}")
    elif tool_name == "bash":
        command = str(tool_input.get("command") or "").strip()
        summary = (tool_output.splitlines()[0].strip() if tool_output.strip() else "no output")
        _remember_verified_work(meta, f"Ran bash command {command[:160]} [{summary[:120]}]")
        _remember_work_log(meta, entry=f"Ran bash: {command[:160]} [{summary[:120]}]")
    elif tool_name == "grep":
        pattern = str(tool_input.get("pattern") or "").strip()
        _remember_verified_work(meta, f"Checked repository matches for grep pattern {pattern[:180]}")
        _remember_work_log(meta, entry=f"Searched with grep pattern={pattern[:160]}")
    elif tool_name == "glob":
        pattern = str(tool_input.get("pattern") or "").strip()
        _remember_verified_work(meta, f"Expanded glob pattern {pattern[:180]}")
    elif tool_name == "web_fetch":
        url = str(tool_input.get("url") or "").strip()
        if url:
            _remember_active_artifact(meta, url)
            _remember_verified_work(meta, f"Fetched remote content from {url}")
    elif tool_name == "web_search":
        query = str(tool_input.get("query") or "").strip()
        if query:
            _remember_verified_work(meta, f"Ran web search for {query[:180]}")


_LLM_DEBUG_CONTEXT_KEYS = {
    "session_id",
    "project_id",
    "user_id",
    "actor_user_id",
    "chat_session_id",
    "plan_id",
    "run_id",
    "tool_draft_id",
    "agent_mode",
    "plan_phase",
    "remote_workspace_id",
}
def _llm_debug_context(tool_metadata: dict[str, object] | None) -> dict[str, object]:
    if not isinstance(tool_metadata, dict):
        return {}
    debug_context: dict[str, object] = {}
    for key in _LLM_DEBUG_CONTEXT_KEYS:
        value = tool_metadata.get(key)
        if value is None or isinstance(value, (dict, list, tuple, set)):
            continue
        debug_context[key] = value
    return debug_context


# ── QueryContext ──────────────────────────────────────────────

@dataclass
class QueryContext:
    """단일 쿼리 실행에 공유되는 컨텍스트."""
    api_client: SupportsStreamingMessages
    tool_registry: ToolRegistry
    permission_checker: Any          # TheseusPermissionChecker (duck-typing)
    cwd: Path
    model: str
    system_prompt: str
    max_tokens: int
    context_window_tokens: int | None = None
    auto_compact_threshold_tokens: int | None = None
    max_turns: int | None = 200
    permission_prompt: PermissionPrompt | None = None
    ask_user_prompt: AskUserPrompt | None = None
    hook_executor: Any | None = None  # TheseusHookExecutor (duck-typing)
    tool_metadata: dict[str, object] | None = None
    is_plan_drafting: bool = False
    """PLAN 모드 DRAFTING 단계 여부. True일 때 JSON 감지 시 PlanDraftedEvent를 yield."""


# ── Tool 실행 ─────────────────────────────────────────────────

async def _execute_tool_call(
    context: QueryContext,
    tool_name: str,
    tool_use_id: str,
    tool_input: dict[str, object],
) -> ExecutedToolCall:
    def _result(content: str, is_error: bool = False, metadata: dict[str, object] | None = None) -> ExecutedToolCall:
        return ExecutedToolCall(
            result=ToolResultBlock(
                tool_use_id=tool_use_id,
                content=content,
                is_error=is_error,
            ),
            metadata=metadata or {},
        )

    tool = context.tool_registry.get(tool_name)
    if tool is None:
        log.warning("unknown tool: %s", tool_name)
        return _result(f"Unknown tool: {tool_name}", True)

    tool_metadata = dict(context.tool_metadata or {})
    call_stack = tuple(
        str(item)
        for item in tool_metadata.get("nested_tool_call_stack", ())
        if item is not None
    )
    if tool_name in call_stack:
        return _result(
            f"Nested tool call blocked: recursive call to {tool_name}.",
            True,
            metadata={"nestedToolBlocked": "recursive_call"},
        )
    try:
        max_nested_depth = int(
            tool_metadata.get(
                "nested_tool_max_depth",
                _DEFAULT_NESTED_TOOL_MAX_DEPTH,
            )
        )
    except (TypeError, ValueError):
        max_nested_depth = _DEFAULT_NESTED_TOOL_MAX_DEPTH
    if call_stack and len(call_stack) >= max_nested_depth:
        return _result(
            (
                "Nested tool call blocked: maximum nested tool depth "
                f"({max_nested_depth}) exceeded."
            ),
            True,
            metadata={"nestedToolBlocked": "max_depth_exceeded"},
        )
    is_nested_call = bool(call_stack)
    nested_depth = len(call_stack)
    if is_nested_call and tool_name in _NESTED_TOOL_BLOCKED_NAMES:
        return _result(
            (
                "Nested tool call blocked: this tool is not allowed to run as a "
                f"nested call: {tool_name}."
            ),
            True,
            metadata={
                "nestedToolBlocked": "blocked_tool",
                "nested": True,
                "nestedDepth": nested_depth,
                "parentToolName": call_stack[-1] if call_stack else None,
            },
        )

    try:
        parsed_input = tool.input_model.model_validate(tool_input)
    except Exception as exc:
        log.warning("invalid input for %s: %s", tool_name, exc)
        return _result(f"Invalid input for {tool_name}: {exc}", True)

    # Permission check
    is_remote_tool = is_remote_workspace_tool(
        tool_metadata,
        tool_name,
    )
    _file_path = (
        None
        if is_remote_tool
        else _resolve_permission_file_path(context.cwd, tool_input, parsed_input)
    )
    _command = _extract_permission_command(tool_input, parsed_input)
    decision = context.permission_checker.evaluate(
        tool_name,
        is_read_only=tool.is_read_only(parsed_input),
        file_path=_file_path,
        command=_command,
    )
    if not decision.allowed:
        if decision.requires_confirmation and context.permission_prompt is not None:
            if context.hook_executor is not None:
                await context.hook_executor.execute(
                    HookEvent.NOTIFICATION,
                    {"event": HookEvent.NOTIFICATION.value,
                     "notification_type": "permission_prompt",
                     "tool_name": tool_name, "reason": decision.reason},
                )
            confirmed = await context.permission_prompt(tool_name, decision.reason)
            if not confirmed:
                return _result(decision.reason or f"Permission denied for {tool_name}", True)
        else:
            return _result(decision.reason or f"Permission denied for {tool_name}", True)

    # Pre-tool hook. Expensive audit/HITL work runs only after cheap RBAC.
    if context.hook_executor is not None:
        pre = await context.hook_executor.execute(
            HookEvent.PRE_TOOL_USE,
            {"tool_name": tool_name, "tool_input": tool_input,
             "event": HookEvent.PRE_TOOL_USE.value},
        )
        if pre.blocked:
            return _result(pre.reason or f"pre_tool_use hook blocked {tool_name}", True)

    # 실행
    pre_change_metadata = (
        {}
        if is_remote_tool
        else _capture_file_change_snapshot(
            context.cwd,
            tool_name,
            _file_path,
        )
    )
    t0 = time.monotonic()
    nested_seen_signatures = set(
        str(item)
        for item in tool_metadata.get("nested_tool_seen", ())
        if item is not None
    )
    nested_parent_call_count = 0
    nested_total_counter = tool_metadata.get("_nested_tool_total_counter")
    if not isinstance(nested_total_counter, dict):
        nested_total_counter = {
            "count": _metadata_int(tool_metadata, "nested_tool_total_count", 0)
        }
    max_calls_per_parent = _metadata_int(
        tool_metadata,
        "nested_tool_max_calls_per_parent",
        _DEFAULT_NESTED_TOOL_MAX_CALLS_PER_PARENT,
    )
    max_total_calls = _metadata_int(
        tool_metadata,
        "nested_tool_max_total_calls",
        _DEFAULT_NESTED_TOOL_MAX_TOTAL_CALLS,
    )
    tool_context_metadata = {
        "tool_registry": context.tool_registry,
        "active_registry": context.tool_registry,
        "ask_user_prompt": context.ask_user_prompt,
        **tool_metadata,
    }
    nested_tool_events: list[dict[str, object]] = []
    tool_context_metadata["_nested_tool_events"] = nested_tool_events
    try:
        async def _nested_tool_invoker(
            nested_tool_name: str,
            nested_tool_input: dict[str, object] | None = None,
        ) -> ToolResult:
            nonlocal nested_parent_call_count
            nested_payload = dict(nested_tool_input or {})
            nested_signature = _nested_tool_signature(
                nested_tool_name,
                nested_payload,
            )
            nested_event_metadata = {
                "nested": True,
                "parentToolName": tool_name,
                "nestedDepth": len(call_stack) + 1,
                "callStack": [*call_stack, tool_name],
            }
            if nested_signature in nested_seen_signatures:
                return ToolResult(
                    output=(
                        "Nested tool call blocked: repeated same tool and "
                        f"arguments for {nested_tool_name}."
                    ),
                    is_error=True,
                    metadata={
                        **nested_event_metadata,
                        "nestedToolBlocked": "duplicate_call",
                    },
                )
            if nested_parent_call_count >= max_calls_per_parent:
                return ToolResult(
                    output=(
                        "Nested tool call blocked: maximum nested calls per "
                        f"parent ({max_calls_per_parent}) exceeded."
                    ),
                    is_error=True,
                    metadata={
                        **nested_event_metadata,
                        "nestedToolBlocked": "max_calls_per_parent_exceeded",
                    },
                )
            if int(nested_total_counter.get("count", 0)) >= max_total_calls:
                return ToolResult(
                    output=(
                        "Nested tool call blocked: maximum total nested calls "
                        f"({max_total_calls}) exceeded."
                    ),
                    is_error=True,
                    metadata={
                        **nested_event_metadata,
                        "nestedToolBlocked": "max_total_calls_exceeded",
                    },
                )
            nested_seen_signatures.add(nested_signature)
            nested_parent_call_count += 1
            nested_total_counter["count"] = int(nested_total_counter.get("count", 0)) + 1
            nested_tool_use_id = f"nested_{uuid4().hex}"
            nested_tool_events.append(
                {
                    "type": "ToolExecutionStarted",
                    "toolName": nested_tool_name,
                    "toolUseId": nested_tool_use_id,
                    "toolInput": nested_payload,
                    "metadata": nested_event_metadata,
                }
            )
            nested_metadata = {
                **tool_metadata,
                "nested_tool_call_stack": (*call_stack, tool_name),
                "nested_tool_parent": tool_name,
                "nested_tool_seen": tuple(nested_seen_signatures),
                "_nested_tool_total_counter": nested_total_counter,
            }
            nested_context = replace(
                context,
                tool_metadata=nested_metadata,
            )
            nested_executed = await _execute_tool_call(
                nested_context,
                nested_tool_name,
                nested_tool_use_id,
                nested_payload,
            )
            nested_tool_events.append(
                {
                    "type": "ToolExecutionCompleted",
                    "toolName": nested_tool_name,
                    "toolUseId": nested_tool_use_id,
                    "toolInput": nested_payload,
                    "isError": nested_executed.result.is_error,
                    "outputPreview": _limit_preview(nested_executed.result.content, 500),
                    "metadata": {
                        **nested_event_metadata,
                        **nested_executed.metadata,
                    },
                }
            )
            return ToolResult(
                output=nested_executed.result.content,
                is_error=nested_executed.result.is_error,
                metadata={
                    "nestedToolName": nested_tool_name,
                    **nested_executed.metadata,
                },
            )

        result = await tool.execute(
            parsed_input,
            ToolExecutionContext(
                cwd=context.cwd,
                metadata=tool_context_metadata,
                hook_executor=context.hook_executor,
                run_id=tool_metadata.get("run_id"),
                tool_draft_id=tool_metadata.get("tool_draft_id"),
                tool_invoker=_nested_tool_invoker,
            ),
        )
    except Exception as exc:
        log.warning(
            "tool failed: name=%s id=%s error=%s",
            tool_name,
            tool_use_id,
            exc,
        )
        result = ToolResult(
            output=(
                f"도구 실행 실패: {tool_name}: "
                f"{type(exc).__name__}: {exc}"
            ),
            is_error=True,
        )
    elapsed = time.monotonic() - t0
    output_text = stringify_tool_output(result.output)
    log.debug("executed %s in %.2fs err=%s output_len=%d",
              tool_name, elapsed, result.is_error, len(output_text))

    inline_output, artifact_path = _offload_tool_output_if_needed(
        tool_name=tool_name, tool_use_id=tool_use_id, output=output_text,
    )
    if artifact_path:
        _remember_active_artifact(context.tool_metadata, str(artifact_path))

    tool_result = ToolResultBlock(
        tool_use_id=tool_use_id,
        content=inline_output,
        is_error=result.is_error,
    )
    event_metadata: dict[str, object] = dict(result.metadata or {})
    if is_nested_call:
        event_metadata.update(
            {
                "nested": True,
                "parentToolName": call_stack[-1] if call_stack else None,
                "nestedDepth": nested_depth,
                "callStack": list(call_stack),
            }
        )
    if nested_tool_events:
        event_metadata["nestedToolCalls"] = nested_tool_events
    if pre_change_metadata:
        event_metadata.update(pre_change_metadata)

    # Post-tool hook
    if context.hook_executor is not None:
        payload = {
            "tool_name": tool_name,
            "tool_input": tool_input,
            "tool_output": tool_result.content,
            "tool_result": tool_result,
            "is_error": tool_result.is_error,
            "tool_is_error": tool_result.is_error,
            "event": HookEvent.POST_TOOL_USE.value,
        }
        await context.hook_executor.execute(HookEvent.POST_TOOL_USE, payload)
        final_output = payload.get("tool_output", tool_result.content)
        if final_output != tool_result.content:
            tool_result = ToolResultBlock(
                tool_use_id=tool_use_id,
                content=stringify_tool_output(final_output),
                is_error=tool_result.is_error,
            )

    _record_tool_carryover(
        context.tool_metadata,
        tool_name=tool_name,
        tool_input=tool_input,
        tool_output=tool_result.content,
        is_error=tool_result.is_error,
        resolved_file_path=None if is_remote_tool else _file_path,
    )
    return ExecutedToolCall(result=tool_result, metadata=event_metadata)


def _capture_file_change_snapshot(
    cwd: Path,
    tool_name: str,
    resolved_file_path: str | None,
) -> dict[str, object]:
    if tool_name not in {"write_file", "edit_file"} or not resolved_file_path:
        return {}

    path = Path(resolved_file_path)
    changed_file: dict[str, object] = {
        "path": str(path),
        "relative_path": _relative_to_cwd(cwd, path),
        "existed_before": path.exists(),
    }
    if not path.exists():
        changed_file["old_content"] = ""
        return {"changed_file": changed_file}

    try:
        size = path.stat().st_size
    except OSError as exc:
        return {
            "changed_file": changed_file,
            "changed_file_skipped_reason": f"stat_failed: {exc}",
        }

    if size > _DIFF_SNAPSHOT_MAX_BYTES:
        return {
            "changed_file": changed_file,
            "changed_file_skipped_reason": "file_too_large",
        }

    try:
        changed_file["old_content"] = path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        return {
            "changed_file": changed_file,
            "changed_file_skipped_reason": "non_utf8_file",
        }
    except OSError as exc:
        return {
            "changed_file": changed_file,
            "changed_file_skipped_reason": f"read_failed: {exc}",
        }

    return {"changed_file": changed_file}


def _relative_to_cwd(cwd: Path, path: Path) -> str:
    try:
        return str(path.resolve().relative_to(cwd.resolve()))
    except ValueError:
        return str(path)


def _assistant_text(message: ConversationMessage) -> str:
    return "".join(
        block.text for block in message.content
        if isinstance(block, TextBlock) and isinstance(block.text, str)
    )


def _current_user_goal(tool_metadata: dict[str, object] | None) -> str | None:
    if not isinstance(tool_metadata, dict):
        return None
    state = tool_metadata.get("task_focus_state")
    if not isinstance(state, dict):
        return None
    goal = state.get("goal")
    return str(goal) if goal else None


def _semantic_loop_evaluator_prompt() -> str:
    return (
        "You classify whether an agent loop should continue after an assistant "
        "message ended without tool calls. Return JSON only with keys: "
        "action, confidence, reason, next_prompt. action must be one of "
        "continue, stop, ask_user, verify, retry_tool_error. Continue only when "
        "the assistant clearly promised immediate work that still requires a "
        "tool or follow-up model turn. Stop when the answer appears final. "
        "Use ask_user when the assistant requested confirmation, approval, or a choice."
    )


async def _semantic_loop_evaluator(
    *,
    context: QueryContext,
    decision_context: LoopDecisionContext,
    fallback: LoopContinuationDecision,
) -> LoopContinuationDecision | None:
    try:
        timeout_seconds = max(
            0.5,
            float(os.getenv("THESEUS_AGENT_LOOP_SEMANTIC_TIMEOUT_SECONDS", "4")),
        )
    except (TypeError, ValueError):
        timeout_seconds = 4.0
    payload = {
        "mode": decision_context.mode,
        "plan_phase": decision_context.plan_phase,
        "stop_reason": decision_context.stop_reason,
        "assistant_text": decision_context.assistant_text[:2500],
        "tool_error": decision_context.tool_error,
        "user_goal": decision_context.user_goal,
        "fallback": fallback.to_metadata(),
    }
    final_text = ""
    request = ApiMessageRequest(
        model=context.model,
        messages=[
            ConversationMessage.from_user_text(
                "Classify this agent loop state:\n"
                + json.dumps(payload, ensure_ascii=False, indent=2)
            )
        ],
        system_prompt=_semantic_loop_evaluator_prompt(),
        max_tokens=256,
        tools=[],
        debug_context={
            **_llm_debug_context(context.tool_metadata),
            "loop_decision_evaluator": True,
        },
    )
    async with asyncio.timeout(timeout_seconds):
        async for event in context.api_client.stream_message(request):
            if isinstance(event, ApiMessageCompleteEvent):
                final_text = _assistant_text(event.message)
    return parse_semantic_decision_payload(final_text, fallback)


async def _decide_auto_continue_after_assistant(
    *,
    context: QueryContext,
    final_message: ConversationMessage,
    stop_reason: str | None,
    tool_call_count: int,
    auto_continue_count: int,
) -> LoopContinuationDecision:
    mode = str((context.tool_metadata or {}).get("agent_mode") or "").upper()
    plan_phase = str((context.tool_metadata or {}).get("plan_phase") or "")
    decision_context = LoopDecisionContext(
        mode=mode,
        plan_phase=plan_phase,
        stop_reason=stop_reason,
        assistant_text=_assistant_text(final_message),
        tool_call_count=tool_call_count,
        auto_continue_count=auto_continue_count,
        available_tools=bool(context.tool_registry.to_api_schema()),
        user_goal=_current_user_goal(context.tool_metadata),
        max_auto_continue=AGENT_AUTO_CONTINUE_MAX,
    )
    return await decide_loop_continuation(
        decision_context,
        semantic_evaluator=lambda ctx, fallback: _semantic_loop_evaluator(
            context=context,
            decision_context=ctx,
            fallback=fallback,
        ),
    )


# ── run_query 루프 ────────────────────────────────────────────

async def run_query(
    context: QueryContext,
    messages: list[ConversationMessage],
) -> AsyncGenerator[tuple[StreamEvent, UsageSnapshot | None], None]:
    """Tool-aware 대화 루프.

    모델이 도구 요청을 멈출 때까지 실행하며 StreamEvent를 yield합니다.
    Auto-compact는 theseus_engine.core.context_compressor에 위임합니다.
    """
    from theseus_engine.core.context_compressor import (
        needs_compression,
        maybe_compress,
    )

    effective_max_tokens = _bounded_completion_tokens(
        context.max_tokens, context.context_window_tokens,
    )
    reactive_compact_attempted = False
    reported_token_clamp = False

    turn_count = 0
    auto_continue_count = 0
    pending_auto_continue: ConversationMessage | None = None
    while context.max_turns is None or turn_count < context.max_turns:
        turn_count += 1
        yield AgentLoopStatus(
            phase="model_start",
            turn=turn_count,
            message=f"Model turn {turn_count} started.",
        ), None

        if effective_max_tokens != context.max_tokens and not reported_token_clamp:
            reported_token_clamp = True
            yield StatusEvent(
                message=(
                    f"max_tokens={context.max_tokens} exceeds safe cap; "
                    f"using {effective_max_tokens}."
                )
            ), None

        max_compact_messages = (
            context.auto_compact_threshold_tokens
            or DEFAULT_AUTO_COMPACT_MESSAGES
        )
        max_compact_messages = max(1, int(max_compact_messages))

        # Auto-compact 체크
        if needs_compression(messages, max_messages=max_compact_messages):
            yield StatusEvent(message="Auto-compacting conversation memory…"), None
            compacted_messages, _ = await maybe_compress(
                messages,
                max_messages=max_compact_messages,
                api_client=context.api_client,
                model=context.model,
            )
            messages[:] = compacted_messages

        final_message: ConversationMessage | None = None
        final_stop_reason: str | None = None
        usage = UsageSnapshot()
        request_messages = messages
        if pending_auto_continue is not None:
            request_messages = [*messages, pending_auto_continue]
            pending_auto_continue = None

        try:
            async for event in context.api_client.stream_message(
                ApiMessageRequest(
                    model=context.model,
                    messages=request_messages,
                    system_prompt=context.system_prompt,
                    max_tokens=effective_max_tokens,
                    tools=context.tool_registry.to_api_schema(),
                    debug_context=_llm_debug_context(context.tool_metadata),
                )
            ):
                if isinstance(event, ApiTextDeltaEvent):
                    yield AssistantTextDelta(text=event.text), None
                elif isinstance(event, ApiRetryEvent):
                    yield StatusEvent(
                        message=(
                            f"Request failed; retrying in {event.delay_seconds:.1f}s "
                            f"(attempt {event.attempt + 1} of {event.max_attempts}): {event.message}"
                        )
                    ), None
                elif isinstance(event, ApiMessageCompleteEvent):
                    final_message = event.message
                    usage = event.usage
                    final_stop_reason = event.stop_reason

        except Exception as exc:
            if _is_completion_token_limit_error(exc):
                limit = _extract_completion_token_limit(exc)
                if limit and effective_max_tokens > limit:
                    prev = effective_max_tokens
                    effective_max_tokens = limit
                    yield StatusEvent(
                        message=f"Model rejected max_tokens={prev}; retrying with {effective_max_tokens}."
                    ), None
                    turn_count = max(0, turn_count - 1)
                    continue
            if not reactive_compact_attempted and _is_prompt_too_long_error(exc):
                reactive_compact_attempted = True
                yield StatusEvent(message="Prompt too long; compacting and retrying…"), None
                compacted_messages, _ = await maybe_compress(
                    messages,
                    keep_recent=4,
                    api_client=context.api_client,
                    model=context.model,
                )
                messages[:] = compacted_messages
                continue
            error_msg = str(exc)
            if any(kw in error_msg.lower() for kw in ("connect", "timeout", "network")):
                yield ErrorEvent(
                    message=f"Network error: {error_msg}. Check your internet connection.",
                    recoverable=True,
                    error_type="llm_api_error",
                ), None
            else:
                yield ErrorEvent(
                    message=f"API error: {error_msg}",
                    recoverable=True,
                    error_type="llm_api_error",
                ), None
            return

        if final_message is None:
            raise RuntimeError("Model stream finished without a final message")

        if final_message.role == "assistant" and final_message.is_effectively_empty():
            log.warning("dropping empty assistant message")
            yield AgentLoopStatus(
                phase="error",
                turn=turn_count,
                message="Model returned an empty assistant message.",
                is_error=True,
            ), usage
            yield ErrorEvent(
                message="Model returned an empty assistant message. Turn ignored.",
                recoverable=False,
                error_type="llm_api_error",
            ), usage
            return

        messages.append(final_message)
        tool_calls = final_message.tool_uses
        yield AgentLoopStatus(
            phase="model_complete",
            turn=turn_count,
            message=(
                f"Model turn {turn_count} completed with {len(tool_calls)} tool call(s)."
            ),
            tool_count=len(tool_calls),
        ), usage
        yield AssistantTurnComplete(message=final_message, usage=usage), usage

        # PLAN DRAFTING 단계에서 JSON 블록 감지 → PlanDraftedEvent 발행
        if context.is_plan_drafting:
            full_text = "".join(
                b.text for b in final_message.content
                if hasattr(b, "text") and isinstance(b.text, str)
            )
            plan_json = extract_plan_json(full_text)
            if plan_json is not None:
                yield PlanDraftedEvent(
                    raw_markdown=full_text,
                    structured_plan=plan_json,
                ), None

        if not tool_calls:
            loop_decision = await _decide_auto_continue_after_assistant(
                context=context,
                final_message=final_message,
                stop_reason=final_stop_reason,
                tool_call_count=len(tool_calls),
                auto_continue_count=auto_continue_count,
            )
            if loop_decision.should_resume:
                auto_continue_count += 1
                pending_auto_continue = ConversationMessage.from_user_text(
                    loop_decision.resume_prompt or AUTO_CONTINUE_PROMPT
                )
                yield AgentLoopStatus(
                    phase="waiting",
                    turn=turn_count,
                    message="루프 판정기가 추가 진행이 필요하다고 판단해 agent loop를 이어갑니다.",
                    tool_count=0,
                    metadata=loop_decision.to_metadata(),
                ), usage
                yield StatusEvent(
                    message="루프 판정기가 추가 진행이 필요하다고 판단해 agent loop를 이어갑니다.",
                    metadata={
                        **loop_decision.to_metadata(),
                        "stopReason": final_stop_reason,
                        "autoContinueCount": auto_continue_count,
                        "maxAutoContinue": AGENT_AUTO_CONTINUE_MAX,
                    },
                ), usage
                continue
            if context.hook_executor is not None:
                await context.hook_executor.execute(
                    HookEvent.STOP,
                    {
                        "event": HookEvent.STOP.value,
                        "stop_reason": "tool_uses_empty",
                        "model_stop_reason": final_stop_reason,
                        "loop_decision": loop_decision.to_metadata(),
                    },
                )
            yield AgentLoopStatus(
                phase="complete",
                turn=turn_count,
                message="Agent loop completed without pending tool calls.",
                tool_count=0,
                metadata=loop_decision.to_metadata(),
            ), usage
            return

        # Tool 실행
        yield AgentLoopStatus(
            phase="waiting",
            turn=turn_count,
            message=f"Executing {len(tool_calls)} tool call(s).",
            tool_count=len(tool_calls),
        ), None

        if len(tool_calls) == 1:
            tc = tool_calls[0]
            yield AgentLoopStatus(
                phase="tool_start",
                turn=turn_count,
                tool_name=tc.name,
                tool_use_id=tc.id,
                message=f"Tool started: {tc.name}",
            ), None
            yield ToolExecutionStarted(
                tool_name=tc.name,
                tool_input=tc.input,
                tool_use_id=tc.id,
            ), None
            executed = await _execute_tool_call(context, tc.name, tc.id, tc.input)
            result = executed.result
            yield AgentLoopStatus(
                phase="tool_complete",
                turn=turn_count,
                tool_name=tc.name,
                tool_use_id=tc.id,
                message=f"Tool completed: {tc.name}",
                is_error=result.is_error,
            ), None
            yield ToolExecutionCompleted(
                tool_name=tc.name,
                output=result.content,
                is_error=result.is_error,
                tool_use_id=tc.id,
                tool_input=tc.input,
                metadata=executed.metadata,
            ), None
            tool_results = [result]
        else:
            for tc in tool_calls:
                yield AgentLoopStatus(
                    phase="tool_start",
                    turn=turn_count,
                    tool_name=tc.name,
                    tool_use_id=tc.id,
                    message=f"Tool started: {tc.name}",
                ), None
                yield ToolExecutionStarted(
                    tool_name=tc.name,
                    tool_input=tc.input,
                    tool_use_id=tc.id,
                ), None

            raw_results = await asyncio.gather(
                *[_execute_tool_call(context, tc.name, tc.id, tc.input)
                  for tc in tool_calls],
                return_exceptions=True,
            )
            tool_results = []
            executed_results: list[ExecutedToolCall] = []
            for tc, executed in zip(tool_calls, raw_results):
                if isinstance(executed, BaseException):
                    log.exception("tool raised: name=%s id=%s", tc.name, tc.id, exc_info=executed)
                    executed = ExecutedToolCall(
                        result=ToolResultBlock(
                            tool_use_id=tc.id,
                            content=f"Tool {tc.name} failed: {type(executed).__name__}: {executed}",
                            is_error=True,
                        ),
                        metadata={},
                    )
                executed_results.append(executed)
                tool_results.append(executed.result)

            for tc, executed in zip(tool_calls, executed_results):
                result = executed.result
                yield AgentLoopStatus(
                    phase="tool_complete",
                    turn=turn_count,
                    tool_name=tc.name,
                    tool_use_id=tc.id,
                    message=f"Tool completed: {tc.name}",
                    is_error=result.is_error,
                ), None
                yield ToolExecutionCompleted(
                    tool_name=tc.name,
                    output=result.content,
                    is_error=result.is_error,
                    tool_use_id=tc.id,
                    tool_input=tc.input,
                    metadata=executed.metadata,
                ), None

        messages.append(ConversationMessage(role="user", content=tool_results))

    if context.max_turns is not None:
        yield AgentLoopStatus(
            phase="error",
            turn=turn_count,
            message=f"Agent loop exceeded max turns: {context.max_turns}.",
            is_error=True,
        ), None
        raise MaxTurnsExceeded(context.max_turns)
    raise RuntimeError("Query loop exited without completing")


# ── QueryEngine ───────────────────────────────────────────────

class QueryEngine:
    """Theseus-native 대화 엔진.

    QueryEngine public 인터페이스를 유지합니다.
    """

    def __init__(
        self,
        *,
        api_client: SupportsStreamingMessages,
        tool_registry: ToolRegistry,
        permission_checker: Any,
        cwd: str | Path,
        model: str,
        system_prompt: str,
        max_tokens: int = 32768,
        context_window_tokens: int | None = None,
        auto_compact_threshold_tokens: int | None = None,
        max_turns: int | None = 30,
        permission_prompt: PermissionPrompt | None = None,
        ask_user_prompt: AskUserPrompt | None = None,
        hook_executor: Any | None = None,
        tool_metadata: dict[str, object] | None = None,
        skill_injection_config: SkillInjectionConfig | None = None,
    ) -> None:
        self._api_client = api_client
        self._tool_registry = tool_registry
        self._permission_checker = permission_checker
        self._cwd = Path(cwd).resolve()
        self._model = model
        self._system_prompt = system_prompt
        self._max_tokens = max_tokens
        self._context_window_tokens = context_window_tokens
        self._auto_compact_threshold_tokens = auto_compact_threshold_tokens
        self._max_turns = max_turns
        self._permission_prompt = permission_prompt
        self._ask_user_prompt = ask_user_prompt
        self._hook_executor = hook_executor
        self._tool_metadata: dict[str, object] = tool_metadata or {}
        self._skill_injection_config = skill_injection_config
        self._messages: list[ConversationMessage] = []
        self._total_usage = UsageSnapshot()
        self._is_plan_drafting: bool = False

    # ── Properties ───────────────────────────────────────────

    @property
    def messages(self) -> list[ConversationMessage]:
        return list(self._messages)

    @property
    def max_turns(self) -> int | None:
        return self._max_turns

    @property
    def api_client(self) -> SupportsStreamingMessages:
        return self._api_client

    @property
    def model(self) -> str:
        return self._model

    @property
    def system_prompt(self) -> str:
        return self._system_prompt

    @property
    def tool_metadata(self) -> dict[str, object]:
        return self._tool_metadata

    @property
    def total_usage(self) -> UsageSnapshot:
        return UsageSnapshot(
            input_tokens=self._total_usage.input_tokens,
            output_tokens=self._total_usage.output_tokens,
        )

    # ── Mutators ─────────────────────────────────────────────

    def clear(self) -> None:
        self._messages.clear()

    def set_system_prompt(self, prompt: str) -> None:
        self._system_prompt = prompt

    def set_model(self, model: str) -> None:
        self._model = model

    def set_api_client(self, api_client: SupportsStreamingMessages) -> None:
        self._api_client = api_client

    def set_max_turns(self, max_turns: int | None) -> None:
        self._max_turns = None if max_turns is None else max(1, int(max_turns))

    def set_permission_checker(self, checker: Any) -> None:
        self._permission_checker = checker

    def set_tool_registry(self, registry: ToolRegistry) -> None:
        """Replace the active tool registry after mode/phase changes."""
        self._tool_registry = registry
        self._tool_metadata["active_registry"] = registry
        if self._hook_executor is not None and hasattr(self._hook_executor, "_active_registry"):
            self._hook_executor._active_registry = registry

    def set_plan_drafting(self, value: bool) -> None:
        """PLAN DRAFTING 단계 여부를 설정합니다.

        True로 설정하면 다음 submit_message()부터 LLM 응답에서
        JSON 블록을 감지하여 PlanDraftedEvent를 yield합니다.
        """
        self._is_plan_drafting = value

    def load_messages(self, messages: list[ConversationMessage]) -> None:
        self._messages = list(messages)

    def has_pending_continuation(self) -> bool:
        if not self._messages:
            return False
        last = self._messages[-1]
        if last.role != "user":
            return False
        if not any(isinstance(b, ToolResultBlock) for b in last.content):
            return False
        for msg in reversed(self._messages[:-1]):
            if msg.role != "assistant":
                continue
            return bool(msg.tool_uses)
        return False

    # ── Core ─────────────────────────────────────────────────

    def _make_context(self, *, system_prompt: str | None = None) -> QueryContext:
        return QueryContext(
            api_client=self._api_client,
            tool_registry=self._tool_registry,
            permission_checker=self._permission_checker,
            cwd=self._cwd,
            model=self._model,
            system_prompt=system_prompt or self._system_prompt,
            max_tokens=self._max_tokens,
            context_window_tokens=self._context_window_tokens,
            auto_compact_threshold_tokens=self._auto_compact_threshold_tokens,
            max_turns=self._max_turns,
            permission_prompt=self._permission_prompt,
            ask_user_prompt=self._ask_user_prompt,
            hook_executor=self._hook_executor,
            tool_metadata=self._tool_metadata,
            is_plan_drafting=self._is_plan_drafting,
        )

    def _build_effective_system_prompt(self, user_prompt: str) -> str:
        if self._skill_injection_config is None:
            self._tool_metadata["active_skills"] = []
            return self._system_prompt
        if not user_prompt.strip():
            self._tool_metadata["active_skills"] = []
            return self._system_prompt

        mode = self._tool_metadata.get("agent_mode")
        try:
            effective_prompt, selected = apply_skill_injection(
                system_prompt=self._system_prompt,
                cwd=self._cwd,
                user_prompt=user_prompt,
                mode=str(mode) if mode is not None else None,
                config=self._skill_injection_config,
            )
        except Exception as exc:
            log.warning("[SkillInjection] failed: %s", exc)
            self._tool_metadata["active_skills"] = []
            return self._system_prompt

        self._tool_metadata["active_skills"] = [
            item.to_metadata() for item in selected
        ]
        return effective_prompt

    def _record_usage(self, usage: UsageSnapshot | None) -> None:
        if usage is None:
            return
        self._total_usage.input_tokens += usage.input_tokens
        self._total_usage.output_tokens += usage.output_tokens

    async def submit_message(
        self, prompt: str | ConversationMessage
    ) -> AsyncGenerator[StreamEvent, None]:
        user_message = (
            prompt
            if isinstance(prompt, ConversationMessage)
            else ConversationMessage.from_user_text(prompt)
        )
        if user_message.text.strip():
            remember_user_goal(self._tool_metadata, user_message.text)

        self._messages.append(user_message)

        if self._hook_executor is not None:
            await self._hook_executor.execute(
                HookEvent.USER_PROMPT_SUBMIT,
                {"event": HookEvent.USER_PROMPT_SUBMIT.value,
                 "prompt": user_message.text},
            )

        effective_system_prompt = self._build_effective_system_prompt(user_message.text)
        active_skills = self._tool_metadata.get("active_skills")
        if isinstance(active_skills, list) and active_skills:
            skill_names = [
                (
                    str(item.get("name") or item.get("path") or "skill")
                    if isinstance(item, dict)
                    else str(item)
                )
                for item in active_skills
            ]
            if skill_names:
                yield StatusEvent(
                    message=f"Active skills: {', '.join(skill_names)}",
                    metadata={"active_skills": active_skills},
                )

        context = self._make_context(system_prompt=effective_system_prompt)
        query_messages = list(self._messages)

        try:
            async for event, usage in run_query(context, query_messages):
                if isinstance(event, AssistantTurnComplete):
                    self._record_usage(usage)
                    self._messages = list(query_messages)
                yield event
        except MaxTurnsExceeded as exc:
            yield ErrorEvent(
                message=str(exc),
                recoverable=False,
                error_type="max_turns_exceeded",
            )

    async def continue_pending(
        self, *, max_turns: int | None = None
    ) -> AsyncIterator[StreamEvent]:
        context = self._make_context()
        if max_turns is not None:
            context.max_turns = max_turns
        async for event, usage in run_query(context, self._messages):
            if isinstance(event, AssistantTurnComplete):
                self._record_usage(usage)
            yield event
