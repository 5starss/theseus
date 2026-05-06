import logging
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Awaitable, Callable, Literal

from src.auth.schemas import SessionContext
from src.db.postgres import SessionLocal
from src.plan.service import assert_plan_execution_context
from src.tooling import load_custom_tools_for_project
from theseus_engine.models.state import AgentMode, TheseusStateMachine
from theseus_engine.models.state import PlanPhase

logger = logging.getLogger(__name__)

ApprovalPolicy = Literal["reject", "allow_safe_only"]


class EngineInitializationError(ImportError):
    """Raised when the Theseus engine cannot be assembled safely."""


@dataclass(slots=True)
class EngineBuildContext:
    """Server-side context used to assemble a Theseus query engine."""

    user_level: int
    project_tool_permissions: dict[str, int]
    mode: AgentMode = AgentMode.AGENT
    approval_policy: ApprovalPolicy = "reject"
    user_query: str | None = None
    history_messages: list[Any] | None = None
    session_id: str = "default"
    project_id: str | None = None
    actor_user_id: str | None = None
    chat_session_id: int | None = None
    plan_id: str | None = None
    plan_content: dict[str, Any] | None = None


@dataclass(slots=True)
class EngineAssembly:
    """Server-safe QueryEngine bundle."""

    engine: Any
    model_name: str
    allowed_tools: tuple[str, ...]
    assistant_text_delta_type: type
    tool_execution_started_type: type
    tool_execution_completed_type: type
    error_event_type: type


def _resolve_model_name() -> str:
    return os.getenv("OPENHARNESS_MODEL", "gpt-4o")


def _infer_registry_permissions(full_registry: Any) -> dict[str, int]:
    permissions: dict[str, int] = {}
    for tool in full_registry.list_tools():
        permissions[tool.name] = getattr(tool, "permission_level", 1)
    return permissions


def _resolve_excluded_tools(mode: AgentMode) -> set[str]:
    # Server route only supports AGENT initially. Keep create_tool out of
    # non-Plan modes so the server cannot expose meta-tooling prematurely.
    if mode != AgentMode.PLAN:
        return {"create_tool"}
    return set()


async def _enforce_executing_plan_guard(
    build_context: EngineBuildContext,
    tool_name: str,
) -> None:
    if tool_name != "create_tool":
        return
    if not build_context.plan_id:
        raise EngineInitializationError("create_tool requires an executing plan")
    if (
        not build_context.project_id
        or not build_context.actor_user_id
        or build_context.chat_session_id is None
    ):
        raise EngineInitializationError(
            "create_tool requires project, user, and chat session context"
        )
    db = SessionLocal()
    try:
        assert_plan_execution_context(
            db,
            plan_id=build_context.plan_id,
            project_id=build_context.project_id,
            chat_session_id=build_context.chat_session_id,
            executing_user_id=build_context.actor_user_id,
        )
    except RuntimeError as exc:
        raise EngineInitializationError(str(exc)) from exc
    finally:
        db.close()


async def _deny_permission_prompt(tool_name: str, reason: str) -> bool:
    logger.warning(
        "Server denied approval-required tool '%s': %s",
        tool_name,
        reason,
    )
    return False


def _coerce_context(
    context: EngineBuildContext | SessionContext,
) -> EngineBuildContext:
    if isinstance(context, EngineBuildContext):
        return context

    logger.warning(
        "Legacy SessionContext passed to get_query_engine; using inferred "
        "tool permissions until the stream route provides explicit permissions."
    )
    return EngineBuildContext(
        user_level=context.permission_level,
        project_tool_permissions={},
        mode=AgentMode.AGENT,
        approval_policy="reject",
        session_id=f"{context.project_id}:{context.user_id}",
        project_id=context.project_id,
        actor_user_id=context.user_id,
    )


