"""Runtime mode context reminders shared by Theseus runtimes."""

from __future__ import annotations

from typing import Any

from theseus_engine.models.modes import AgentMode, PlanPhase


def build_mode_runtime_reminders(
    current_mode: AgentMode | str,
    previous_mode: AgentMode | str | None = None,
    plan_phase: PlanPhase | str | None = None,
    source: str = "runtime",
    explicit_selection: bool = False,
) -> tuple[str, ...]:
    """Build turn-local reminders for the selected Theseus runtime mode.

    The returned reminders are intended for system prompt runtime context, not
    for persisted user history. Callers that store pending reminders should
    replace the pending value with this tuple instead of appending to it.
    """

    mode_name = _normalize_mode_name(current_mode)
    previous_name = _normalize_mode_name(previous_mode) if previous_mode else ""
    phase_name = _normalize_phase_name(plan_phase) if plan_phase else ""

    reminders = [
        _build_mode_assertion(
            mode_name,
            previous_name=previous_name,
            source=source,
            explicit_selection=explicit_selection,
        ),
        (
            "For this turn, this runtime mode has higher priority than older "
            "conversation assumptions, explanations, or instructions about "
            "ASK, AGENT, PLAN, or COORDINATOR behavior."
        ),
        (
            "Treat older conversation instructions that imply a different "
            "Theseus runtime mode as stale for this turn; do not continue the "
            "previous mode's behavior unless it matches the current mode."
        ),
        (
            "This does not disable Theseus security policy, RBAC, sandbox "
            "limits, command restrictions, or human approval requirements; "
            "those controls remain authoritative."
        ),
        _mode_specific_reminder(mode_name, phase_name),
    ]
    return tuple(item for item in reminders if item)


def _build_mode_assertion(
    mode_name: str,
    *,
    previous_name: str,
    source: str,
    explicit_selection: bool,
) -> str:
    source_label = source.strip() or "runtime"
    prefix = f"Current Theseus runtime mode for this turn is {mode_name}."
    if previous_name and previous_name != mode_name:
        prefix += f" Previous runtime mode was {previous_name}."
    if explicit_selection:
        prefix += (
            f" The user selected this mode through the {source_label} mode control."
        )
    else:
        prefix += f" This mode was provided by {source_label}."
    return prefix


def _mode_specific_reminder(mode_name: str, phase_name: str) -> str:
    if mode_name == "ASK":
        return (
            "ASK mode is read-only and answer-focused. You may use read-only "
            "tools that appear in the current schema to inspect context, but do "
            "not create, modify, delete, execute shell commands, or claim "
            "AGENT/PLAN actions are being performed. If state-changing execution "
            "or plan creation is needed, explain the needed mode switch instead."
        )
    if mode_name == "AGENT":
        return (
            "AGENT mode should solve the user's request by using relevant active "
            "tools from the current registry when useful. Do not say tools or "
            "custom tools are unavailable before checking the active tool list. "
            "Use only tools allowed by current permissions and approval policy."
        )
    if mode_name == "PLAN":
        if phase_name:
            return (
                f"PLAN mode is active in {phase_name} phase. Produce or revise "
                "a PLAN draft, plan JSON, approved plan execution, or verification "
                "result according to the phase contract. Do not behave as ASK or "
                "AGENT unless the phase contract explicitly allows it."
            )
        return (
            "PLAN mode is active. Produce or revise a PLAN draft, plan JSON, "
            "approved plan execution, or verification result according to the "
            "current phase contract. Do not behave as ASK or AGENT unless the "
            "phase contract explicitly allows it."
        )
    if mode_name == "COORDINATOR":
        return (
            "COORDINATOR mode should decompose, dispatch, synthesize, and verify "
            "work across sub-agents or phases while respecting active tool "
            "visibility and approval policy."
        )
    return ""


def _normalize_mode_name(value: Any) -> str:
    if isinstance(value, AgentMode):
        return value.name
    if hasattr(value, "name"):
        name = str(getattr(value, "name", "")).strip()
        if name:
            return name.upper()
    if hasattr(value, "value"):
        value = getattr(value, "value")
    normalized = str(value or "").strip().upper()
    mode_aliases = {
        "ASK": "ASK",
        "AGENT": "AGENT",
        "PLAN": "PLAN",
        "COORDINATOR": "COORDINATOR",
    }
    return mode_aliases.get(normalized, normalized)


def _normalize_phase_name(value: Any) -> str:
    if isinstance(value, PlanPhase):
        return value.name
    if hasattr(value, "name"):
        name = str(getattr(value, "name", "")).strip()
        if name:
            return name.upper()
    if hasattr(value, "value"):
        value = getattr(value, "value")
    return str(value or "").strip().upper()
