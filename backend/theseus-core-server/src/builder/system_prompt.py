from __future__ import annotations

import json
from typing import Any, Iterable

from theseus_engine.models.modes import (
    AgentMode,
    CoordinatorPhase,
    PlanPhase,
)
from theseus_engine.models.state import (
    TheseusStateMachine,
)


def build_theseus_system_prompt(
    *,
    mode: AgentMode,
    plan_phase: PlanPhase | None = None,
    coordinator_phase: CoordinatorPhase | None = None,
    plan_content: Any | None = None,
    available_tools: Iterable[str] | None = None,
    runtime_reminders: Iterable[str] | None = None,
) -> str:
    """Build the canonical Theseus system prompt for a server-side request."""

    state_machine = TheseusStateMachine(initial_mode=mode)
    if mode == AgentMode.PLAN:
        state_machine.plan_phase = plan_phase or PlanPhase.DRAFTING
    elif mode == AgentMode.COORDINATOR:
        state_machine.coordinator_phase = coordinator_phase or CoordinatorPhase.DECOMPOSE

    if plan_content is not None:
        state_machine.plan = _format_plan_content(plan_content)

    return state_machine.get_system_prompt(
        available_tools=available_tools,
        runtime_reminders=runtime_reminders,
    )


def _format_plan_content(plan_content: Any) -> str:
    if isinstance(plan_content, str):
        return plan_content
    try:
        return json.dumps(plan_content, ensure_ascii=False, indent=2, sort_keys=True)
    except TypeError:
        return str(plan_content)
