from __future__ import annotations

import json
import logging
import os
import re
from dataclasses import dataclass, field
from typing import Awaitable, Callable, Literal

from theseus_engine.core.plan_flow import (
    PLAN_CONTINUE_PROMPT,
    PLAN_TOOL_ERROR_PROMPT,
    PLAN_VERIFICATION_PROMPT,
    contains_execution_complete,
    contains_verification_complete,
)

log = logging.getLogger(__name__)

LoopAction = Literal["continue", "stop", "ask_user", "verify", "retry_tool_error"]
LoopDecisionMode = Literal["heuristic", "semantic", "hybrid"]


def read_non_negative_int_env(name: str, default: int) -> int:
    raw = os.getenv(name, str(default))
    try:
        return max(0, int(raw))
    except (TypeError, ValueError):
        log.warning("Invalid %s=%r; using %s", name, raw, default)
        return max(0, default)


def read_loop_decision_mode() -> LoopDecisionMode:
    raw = os.getenv("THESEUS_AGENT_LOOP_DECISION_MODE", "hybrid").strip().lower()
    if raw in {"heuristic", "semantic", "hybrid"}:
        return raw  # type: ignore[return-value]
    log.warning("Invalid THESEUS_AGENT_LOOP_DECISION_MODE=%r; using hybrid", raw)
    return "hybrid"


AGENT_AUTO_CONTINUE_MAX = read_non_negative_int_env("THESEUS_AGENT_AUTO_CONTINUE_MAX", 1)

AUTO_CONTINUE_PROMPT = (
    "Continue the task now. Your previous assistant message indicated pending work "
    "but did not call a tool. Do not repeat the plan or ask the user to wait. "
    "If a tool is needed, call the appropriate tool now. If no tool is needed, "
    "provide the final result directly."
)

SEMANTIC_CONTINUE_CONFIDENCE = 0.7

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
        r"(?:확인해 주세요|선택해 주세요|결정해 주세요|승인해 주세요)",
        r"(?:which option|would you like|should I|please confirm|confirm before)",
    )
)
_FINAL_ANSWER_PATTERNS = tuple(
    re.compile(pattern, re.IGNORECASE)
    for pattern in (
        r"(?:분석 결과|조회 결과|현재 .*상태|요약[:：]|권장 조치|최종 리포트)",
        r"(?:완료했습니다|완료되었습니다|정상입니다|안정적입니다|문제 없습니다)",
        r"(?:result|summary|final answer|completed|no further action)",
    )
)
_BLOCKED_OR_WAITING_PATTERNS = tuple(
    re.compile(pattern, re.IGNORECASE)
    for pattern in (
        r"(?:승인.*필요|권한.*필요|사용자.*승인|명시적 승인)",
        r"(?:차단되었습니다|수행할 수 없습니다|진행할 수 없습니다|불가능합니다)",
        r"(?:requires approval|permission required|blocked|cannot proceed)",
    )
)
_CONTINUATION_STOP_REASONS = {
    "max_tokens",
    "length",
    "incomplete",
    "model_length",
    "token_limit",
}


@dataclass(frozen=True)
class LoopDecisionContext:
    mode: str
    plan_phase: str | None = None
    stop_reason: str | None = None
    assistant_text: str = ""
    tool_call_count: int = 0
    tool_error: bool = False
    last_tool_results: tuple[str, ...] = ()
    auto_continue_count: int = 0
    available_tools: bool = False
    user_goal: str | None = None
    max_auto_continue: int = AGENT_AUTO_CONTINUE_MAX


@dataclass(frozen=True)
class LoopContinuationDecision:
    action: LoopAction
    reason: str
    confidence: float = 1.0
    resume_prompt: str | None = None
    trigger_signals: tuple[str, ...] = field(default_factory=tuple)

    @property
    def should_resume(self) -> bool:
        return self.action in {"continue", "verify", "retry_tool_error"}

    def to_metadata(self) -> dict[str, object]:
        return {
            "loopDecision": self.action,
            "decisionReason": self.reason,
            "confidence": round(float(self.confidence), 3),
            "triggerSignals": list(self.trigger_signals),
            "resumePrompt": self.resume_prompt,
        }


LoopSemanticEvaluator = Callable[
    [LoopDecisionContext, LoopContinuationDecision],
    Awaitable[LoopContinuationDecision | None],
]


def _compact_text(text: str) -> str:
    return " ".join(str(text or "").strip().split())


def _matches_any(text: str, patterns: tuple[re.Pattern[str], ...]) -> bool:
    return any(pattern.search(text) for pattern in patterns)


def _stop_reason_requests_continuation(stop_reason: str | None) -> bool:
    if not stop_reason:
        return False
    return stop_reason.strip().lower() in _CONTINUATION_STOP_REASONS


def _mode_key(value: str | None) -> str:
    return str(value or "").strip().upper()


def _phase_key(value: str | None) -> str:
    return str(value or "").strip().upper()


