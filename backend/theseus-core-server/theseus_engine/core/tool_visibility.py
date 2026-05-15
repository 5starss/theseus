"""Shared tool visibility policy for Theseus runtimes.

This module keeps mode/phase/RBAC filtering inside ``theseus_engine`` so the
server builder, editor runtime, TUI, and CLI command handler do not each carry
their own slightly different ``exclude_tools`` rules.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Mapping

from theseus_engine.models.modes import AgentMode, PlanPhase
from theseus_engine.tools.core.base_tools import ToolRegistry


PLAN_DRAFTING_ALLOWED_TOOLS = frozenset(
    {
        "read_file",
        "glob",
        "grep",
        "web_fetch",
        "web_search",
        "deep_research",
        "lsp",
        "list_mcp_resources",
        "read_mcp_resource",
        "skill_read",
        "skill_list",
        "search_knowledge_base",
        "memory_read",
        "memory_list",
        "tool_search",
        "brief",
    }
)

ASK_ALLOWED_TOOLS = PLAN_DRAFTING_ALLOWED_TOOLS

REMOTE_READ_ANALYSIS_TOOL_NAMES = frozenset(
    {
        "remote_read_file",
        "remote_glob",
        "remote_grep",
        "remote_tail_log",
        "remote_check_cpu",
        "remote_check_memory",
        "remote_check_disk",
    }
)

REMOTE_WRITE_EXECUTION_TOOL_NAMES = frozenset(
    {
        "remote_write_file",
        "remote_edit_file",
        "remote_run_command",
    }
)

LOCAL_REPORT_WRITE_TOOL_NAMES = frozenset({"local_write_report"})


@dataclass(frozen=True)
class ToolVisibilityPolicy:
    """Inputs used to derive the active tool registry for one runtime turn."""

    mode: AgentMode
    user_level: int
    tool_permissions: Mapping[str, int] = field(default_factory=dict)
    plan_phase: PlanPhase | None = None
    can_create_tool: bool = False
    disabled_tools: frozenset[str] = field(default_factory=frozenset)
    has_remote_workspace: bool = False
    allow_remote_write_execution: bool = False
    allow_local_report_write: bool = False
    default_permission_level: int = 1


def all_tool_names(registry: ToolRegistry) -> set[str]:
    return {tool.name for tool in registry.list_tools()}


def resolve_plan_phase(
    *,
    mode: AgentMode,
    explicit_phase: PlanPhase | None = None,
    has_executing_plan: bool = False,
) -> PlanPhase | None:
    """Resolve a missing plan phase using the same fallback across runtimes."""

    if mode != AgentMode.PLAN:
        return None
    if explicit_phase is not None:
        return explicit_phase
    if has_executing_plan:
        return PlanPhase.EXECUTING
    return PlanPhase.DRAFTING


def can_create_tool_for_state(
    *,
    mode: AgentMode,
    plan_phase: PlanPhase | None,
    project_id: str | None = None,
    actor_role: str = "MEMBER",
) -> bool:
    """Return whether create_tool may be visible in the current runtime state."""

    is_plan_executing = mode == AgentMode.PLAN and plan_phase == PlanPhase.EXECUTING
    if not is_plan_executing:
        return False
    return project_id is None or actor_role.upper() == "ADMIN"


def resolve_excluded_tool_names(
    registry: ToolRegistry,
    policy: ToolVisibilityPolicy,
) -> set[str]:
    """Resolve tool names that should not be exposed to the model."""

    names = all_tool_names(registry)
    excluded = set(policy.disabled_tools)
    if not policy.has_remote_workspace or not policy.allow_local_report_write:
        excluded.update(LOCAL_REPORT_WRITE_TOOL_NAMES)

    if policy.mode == AgentMode.ASK:
        allowed = set(ASK_ALLOWED_TOOLS)
        if policy.has_remote_workspace:
            allowed.update(REMOTE_READ_ANALYSIS_TOOL_NAMES)
        excluded.update(names - allowed)
        return excluded

    if policy.mode == AgentMode.PLAN and policy.plan_phase in {
        PlanPhase.DRAFTING,
        PlanPhase.WAIT_FOR_REVIEW,
    }:
        allowed = set(PLAN_DRAFTING_ALLOWED_TOOLS)
        if policy.has_remote_workspace:
            allowed.update(REMOTE_READ_ANALYSIS_TOOL_NAMES)
        excluded.update(names - allowed)
        return excluded

    if not policy.can_create_tool:
        excluded.add("create_tool")

    if policy.has_remote_workspace and not policy.allow_remote_write_execution:
        excluded.update(REMOTE_WRITE_EXECUTION_TOOL_NAMES)

    return excluded


def build_visible_registry(
    full_registry: ToolRegistry,
    policy: ToolVisibilityPolicy,
) -> ToolRegistry:
    """Create a ToolRegistry filtered by mode, project policy, and RBAC."""

    excluded = resolve_excluded_tool_names(full_registry, policy)
    active = ToolRegistry()
    for tool in full_registry.list_tools():
        if tool.name in excluded:
            continue
        required = policy.tool_permissions.get(
            tool.name,
            getattr(tool, "permission_level", policy.default_permission_level),
        )
        if policy.user_level >= required:
            active.register(tool)
    return active


def active_tool_names(registry: ToolRegistry | None) -> tuple[str, ...]:
    if registry is None:
        return ()
    return tuple(tool.name for tool in registry.list_tools())
