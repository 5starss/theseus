from __future__ import annotations

import logging
import os
import re

log = logging.getLogger(__name__)


def read_non_negative_int_env(name: str, default: int) -> int:
    raw = os.getenv(name, str(default))
    try:
        return max(0, int(raw))
    except (TypeError, ValueError):
        log.warning("Invalid %s=%r; using %s", name, raw, default)
        return max(0, default)


AGENT_AUTO_CONTINUE_MAX = read_non_negative_int_env("THESEUS_AGENT_AUTO_CONTINUE_MAX", 1)

AUTO_CONTINUE_PROMPT = (
    "Continue the task now. Your previous assistant message indicated pending work "
    "but did not call a tool. Do not repeat the plan or ask the user to wait. "
    "If a tool is needed, call the appropriate tool now. If no tool is needed, "
    "provide the final result directly."
)

_PENDING_ACTION_PATTERNS = tuple(
    re.compile(pattern, re.IGNORECASE)
    for pattern in (
        r"\bI\s+(?:will|am going to)\b",
        r"\b(?:I'll|I’ll)\b",
        r"\b(?:let me|I'll now|I will now)\b",
        r"\b(?:checking|analyzing|reading|editing|running|testing|verifying)\b",
        r"(?:하겠습니다|하겠습니?다|하겠어요|하겠습니다\.)",
        r"(?:읽겠습니다|확인하겠습니다|분석하겠습니다|수정하겠습니다|실행하겠습니다|검증하겠습니다)",
        r"(?:진행하겠습니다|시작하겠습니다|작업하겠습니다|들어가겠습니다)",
        r"(?:진행 중입니다|분석 중입니다|수정 작업에 들어가겠습니다)",
        r"(?:잠시만 기다려|기다려 주시면|바로 .*하겠습니다|먼저 .*하겠습니다)",
    )
)
_USER_DECISION_PATTERNS = tuple(
    re.compile(pattern, re.IGNORECASE)
    for pattern in (
        r"\?$",
        r"(?:진행해도 될까요|진행하시겠습니까|승인.*(?:필요|해|하시겠습니까))",
        r"(?:허용하시겠습니까|동의하시면|말씀해 주세요|어떻게 진행할까요)",
        r"(?:which option|would you like|should I|please confirm)",
    )
)
_CONTINUATION_STOP_REASONS = {
    "max_tokens",
    "length",
    "incomplete",
    "model_length",
    "token_limit",
}


def should_auto_continue_after_assistant(
    *,
    final_text: str,
    stop_reason: str | None,
    tool_call_count: int,
    auto_continue_count: int,
    has_available_tools: bool,
    mode: str,
) -> bool:
    if tool_call_count > 0:
        return False
    if auto_continue_count >= AGENT_AUTO_CONTINUE_MAX:
        return False
    if not has_available_tools:
        return False
    if mode.upper() == "ASK":
        return False
    return _stop_reason_requests_continuation(stop_reason) or _looks_like_pending_action(final_text)


def _looks_like_user_decision_request(text: str) -> bool:
    compact = text.strip()
    if not compact:
        return False
    return any(pattern.search(compact) for pattern in _USER_DECISION_PATTERNS)


def _looks_like_pending_action(text: str) -> bool:
    compact = text.strip()
    if not compact:
        return False
    if _looks_like_user_decision_request(compact):
        return False
    return any(pattern.search(compact) for pattern in _PENDING_ACTION_PATTERNS)


def _stop_reason_requests_continuation(stop_reason: str | None) -> bool:
    if not stop_reason:
        return False
    normalized = stop_reason.strip().lower()
    return normalized in _CONTINUATION_STOP_REASONS
