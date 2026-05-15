"""Canonical system prompt builder for Theseus runtimes."""

from typing import Iterable, Optional

from theseus_engine.models.modes import AgentMode, CoordinatorPhase, PlanPhase
from theseus_engine.prompts.base import BASE_SYSTEM_PROMPT
from theseus_engine.prompts.capabilities import (
    build_prompt_capabilities,
    render_capability_sections,
    render_runtime_reminders,
)
from theseus_engine.prompts.coordinator import (
    COORDINATOR_DECOMPOSE_PROMPT,
    COORDINATOR_DISPATCH_PROMPT,
    COORDINATOR_SYNTHESIZE_PROMPT,
    COORDINATOR_VERIFY_PROMPT,
)
from theseus_engine.prompts.environment import get_environment_section
from theseus_engine.prompts.modes import AGENT_PROMPT, ASK_PROMPT
from theseus_engine.prompts.plan import (
    PLAN_DRAFTING_PROMPT,
    PLAN_EXECUTING_PROMPT_TEMPLATE,
    PLAN_REVIEW_PROMPT,
    PLAN_VERIFYING_PROMPT,
)


def _select_mode_prompt(
    *,
    mode: AgentMode,
    plan_phase: Optional[PlanPhase],
    coordinator_phase: Optional[CoordinatorPhase],
    plan: str,
) -> str:
    if mode == AgentMode.ASK:
        return ASK_PROMPT
    if mode == AgentMode.AGENT:
        return AGENT_PROMPT
    if mode == AgentMode.PLAN:
        if plan_phase == PlanPhase.DRAFTING:
            return PLAN_DRAFTING_PROMPT
        if plan_phase == PlanPhase.WAIT_FOR_REVIEW:
            return PLAN_REVIEW_PROMPT
        if plan_phase == PlanPhase.EXECUTING:
            return PLAN_EXECUTING_PROMPT_TEMPLATE.format(plan=plan or "")
        return PLAN_VERIFYING_PROMPT
    if mode == AgentMode.COORDINATOR:
        if coordinator_phase == CoordinatorPhase.DECOMPOSE:
            return COORDINATOR_DECOMPOSE_PROMPT
        if coordinator_phase == CoordinatorPhase.DISPATCH:
            return COORDINATOR_DISPATCH_PROMPT
        if coordinator_phase == CoordinatorPhase.SYNTHESIZE:
            return COORDINATOR_SYNTHESIZE_PROMPT
        return COORDINATOR_VERIFY_PROMPT
    return AGENT_PROMPT


def build_system_prompt(
    *,
    mode: AgentMode,
    plan_phase: Optional[PlanPhase] = PlanPhase.DRAFTING,
    coordinator_phase: Optional[CoordinatorPhase] = CoordinatorPhase.DECOMPOSE,
    plan: str = "",
    available_tools: Optional[Iterable[str]] = None,
    runtime_reminders: Optional[Iterable[str]] = None,
) -> str:
    """Build the canonical Theseus system prompt for all runtimes."""

    capabilities = build_prompt_capabilities(
        mode=mode,
        plan_phase=plan_phase,
        coordinator_phase=coordinator_phase,
        available_tools=available_tools,
        runtime_reminders=runtime_reminders,
    )
    mode_prompt = _select_mode_prompt(
        mode=mode,
        plan_phase=plan_phase,
        coordinator_phase=coordinator_phase,
        plan=plan,
    )
    sections = [
        BASE_SYSTEM_PROMPT,
        get_environment_section(),
        mode_prompt,
        render_capability_sections(capabilities),
        render_runtime_reminders(capabilities.runtime_reminders),
    ]
    return "\n\n".join(section for section in sections if section)


__all__ = ["build_system_prompt"]
