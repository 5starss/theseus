from __future__ import annotations

import hashlib
import json
import logging
import re
from pathlib import Path
from typing import Any, Iterable

from src.config import settings
from src.tool_plan.schemas import ToolPlanRequestEvent, ToolPlanResult

logger = logging.getLogger(__name__)

CORE_ROOT = Path(__file__).resolve().parents[1]


def _resolve_replay_path() -> Path:
    configured = Path(settings.THESEUS_DEMO_REPLAY_PATH)
    if configured.is_absolute():
        return configured
    return CORE_ROOT / configured


def _load_replay_config() -> dict[str, Any]:
    if not settings.THESEUS_DEMO_REPLAY_ENABLED:
        return {}

    path = _resolve_replay_path()
    if not path.exists():
        logger.warning("Demo replay file does not exist: %s", path)
        return {}

    try:
        import yaml

        loaded = yaml.safe_load(path.read_text(encoding="utf-8"))
    except Exception as exc:
        logger.warning("Demo replay file load failed: %s", exc, exc_info=True)
        return {}

    if not isinstance(loaded, dict):
        logger.warning("Demo replay file must contain a YAML mapping: %s", path)
        return {}
    return loaded


def _as_list(value: Any) -> list[Any]:
    if value is None:
        return []
    if isinstance(value, list):
        return value
    if isinstance(value, tuple):
        return list(value)
    return [value]


def _normalize_mode(value: Any) -> str:
    raw = getattr(value, "name", None) or getattr(value, "value", None) or value
    text = str(raw or "").strip()
    if text.lower() == "ask":
        return "ASK"
    if text.lower() == "agent":
        return "AGENT"
    if text.lower() == "plan":
        return "PLAN"
    return text.upper()


def _normalize_text(value: Any, *, case_sensitive: bool) -> str:
    text = str(value or "")
    return text if case_sensitive else text.casefold()


def _match_text(prompt: str, matcher: dict[str, Any]) -> bool:
    case_sensitive = bool(matcher.get("case_sensitive", matcher.get("caseSensitive", False)))
    haystack = _normalize_text(prompt, case_sensitive=case_sensitive)
    matched = False

    exact_values = _as_list(matcher.get("exact"))
    if exact_values:
        matched = any(
            haystack == _normalize_text(value, case_sensitive=case_sensitive)
            for value in exact_values
        )

    contains_values = [
        *_as_list(matcher.get("contains")),
        *_as_list(matcher.get("contains_any")),
        *_as_list(matcher.get("containsAny")),
    ]
    if contains_values:
        matched = matched or any(
            _normalize_text(value, case_sensitive=case_sensitive) in haystack
            for value in contains_values
        )

    contains_all_values = [
        *_as_list(matcher.get("contains_all")),
        *_as_list(matcher.get("containsAll")),
    ]
    if contains_all_values:
        matched = matched or all(
            _normalize_text(value, case_sensitive=case_sensitive) in haystack
            for value in contains_all_values
        )

    regex_values = _as_list(matcher.get("regex"))
    if regex_values:
        flags = 0 if case_sensitive else re.IGNORECASE
        matched = matched or any(
            re.search(str(pattern), prompt, flags=flags) is not None
            for pattern in regex_values
        )

    return matched


def _match_id_constraint(
    matcher: dict[str, Any],
    *,
    key: str,
    actual: Any,
) -> bool:
    expected = matcher.get(key)
    if expected is None:
        return True
    expected_values = {str(value) for value in _as_list(expected)}
    return str(actual) in expected_values


