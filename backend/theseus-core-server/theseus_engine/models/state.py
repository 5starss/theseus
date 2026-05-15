"""Theseus runtime state machine facade.

Prompt text lives in :mod:`theseus_engine.prompts`. This module keeps the
state-machine API and legacy enum import paths stable for CLI, TUI, Extension,
and server adapters.
"""

from typing import Iterable, Optional

from theseus_engine.models.modes import (
    MODE_DESCRIPTIONS,
    AgentMode,
    CoordinatorPhase,
    PlanPhase,
)
from theseus_engine.prompts.builder import build_system_prompt
from theseus_engine.prompts.capabilities import PromptCapabilities


# ---------------------------------------------------------------------------
# Theseus State Machine
# ---------------------------------------------------------------------------


class TheseusStateMachine:
    """4-Mode 상태 머신: Ask / Agent / Plan / Coordinator.

    상용 AI 코딩 어시스턴트(Cursor, Copilot)의 모드 전환 패러다임을
    기반으로, 사용자의 의도에 맞는 프롬프트를 동적으로 조합합니다.

    Attributes:
        mode: 현재 활성 모드 (ASK, AGENT, PLAN, COORDINATOR).
        plan_phase: Plan 모드일 때의 하위 단계.
        coordinator_phase: Coordinator 모드일 때의 하위 단계.
        plan: 승인 대기 중인 플랜 마크다운 텍스트.
        plan_blocks: Pydantic 구조화 블록 리스트 (리뷰 UI용).
        plan_document: PlanDocument 객체 (원본 구조화 데이터).
    """

    def __init__(self, initial_mode: AgentMode = AgentMode.AGENT):
        """상태 머신을 초기화합니다.

        Args:
            initial_mode: 시작 시 활성화될 모드. 기본값은 Agent.
        """
        self.mode = initial_mode
        self.plan_phase: Optional[PlanPhase] = None
        self.coordinator_phase: Optional[CoordinatorPhase] = None
        self.plan = ""
        self.plan_blocks = []
        self.plan_document = None

    # ----- Mode switching -----

    def switch_mode(self, new_mode: AgentMode) -> None:
        """최상위 모드를 전환합니다."""
        old = self.mode
        self.mode = new_mode

        if new_mode == AgentMode.PLAN:
            self.plan_phase = PlanPhase.DRAFTING
            self.coordinator_phase = None
            self.plan = ""
            self.plan_blocks = []
            self.plan_document = None
        elif new_mode == AgentMode.COORDINATOR:
            self.coordinator_phase = CoordinatorPhase.DECOMPOSE
            self.plan_phase = None
        else:
            self.plan_phase = None
            self.coordinator_phase = None

        try:
            print(
                f"\n[Mode Switch] {old.value} -> {new_mode.value}"
                f"  ({MODE_DESCRIPTIONS[new_mode]})"
            )
        except UnicodeEncodeError:
            print(f"\n[Mode Switch] {old.value} -> {new_mode.value}")

    def set_plan_phase(self, phase: PlanPhase) -> None:
        """Plan 모드 내에서 하위 단계를 전환합니다."""
        self.plan_phase = phase
        print(f"\n[Plan Phase] → {phase.value}")

    def set_coordinator_phase(self, phase: CoordinatorPhase) -> None:
        """Coordinator 모드 내에서 하위 단계를 전환합니다."""
        self.coordinator_phase = phase
        print(f"\n[Coordinator Phase] → {phase.value}")

    # ----- Convenience properties -----

    @property
    def is_plan_reviewing(self) -> bool:
        """현재 플랜 리뷰 대기 중인지 여부."""
        return (
            self.mode == AgentMode.PLAN
            and self.plan_phase == PlanPhase.WAIT_FOR_REVIEW
        )

    @property
    def is_plan_drafting(self) -> bool:
        """현재 플랜 작성 중인지 여부."""
        return (
            self.mode == AgentMode.PLAN
            and self.plan_phase == PlanPhase.DRAFTING
        )

    @property
    def is_plan_executing(self) -> bool:
        """현재 플랜 실행 단계인지 여부."""
        return (
            self.mode == AgentMode.PLAN
            and self.plan_phase == PlanPhase.EXECUTING
        )

    @property
    def is_plan_verifying(self) -> bool:
        """현재 플랜 검증 단계인지 여부."""
        return (
            self.mode == AgentMode.PLAN
            and self.plan_phase == PlanPhase.VERIFYING
        )

    @property
    def display_mode(self) -> str:
        """프롬프트 표시용 현재 모드 문자열."""
        if self.mode == AgentMode.PLAN and self.plan_phase:
            return f"Plan/{self.plan_phase.value}"
        if self.mode == AgentMode.COORDINATOR and self.coordinator_phase:
            return f"Coordinator/{self.coordinator_phase.value}"
        return self.mode.value

    # ----- System prompt assembly -----

    def get_system_prompt(
        self,
        *,
        available_tools: Optional[Iterable[str]] = None,
        runtime_reminders: Optional[Iterable[str]] = None,
    ) -> str:
        return build_system_prompt(
            mode=self.mode,
            plan_phase=self.plan_phase,
            coordinator_phase=self.coordinator_phase,
            plan=self.plan,
            available_tools=available_tools,
            runtime_reminders=runtime_reminders,
        )


__all__ = [
    "AgentMode",
    "PlanPhase",
    "CoordinatorPhase",
    "MODE_DESCRIPTIONS",
    "PromptCapabilities",
    "TheseusStateMachine",
]