def get_query_engine(
    context: EngineBuildContext | SessionContext,
) -> EngineAssembly:
    """Assemble a server-side Theseus QueryEngine."""

    build_context = _coerce_context(context)

    try:
        from openharness.config.settings import PermissionSettings
        from openharness.engine.query_engine import QueryEngine
        from openharness.engine.stream_events import (
            AssistantTextDelta,
            ErrorEvent,
            ToolExecutionCompleted,
            ToolExecutionStarted,
        )
        from openharness.hooks.executor import HookExecutionContext
        from openharness.hooks.loader import HookRegistry
        from openharness.tools import create_default_tool_registry
        from theseus_engine.models.rbac import TheseusPermissionChecker
        from theseus_engine.tools.core import ALL_CORE_TOOLS, build_filtered_registry, load_custom_tools
        from theseus_engine.wrappers.hooks.theseus_hook_executor import (
            TheseusHookExecutor,
        )
        from theseus_engine.wrappers.llm_clients.theseus_client import (
            TheseusLLMClient,
        )
    except ImportError as exc:
        raise EngineInitializationError(
            "OpenHarness is not available in the current Python environment."
        ) from exc

    if not isinstance(build_context.mode, AgentMode):
        raise EngineInitializationError("Engine mode must be a valid AgentMode.")

    model_name = _resolve_model_name()
    api_client = TheseusLLMClient(model_name)

    full_registry = create_default_tool_registry()
    for tool_cls in ALL_CORE_TOOLS:
        full_registry.register(tool_cls())

    inferred_permissions = _infer_registry_permissions(full_registry)
    tool_permissions = dict(inferred_permissions)
    tool_permissions.update(build_context.project_tool_permissions)

    if build_context.project_id:
        loaded_tools = load_custom_tools_for_project(
            full_registry,
            project_id=build_context.project_id,
            tool_permissions=tool_permissions,
        )
    else:
        loaded_tools = load_custom_tools(full_registry, tool_permissions)
    if loaded_tools:
        logger.info(
            "Loaded %d custom tools into server registry for session %s.",
            len(loaded_tools),
            build_context.session_id,
        )

    active_registry = build_filtered_registry(
        full_registry,
        tool_permissions,
        build_context.user_level,
        exclude_tools=_resolve_excluded_tools(build_context.mode),
    )
    allowed_tools = tuple(tool.name for tool in active_registry.list_tools())
    if not allowed_tools:
        raise EngineInitializationError(
            "No tools are available for the current server session."
        )

    state_machine = TheseusStateMachine(initial_mode=build_context.mode)
    if build_context.mode == AgentMode.PLAN:
        state_machine.set_plan_phase(PlanPhase.EXECUTING)
        if build_context.plan_content is not None:
            state_machine.plan = str(build_context.plan_content)
    permission_checker = TheseusPermissionChecker(
        settings=PermissionSettings(),
        user_level=build_context.user_level,
        tool_permissions=tool_permissions,
    )

    hook_registry = HookRegistry()
    hook_context = HookExecutionContext(
        cwd=Path.cwd(),
        api_client=api_client,
        default_model=model_name,
    )
    hook_executor = TheseusHookExecutor(
        hook_registry,
        hook_context,
        active_registry=active_registry,
        full_registry=None,
        pre_tool_guard=lambda tool_name: _enforce_executing_plan_guard(build_context, tool_name),
    )

    engine = QueryEngine(
        api_client=api_client,
        tool_registry=active_registry,
        permission_checker=permission_checker,
        hook_executor=hook_executor,
        cwd=Path.cwd(),
        model=model_name,
        system_prompt=state_machine.get_system_prompt(),
        max_turns=30,
        permission_prompt=_deny_permission_prompt,
        tool_metadata={
            "tool_registry": full_registry,
            "tool_permissions": tool_permissions,
            "permission_prompt": _deny_permission_prompt,
            "session_id": build_context.session_id,
            "project_id": build_context.project_id,
            "user_id": build_context.actor_user_id,
            "chat_session_id": build_context.chat_session_id,
            "plan_id": build_context.plan_id,
        },
    )

    if build_context.history_messages:
        engine.load_messages(build_context.history_messages)

    return EngineAssembly(
        engine=engine,
        model_name=model_name,
        allowed_tools=allowed_tools,
        assistant_text_delta_type=AssistantTextDelta,
        tool_execution_started_type=ToolExecutionStarted,
        tool_execution_completed_type=ToolExecutionCompleted,
        error_event_type=ErrorEvent,
    )