def _entry_matches(
    entry: dict[str, Any],
    *,
    prompt: str,
    mode: Any,
    user_id: Any = None,
    project_id: Any = None,
    remote_workspace_id: Any = None,
) -> bool:
    if entry.get("enabled", True) is False:
        return False

    matcher = entry.get("match") or {}
    if not isinstance(matcher, dict):
        matcher = {}

    mode_values = [
        *_as_list(entry.get("mode")),
        *_as_list(entry.get("modes")),
        *_as_list(matcher.get("mode")),
        *_as_list(matcher.get("modes")),
    ]
    if mode_values:
        expected_modes = {_normalize_mode(value) for value in mode_values}
        if _normalize_mode(mode) not in expected_modes:
            return False

    if not _match_id_constraint(matcher, key="user_id", actual=user_id):
        return False
    if not _match_id_constraint(matcher, key="userId", actual=user_id):
        return False
    if not _match_id_constraint(matcher, key="project_id", actual=project_id):
        return False
    if not _match_id_constraint(matcher, key="projectId", actual=project_id):
        return False
    if not _match_id_constraint(matcher, key="remote_workspace_id", actual=remote_workspace_id):
        return False
    if not _match_id_constraint(matcher, key="remoteWorkspaceId", actual=remote_workspace_id):
        return False

    remote_policy = None
    for key in ("remote", "remote_workspace", "remoteWorkspace"):
        if key in matcher:
            remote_policy = matcher[key]
            break
    if remote_policy is not None:
        normalized_policy = str(remote_policy).strip().lower()
        has_remote = remote_workspace_id is not None
        if normalized_policy in {"any", "optional", "*"}:
            pass
        elif normalized_policy in {"required", "present", "true", "remote"} and not has_remote:
            return False
        elif normalized_policy in {"none", "absent", "false", "local"} and has_remote:
            return False

    return _match_text(prompt, matcher)


def _entries(config: dict[str, Any], *keys: str) -> Iterable[dict[str, Any]]:
    for key in keys:
        raw_entries = config.get(key)
        if not isinstance(raw_entries, list):
            continue
        for entry in raw_entries:
            if isinstance(entry, dict):
                yield entry


def find_chat_replay(
    *,
    prompt: str,
    mode: Any,
    user_id: Any = None,
    project_id: Any = None,
    remote_workspace_id: Any = None,
) -> dict[str, Any] | None:
    config = _load_replay_config()
    for entry in _entries(config, "chat_replays", "chat"):
        if _entry_matches(
            entry,
            prompt=prompt,
            mode=mode,
            user_id=user_id,
            project_id=project_id,
            remote_workspace_id=remote_workspace_id,
        ):
            return entry
    return None


def find_tool_plan_replay(event: ToolPlanRequestEvent) -> dict[str, Any] | None:
    config = _load_replay_config()
    for entry in _entries(config, "plan_replays", "tool_plan_replays", "plans"):
        if _entry_matches(
            entry,
            prompt=getattr(event, "prompt", ""),
            mode=getattr(event, "mode", "PLAN"),
            user_id=getattr(event, "requested_by_user_id", None),
            project_id=getattr(event, "project_id", None),
            remote_workspace_id=getattr(event, "remote_workspace_id", None),
        ):
            return entry
    return None