def classify_loop_continuation(context: LoopDecisionContext) -> LoopContinuationDecision:
    text = _compact_text(context.assistant_text)
    mode = _mode_key(context.mode)
    phase = _phase_key(context.plan_phase)

    if context.tool_call_count > 0:
        return LoopContinuationDecision("stop", "tool_calls_present", 1.0, trigger_signals=("tool_call",))
    if context.auto_continue_count >= context.max_auto_continue:
        return LoopContinuationDecision("stop", "auto_continue_limit_reached", 1.0, trigger_signals=("budget",))
    if not context.available_tools:
        return LoopContinuationDecision("stop", "no_available_tools", 1.0, trigger_signals=("tool_registry_empty",))
    if mode == "ASK":
        return LoopContinuationDecision("stop", "ask_mode_never_auto_continues", 1.0, trigger_signals=("ask_mode",))

    if _matches_any(text, _USER_DECISION_PATTERNS):
        return LoopContinuationDecision("ask_user", "assistant_requested_user_decision", 0.95, trigger_signals=("user_decision",))
    if _matches_any(text, _BLOCKED_OR_WAITING_PATTERNS):
        return LoopContinuationDecision("ask_user", "assistant_reported_blocked_or_approval_needed", 0.9, trigger_signals=("blocked_or_approval",))

    if mode == "PLAN" and phase == "EXECUTING" and contains_execution_complete(text):
        return LoopContinuationDecision(
            "verify",
            "plan_execution_complete",
            0.96,
            resume_prompt=PLAN_VERIFICATION_PROMPT,
            trigger_signals=("plan_execution_complete",),
        )
    if mode == "PLAN" and phase == "VERIFYING" and contains_verification_complete(text):
        return LoopContinuationDecision("stop", "plan_verification_complete", 0.96, trigger_signals=("plan_verification_complete",))

    if context.tool_error and mode in {"AGENT", "PLAN"}:
        return LoopContinuationDecision(
            "retry_tool_error",
            "tool_error_requires_recovery_turn",
            0.8,
            resume_prompt=PLAN_TOOL_ERROR_PROMPT,
            trigger_signals=("tool_error",),
        )

    if _stop_reason_requests_continuation(context.stop_reason):
        return LoopContinuationDecision(
            "continue",
            "provider_stop_reason_requests_continuation",
            0.92,
            resume_prompt=AUTO_CONTINUE_PROMPT,
            trigger_signals=("stop_reason", str(context.stop_reason or "")),
        )

    if _matches_any(text, _FINAL_ANSWER_PATTERNS):
        return LoopContinuationDecision("stop", "assistant_text_looks_final", 0.78, trigger_signals=("final_answer",))

    if _matches_any(text, _PENDING_ACTION_PATTERNS):
        return LoopContinuationDecision(
            "continue",
            "assistant_text_has_pending_action_candidate",
            0.62,
            resume_prompt=PLAN_CONTINUE_PROMPT if mode == "PLAN" else AUTO_CONTINUE_PROMPT,
            trigger_signals=("pending_action_text",),
        )

    return LoopContinuationDecision("stop", "no_continuation_signal", 0.74, trigger_signals=("no_signal",))


def _is_hard_decision(decision: LoopContinuationDecision) -> bool:
    return decision.reason in {
        "tool_calls_present",
        "auto_continue_limit_reached",
        "no_available_tools",
        "ask_mode_never_auto_continues",
        "assistant_requested_user_decision",
        "assistant_reported_blocked_or_approval_needed",
        "provider_stop_reason_requests_continuation",
        "plan_execution_complete",
        "plan_verification_complete",
        "tool_error_requires_recovery_turn",
    }


def _should_use_semantic_evaluator(
    *,
    decision_mode: LoopDecisionMode,
    decision: LoopContinuationDecision,
    semantic_evaluator: LoopSemanticEvaluator | None,
) -> bool:
    if semantic_evaluator is None or decision_mode == "heuristic":
        return False
    if _is_hard_decision(decision):
        return False
    if decision_mode == "semantic":
        return True
    return decision.reason == "assistant_text_has_pending_action_candidate"


async def decide_loop_continuation(
    context: LoopDecisionContext,
    *,
    semantic_evaluator: LoopSemanticEvaluator | None = None,
    decision_mode: LoopDecisionMode | None = None,
) -> LoopContinuationDecision:
    heuristic = classify_loop_continuation(context)
    mode = decision_mode or read_loop_decision_mode()
    if not _should_use_semantic_evaluator(
        decision_mode=mode,
        decision=heuristic,
        semantic_evaluator=semantic_evaluator,
    ):
        return heuristic

    try:
        refined = await semantic_evaluator(context, heuristic) if semantic_evaluator else None
    except Exception as exc:
        log.warning("Loop semantic evaluator failed; using heuristic decision: %s", exc)
        return heuristic

    if refined is None:
        return heuristic
    if refined.action in {"continue", "verify", "retry_tool_error"} and refined.confidence < SEMANTIC_CONTINUE_CONFIDENCE:
        return LoopContinuationDecision(
            "stop",
            "semantic_low_confidence",
            refined.confidence,
            trigger_signals=(*refined.trigger_signals, "semantic_low_confidence"),
        )
    return refined


def parse_semantic_decision_payload(
    payload: str,
    fallback: LoopContinuationDecision,
) -> LoopContinuationDecision | None:
    text = str(payload or "").strip()
    if not text:
        return None
    match = re.search(r"\{.*\}", text, re.DOTALL)
    if match:
        text = match.group(0)
    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        return None
    if not isinstance(data, dict):
        return None
    action = str(data.get("action") or "").strip().lower()
    if action not in {"continue", "stop", "ask_user", "verify", "retry_tool_error"}:
        return None
    try:
        confidence = float(data.get("confidence", fallback.confidence))
    except (TypeError, ValueError):
        confidence = fallback.confidence
    confidence = max(0.0, min(1.0, confidence))
    reason = str(data.get("reason") or f"semantic_{action}").strip()[:200]
    next_prompt = data.get("next_prompt")
    resume_prompt = str(next_prompt).strip() if isinstance(next_prompt, str) and next_prompt.strip() else fallback.resume_prompt
    return LoopContinuationDecision(
        action=action,  # type: ignore[arg-type]
        reason=reason,
        confidence=confidence,
        resume_prompt=resume_prompt,
        trigger_signals=(*fallback.trigger_signals, "semantic_evaluator"),
    )


def should_continue(decision: LoopContinuationDecision) -> bool:
    return decision.should_resume
