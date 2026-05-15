"""Runtime mode and phase enums for Theseus.

This module intentionally contains no prompt text so prompt builders can
reuse mode definitions without importing the state-machine facade.
"""

from enum import Enum


class AgentMode(Enum):
    """최상위 사용자 선택 모드 (Cursor/Copilot 스타일)."""

    ASK = "Ask"
    AGENT = "Agent"
    PLAN = "Plan"
    COORDINATOR = "Coordinator"


class PlanPhase(Enum):
    """Plan 모드 내부의 하위 단계."""

    DRAFTING = "Drafting"
    WAIT_FOR_REVIEW = "WaitForReview"
    EXECUTING = "Executing"
    VERIFYING = "Verifying"


class CoordinatorPhase(Enum):
    """Coordinator 모드 내부의 4단계 오케스트레이션 파이프라인."""

    DECOMPOSE = "Decompose"
    DISPATCH = "Dispatch"
    SYNTHESIZE = "Synthesize"
    VERIFY = "Verify"


MODE_DESCRIPTIONS = {
    AgentMode.ASK: "💬 Ask         — 질문/답변 전용 (도구 사용 안 함)",
    AgentMode.AGENT: "🤖 Agent       — 자율 실행 (도구 자유 사용)",
    AgentMode.PLAN: "📋 Plan        — 계획 → 리뷰 → 실행 → 검증 파이프라인",
    AgentMode.COORDINATOR: "🎯 Coordinator — 병렬 서브 에이전트 오케스트레이션",
}

__all__ = [
    "AgentMode",
    "PlanPhase",
    "CoordinatorPhase",
    "MODE_DESCRIPTIONS",
]