def _stringify(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        return value
    return json.dumps(value, ensure_ascii=False, default=str)


def _event_data(item: dict[str, Any]) -> dict[str, Any]:
    return item.get("data") if isinstance(item.get("data"), dict) else item


def _normalize_chat_events(events: list[Any]) -> list[dict[str, Any]]:
    normalized: list[dict[str, Any]] = []
    for raw in events:
        if not isinstance(raw, dict):
            continue
        event_type = str(raw.get("type") or raw.get("event") or "chunk").strip()
        normalized.extend(_normalize_chat_event(event_type, raw, raw.get("delay_ms", raw.get("delayMs"))))
    return normalized


def _normalize_chat_event(
    event_type: str,
    raw: dict[str, Any],
    delay_ms: Any = None,
) -> list[dict[str, Any]]:
    event_key = event_type.lower()
    data = _event_data(raw)

    if event_key in {"chunk", "assistant", "assistant_text"}:
        return [
            {
                "event": "chunk",
                "data": {"content": _stringify(data.get("content", raw.get("content")))},
                "delay_ms": delay_ms,
            }
        ]

    if event_key in {"status", "tool_start", "tool_execution_started"}:
        tool_name = data.get("tool_name") or data.get("toolName")
        return [
            {
                "event": "status",
                "data": {
                    "message": data.get("message") or f"Executing tool: {tool_name}",
                    "tool_name": tool_name,
                    "tool_use_id": data.get("tool_use_id") or data.get("toolUseId"),
                    "tool_input": data.get("tool_input") or data.get("toolInput") or {},
                    "status": data.get("status") or "started",
                    "metadata": data.get("metadata") if isinstance(data.get("metadata"), dict) else None,
                },
                "delay_ms": delay_ms,
            }
        ]

    if event_key in {
        "tool_result",
        "tool_complete",
        "tool_execution_completed",
        "tool_execution_failed",
    }:
        tool_name = data.get("tool_name") or data.get("toolName")
        is_error = bool(data.get("is_error", data.get("isError", event_key.endswith("failed"))))
        return [
            {
                "event": "tool_result",
                "data": {
                    "tool_name": tool_name,
                    "tool_use_id": data.get("tool_use_id") or data.get("toolUseId"),
                    "tool_input": data.get("tool_input") or data.get("toolInput") or {},
                    "output": _stringify(data.get("output")),
                    "error": _stringify(data.get("error")) if data.get("error") is not None else None,
                    "is_error": is_error,
                    "status": data.get("status") or ("failed" if is_error else "completed"),
                    "metadata": data.get("metadata") if isinstance(data.get("metadata"), dict) else None,
                },
                "delay_ms": delay_ms,
            }
        ]

    if event_key == "error":
        return [
            {
                "event": "error",
                "data": {"message": _stringify(data.get("message") or raw.get("message"))},
                "delay_ms": delay_ms,
            }
        ]

    if event_key == "completed":
        return [
            {
                "event": "completed",
                "data": data,
                "delay_ms": delay_ms,
            }
        ]
    return []


def _first_text(mapping: dict[str, Any], *keys: str) -> str:
    for key in keys:
        value = mapping.get(key)
        if value is not None:
            return _stringify(value)
    return ""


def _first_present(mapping: dict[str, Any], *keys: str) -> Any:
    for key in keys:
        if key in mapping:
            return mapping[key]
    return None


def _int_or_none(value: Any) -> int | None:
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def replay_delay_ms(mapping: dict[str, Any]) -> int | None:
    return _int_or_none(_first_present(mapping, "delay_ms", "delayMs"))


def _timing_config(replay: dict[str, Any]) -> dict[str, Any]:
    timing = replay.get("timing") or replay.get("delays") or {}
    return timing if isinstance(timing, dict) else {}


def _timing_int(replay: dict[str, Any], *keys: str, default: int | None = None) -> int | None:
    timing = _timing_config(replay)
    for key in keys:
        if key in timing:
            value = _int_or_none(timing[key])
            return default if value is None else value
    return default


_TOOL_DELAY_WEIGHTS = {
    "glob": 0.65,
    "read": 1.0,
    "search": 1.35,
    "analysis": 1.55,
    "diagnostic": 1.65,
    "edit": 2.45,
    "validation": 2.8,
    "default": 1.2,
}

_TOOL_DELAY_START_RATIOS = {
    "glob": 0.32,
    "read": 0.26,
    "search": 0.24,
    "analysis": 0.22,
    "diagnostic": 0.25,
    "edit": 0.18,
    "validation": 0.16,
    "default": 0.24,
}


def _stable_jitter(seed: str, *, spread: float) -> float:
    digest = hashlib.sha256(seed.encode("utf-8")).hexdigest()
    fraction = int(digest[:8], 16) / 0xFFFFFFFF
    return 1.0 - spread + (fraction * spread * 2)


def _tool_delay_identity(tool: dict[str, Any], index: int) -> str:
    return "|".join(
        str(part or "")
        for part in (
            index,
            tool.get("tool_name"),
            tool.get("toolName"),
            tool.get("name"),
            tool.get("tool_use_id"),
            tool.get("toolUseId"),
            tool.get("id"),
        )
    )


def _tool_delay_kind(tool: dict[str, Any]) -> str:
    text_parts = [
        tool.get("tool_name"),
        tool.get("toolName"),
        tool.get("name"),
        tool.get("label"),
        tool.get("tool_use_id"),
        tool.get("toolUseId"),
    ]
    for key in ("started", "completed", "failed", "result"):
        value = tool.get(key)
        if isinstance(value, dict):
            text_parts.extend([value.get("message"), value.get("status")])
    text = " ".join(_stringify(part) for part in text_parts).casefold()

    if any(token in text for token in ("test", "validate", "verify", "compile", "check", "검증")):
        return "validation"
    if any(token in text for token in ("edit", "write", "update", "patch", "replace", "수정", "변경")):
        return "edit"
    if any(token in text for token in ("diagnostic", "diagnostics", "monitor", "health", "진단", "모니터링")):
        return "diagnostic"
    if any(token in text for token in ("locator", "analyze", "analysis", "inspect", "분석", "추출")):
        return "analysis"
    if any(token in text for token in ("search", "grep", "find", "검색")):
        return "search"
    if any(token in text for token in ("read", "cat", "읽")):
        return "read"
    if any(token in text for token in ("glob", "list", "ls", "목록")):
        return "glob"
    return "default"


def _distribute_total_delay(total_delay_ms: int, weighted_items: list[tuple[str, float]]) -> list[int]:
    if total_delay_ms <= 0 or not weighted_items:
        return []

    total_weight = sum(weight for _, weight in weighted_items)
    if total_weight <= 0:
        return [0 for _ in weighted_items]

    raw_durations = [(total_delay_ms * weight) / total_weight for _, weight in weighted_items]
    durations = [int(value) for value in raw_durations]
    remaining = total_delay_ms - sum(durations)
    if remaining > 0:
        order = sorted(
            range(len(raw_durations)),
            key=lambda index: raw_durations[index] - durations[index],
            reverse=True,
        )
        for index in order[:remaining]:
            durations[index] += 1
    return durations


def _tool_stack_delay_pairs(replay: dict[str, Any], tool_stack: list[dict[str, Any]]) -> list[dict[str, int]]:
    total_delay_ms = _timing_int(
        replay,
        "toolStackTotalDelayMs",
        "tool_stack_total_delay_ms",
        "toolTotalDelayMs",
        "tool_total_delay_ms",
        default=None,
    )
    if total_delay_ms is None or total_delay_ms <= 0 or not tool_stack:
        return []

    weighted_items: list[tuple[str, float]] = []
    identities: list[str] = []
    replay_id = _stringify(replay.get("id"))
    for index, tool in enumerate(tool_stack):
        kind = _tool_delay_kind(tool)
        identity = _tool_delay_identity(tool, index)
        identities.append(identity)
        jitter = _stable_jitter(f"{replay_id}|{identity}|duration", spread=0.13)
        weighted_items.append((kind, _TOOL_DELAY_WEIGHTS.get(kind, _TOOL_DELAY_WEIGHTS["default"]) * jitter))

    durations = _distribute_total_delay(total_delay_ms, weighted_items)
    delay_pairs: list[dict[str, int]] = []
    for index, duration in enumerate(durations):
        kind = weighted_items[index][0]
        ratio_jitter = _stable_jitter(f"{replay_id}|{identities[index]}|start", spread=0.04)
        start_ratio = _TOOL_DELAY_START_RATIOS.get(kind, _TOOL_DELAY_START_RATIOS["default"]) * ratio_jitter
        start_ratio = max(0.12, min(0.36, start_ratio))
        start_delay_ms = int(duration * start_ratio)
        if duration >= 400:
            start_delay_ms = max(120, start_delay_ms)
        if start_delay_ms >= duration:
            start_delay_ms = duration // 2
        delay_pairs.append(
            {
                "start": start_delay_ms,
                "result": duration - start_delay_ms,
            }
        )
    return delay_pairs


def _text_stream_events(
    replay: dict[str, Any],
    content: str,
    *,
    initial_delay_ms: int | None,
) -> list[dict[str, Any]]:
    text = _stringify(content)
    if not text:
        return []

    chunk_chars = _timing_int(
        replay,
        "textChunkChars",
        "text_chunk_chars",
        "chunkChars",
        "chunk_size",
        "chunkSize",
        default=0,
    )
    chunk_delay_ms = _timing_int(
        replay,
        "textChunkDelayMs",
        "text_chunk_delay_ms",
        "chunkDelayMs",
        default=None,
    )

    if chunk_chars is None or chunk_chars <= 0:
        chunks = [text]
    else:
        chunks = [text[index : index + chunk_chars] for index in range(0, len(text), chunk_chars)]

    events: list[dict[str, Any]] = []
    for index, chunk in enumerate(chunks):
        events.append(
            {
                "event": "chunk",
                "data": {"content": chunk},
                "delay_ms": initial_delay_ms if index == 0 else chunk_delay_ms,
            }
        )
    return events


def _answer_chunks(replay: dict[str, Any], *, before_tools: bool) -> list[str]:
    answer = replay.get("answer")
    if isinstance(answer, str):
        return [] if before_tools else [answer]
    if not isinstance(answer, dict):
        key = "answer_before_tools" if before_tools else "answer_after_tools"
        camel_key = "answerBeforeTools" if before_tools else "answerAfterTools"
        return [text for text in [_first_text(replay, key, camel_key)] if text]

    if before_tools:
        keys = ("before_tools", "beforeTools", "prelude", "before")
    else:
        keys = ("after_tools", "afterTools", "final", "after")
    direct = _first_text(answer, *keys)
    chunks = [direct] if direct else []
    extra_key = "before_chunks" if before_tools else "after_chunks"
    extra_camel_key = "beforeChunks" if before_tools else "afterChunks"
    for item in [*_as_list(answer.get(extra_key)), *_as_list(answer.get(extra_camel_key))]:
        text = _stringify(item)
        if text:
            chunks.append(text)
    return chunks


def _tool_stack_entries(replay: dict[str, Any]) -> list[dict[str, Any]]:
    raw_stack = (
        replay.get("tool_stack")
        or replay.get("toolStack")
        or replay.get("tools")
        or []
    )
    if not isinstance(raw_stack, list):
        return []
    return [item for item in raw_stack if isinstance(item, dict)]


def _tool_start_event(
    replay: dict[str, Any],
    tool: dict[str, Any],
    *,
    delay_ms_override: int | None = None,
) -> dict[str, Any]:
    started = tool.get("started") if isinstance(tool.get("started"), dict) else {}
    tool_name = tool.get("tool_name") or tool.get("toolName") or tool.get("name")
    tool_use_id = tool.get("tool_use_id") or tool.get("toolUseId") or tool.get("id")
    delay_ms = replay_delay_ms(started)
    if delay_ms is None:
        delay_ms = delay_ms_override
    if delay_ms is None:
        delay_ms = _timing_int(replay, "toolStartDelayMs", "tool_start_delay_ms", default=None)
    tool_input = (
        tool.get("tool_input")
        or tool.get("toolInput")
        or tool.get("input")
        or tool.get("arguments")
        or {}
    )
    return {
        "event": "status",
        "data": {
            "message": started.get("message") or tool.get("message") or f"Executing tool: {tool_name}",
            "tool_name": tool_name,
            "tool_use_id": tool_use_id,
            "tool_input": tool_input if isinstance(tool_input, dict) else {},
            "status": started.get("status") or "started",
            "metadata": started.get("metadata") if isinstance(started.get("metadata"), dict) else None,
        },
        "delay_ms": delay_ms,
    }


def _tool_result_event(
    replay: dict[str, Any],
    tool: dict[str, Any],
    *,
    delay_ms_override: int | None = None,
) -> dict[str, Any]:
    result = (
        tool.get("completed")
        if isinstance(tool.get("completed"), dict)
        else tool.get("result")
        if isinstance(tool.get("result"), dict)
        else tool.get("failed")
        if isinstance(tool.get("failed"), dict)
        else {}
    )
    tool_name = tool.get("tool_name") or tool.get("toolName") or tool.get("name")
    tool_use_id = tool.get("tool_use_id") or tool.get("toolUseId") or tool.get("id")
    tool_input = (
        tool.get("tool_input")
        or tool.get("toolInput")
        or tool.get("input")
        or tool.get("arguments")
        or {}
    )
    is_error = bool(
        result.get(
            "is_error",
            result.get("isError", tool.get("is_error", tool.get("isError", "failed" in tool))),
        )
    )
    fallback_delay_keys = (
        ("toolFailedDelayMs", "tool_failed_delay_ms", "toolResultDelayMs", "tool_result_delay_ms")
        if is_error
        else ("toolCompletedDelayMs", "tool_completed_delay_ms", "toolResultDelayMs", "tool_result_delay_ms")
    )
    delay_ms = replay_delay_ms(result)
    if delay_ms is None:
        delay_ms = delay_ms_override
    if delay_ms is None:
        delay_ms = _timing_int(replay, *fallback_delay_keys, default=None)
    return {
        "event": "tool_result",
        "data": {
            "tool_name": tool_name,
            "tool_use_id": tool_use_id,
            "tool_input": tool_input if isinstance(tool_input, dict) else {},
            "output": _stringify(result.get("output", tool.get("output"))),
            "error": _stringify(result.get("error")) if result.get("error") is not None else None,
            "is_error": is_error,
            "status": result.get("status") or ("failed" if is_error else "completed"),
            "metadata": result.get("metadata") if isinstance(result.get("metadata"), dict) else None,
        },
        "delay_ms": delay_ms,
    }


def _structured_chat_events(replay: dict[str, Any]) -> list[dict[str, Any]]:
    normalized: list[dict[str, Any]] = []
    tool_stack = _tool_stack_entries(replay)
    before_delay_ms = _timing_int(
        replay,
        "beforeToolsDelayMs",
        "before_tools_delay_ms",
        "beforeAnswerDelayMs",
        default=None,
    )
    after_delay_ms = _timing_int(
        replay,
        "afterToolsDelayMs",
        "after_tools_delay_ms",
        "afterAnswerDelayMs",
        default=None,
    )

    for content in _answer_chunks(replay, before_tools=True):
        normalized.extend(_text_stream_events(replay, content, initial_delay_ms=before_delay_ms))

    tool_delay_pairs = _tool_stack_delay_pairs(replay, tool_stack)
    for index, tool in enumerate(tool_stack):
        delay_pair = tool_delay_pairs[index] if index < len(tool_delay_pairs) else {}
        normalized.append(_tool_start_event(replay, tool, delay_ms_override=delay_pair.get("start")))
        normalized.append(_tool_result_event(replay, tool, delay_ms_override=delay_pair.get("result")))

    for content in _answer_chunks(replay, before_tools=False):
        normalized.extend(_text_stream_events(replay, content, initial_delay_ms=after_delay_ms))

    return normalized


def chat_replay_stream_events(replay: dict[str, Any]) -> list[dict[str, Any]]:
    events = replay.get("events")
    if isinstance(events, list):
        return _normalize_chat_events(events)
    return _structured_chat_events(replay)


def chat_replay_model_name(replay: dict[str, Any]) -> str:
    completed = replay.get("completed") if isinstance(replay.get("completed"), dict) else {}
    return str(completed.get("model_name") or completed.get("modelName") or "demo-replay")


def chat_replay_total_tokens(replay: dict[str, Any]) -> int:
    completed = replay.get("completed") if isinstance(replay.get("completed"), dict) else {}
    try:
        return int(completed.get("total_tokens", completed.get("totalTokens", 0)) or 0)
    except (TypeError, ValueError):
        return 0


def plan_replay_progress(replay: dict[str, Any]) -> list[dict[str, Any]]:
    progress = replay.get("progress")
    if isinstance(progress, list) and progress:
        return [item for item in progress if isinstance(item, dict)]
    return [
        {"message": "REQUEST_RECEIVED", "progressRate": 5},
        {"message": "PLAN_DRAFTING", "progressRate": 30},
        {"message": "PLAN_STRUCTURING", "progressRate": 75},
        {"message": "PLAN_COMPLETED", "progressRate": 100},
    ]


def plan_replay_chunks(replay: dict[str, Any]) -> list[str]:
    chunks = replay.get("chunks")
    if isinstance(chunks, list):
        return [_stringify(chunk) for chunk in chunks if _stringify(chunk)]
    if isinstance(chunks, str):
        return [chunks]
    return []


def build_tool_plan_result_from_replay(replay: dict[str, Any]) -> ToolPlanResult:
    result = replay.get("result") if isinstance(replay.get("result"), dict) else replay
    raw_markdown = _stringify(
        result.get("raw_markdown")
        or result.get("rawMarkdown")
        or result.get("markdown")
        or ""
    )
    structured = (
        result.get("structured_plan_json")
        or result.get("structuredPlanJson")
        or result.get("structured")
        or {}
    )
    snapshot = result.get("plan_snapshot") or result.get("planSnapshot") or {}

    if not isinstance(structured, dict):
        structured = {"content": structured}
    if not isinstance(snapshot, dict):
        snapshot = {"content": snapshot}

    return ToolPlanResult(
        rawMarkdown=raw_markdown,
        structuredPlanJson=structured,
        planSnapshot=snapshot,
    )
