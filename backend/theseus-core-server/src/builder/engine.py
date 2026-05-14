import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Awaitable, Callable, Literal

from src.auth.schemas import SessionContext
from src.builder.system_prompt import build_theseus_system_prompt
from src.config import resolve_model_name
from src.db.postgres import SessionLocal
from src.plan.service import assert_plan_execution_context
from src.remote_workspace.read_primitives import (
    REMOTE_READ_ANALYSIS_TOOL_NAMES,
    build_remote_read_analysis_tools,
)
from src.remote_workspace.schemas import RemoteWorkspaceConnectionConfig
from src.remote_workspace.runtime import (
    REMOTE_WORKSPACE_RUNTIME_KEY,
    register_remote_workspace_config,
)
from src.remote_workspace.write_primitives import (
    REMOTE_WRITE_EXECUTION_TOOL_NAMES,
    build_remote_write_execution_tools,
)
from src.tooling import load_custom_tools_for_project
from theseus_engine.engine.query_engine import QueryEngine
from theseus_engine.engine.stream_events import (
    AssistantTextDelta,
    ErrorEvent,
    ToolExecutionCompleted,
    ToolExecutionStarted,
)
from theseus_engine.models.rbac import TheseusPermissionChecker, TheseusPermissionSettings
from theseus_engine.models.state import AgentMode, PlanPhase
from theseus_engine.tools.core import ALL_CORE_TOOLS, build_filtered_registry, load_custom_tools
from theseus_engine.tools.core.base_tools import ToolRegistry
from theseus_engine.tools.tool_repair import ToolRepairPolicy
from theseus_engine.wrappers.hooks.theseus_hook_executor import (
    AggregatedHookResult,
    HookEvent,
    HookResult,
    TheseusHookExecutor,
)
from theseus_engine.wrappers.llm_clients.theseus_client import TheseusLLMClient

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
    plan_phase: PlanPhase | None = None
    remote_workspace_id: int | None = None
    remote_workspace: RemoteWorkspaceConnectionConfig | None = None


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


def _infer_registry_permissions(full_registry: Any) -> dict[str, int]:
    permissions: dict[str, int] = {}
    for tool in full_registry.list_tools():
        permissions[tool.name] = getattr(tool, "permission_level", 1)
    return permissions


_PLAN_DRAFTING_ALLOWED_TOOLS = frozenset(
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
_LOCAL_REMOTE_OVERLAP_TOOL_NAMES = frozenset(
    {"read_file", "glob", "grep", "bash", "write_file", "edit_file"}
)


def _all_tool_names(full_registry: ToolRegistry) -> set[str]:
    return {tool.name for tool in full_registry.list_tools()}


def _resolve_plan_phase(build_context: EngineBuildContext) -> PlanPhase | None:
    if build_context.mode != AgentMode.PLAN:
        return None
    if build_context.plan_phase is not None:
        return build_context.plan_phase
    if build_context.plan_id:
        return PlanPhase.EXECUTING
    return PlanPhase.DRAFTING


def _allows_remote_write_execution(
    mode: AgentMode,
    plan_phase: PlanPhase | None,
    remote_workspace: RemoteWorkspaceConnectionConfig | None,
) -> bool:
    del plan_phase
    if mode == AgentMode.AGENT:
        return bool(remote_workspace and remote_workspace.allow_write_execution)
    return False


def _resolve_excluded_tools(
    mode: AgentMode,
    plan_phase: PlanPhase | None,
    full_registry: ToolRegistry,
    *,
    has_remote_workspace: bool,
    allow_remote_write_execution: bool,
) -> set[str]:
    all_tool_names = _all_tool_names(full_registry)
    if mode == AgentMode.ASK:
        if has_remote_workspace:
            return all_tool_names - REMOTE_READ_ANALYSIS_TOOL_NAMES
        return all_tool_names
    if mode == AgentMode.PLAN and plan_phase in {
        PlanPhase.DRAFTING,
        PlanPhase.WAIT_FOR_REVIEW,
    }:
        allowed_tools = set(_PLAN_DRAFTING_ALLOWED_TOOLS)
        if has_remote_workspace:
            allowed_tools.difference_update(_LOCAL_REMOTE_OVERLAP_TOOL_NAMES)
            allowed_tools.update(REMOTE_READ_ANALYSIS_TOOL_NAMES)
        return all_tool_names - allowed_tools
    if mode != AgentMode.PLAN:
        excluded_tools = {"create_tool"}
        if has_remote_workspace:
            excluded_tools.update(_LOCAL_REMOTE_OVERLAP_TOOL_NAMES)
            if not allow_remote_write_execution:
                excluded_tools.update(REMOTE_WRITE_EXECUTION_TOOL_NAMES)
        return excluded_tools
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


class ServerHookExecutor:
    """Adds server-only guards around the native Theseus hook executor."""

    def __init__(
        self,
        *,
        delegate: TheseusHookExecutor,
        pre_tool_guard: Callable[[str], Awaitable[None]] | None = None,
    ) -> None:
        self._delegate = delegate
        self._pre_tool_guard = pre_tool_guard

    async def execute(self, event: HookEvent, payload: dict[str, Any]) -> AggregatedHookResult:
        if event == HookEvent.PRE_TOOL_USE and self._pre_tool_guard is not None:
            tool_name = str(payload.get("tool_name") or "")
            try:
                await self._pre_tool_guard(tool_name)
            except Exception as exc:
                return AggregatedHookResult(
                    results=[
                        HookResult(
                            hook_type="server_plan_guard",
                            success=False,
                            blocked=True,
                            reason=str(exc),
                        )
                    ]
                )
        return await self._delegate.execute(event, payload)


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

    if not isinstance(build_context.mode, AgentMode):
        raise EngineInitializationError("Engine mode must be a valid AgentMode.")

    plan_phase = _resolve_plan_phase(build_context)
    allow_remote_write_execution = _allows_remote_write_execution(
        build_context.mode,
        plan_phase,
        build_context.remote_workspace,
    )
    model_name = resolve_model_name()
    api_client = TheseusLLMClient(model_name)

    full_registry = ToolRegistry()
    for tool_cls in ALL_CORE_TOOLS:
        full_registry.register(tool_cls())
    if build_context.remote_workspace is not None:
        for tool in build_remote_read_analysis_tools(build_context.remote_workspace):
            full_registry.register(tool)
        if allow_remote_write_execution:
            for tool in build_remote_write_execution_tools(build_context.remote_workspace):
                full_registry.register(tool)
    remote_workspace_runtime_key = (
        register_remote_workspace_config(build_context.remote_workspace)
        if build_context.remote_workspace is not None
        else None
    )

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
        exclude_tools=_resolve_excluded_tools(
            build_context.mode,
            plan_phase,
            full_registry,
            has_remote_workspace=build_context.remote_workspace is not None,
            allow_remote_write_execution=allow_remote_write_execution,
        ),
    )
    allowed_tools = tuple(tool.name for tool in active_registry.list_tools())
    if not allowed_tools and build_context.mode != AgentMode.ASK:
        raise EngineInitializationError(
            "No tools are available for the current server session."
        )

    system_prompt = build_theseus_system_prompt(
        mode=build_context.mode,
        plan_phase=plan_phase,
        plan_content=build_context.plan_content,
        available_tools=allowed_tools,
    )
    permission_checker = TheseusPermissionChecker(
        settings=TheseusPermissionSettings(),
        user_level=build_context.user_level,
        tool_permissions=tool_permissions,
    )

    base_hook_executor = TheseusHookExecutor(
        active_registry=active_registry,
        full_registry=full_registry,
        llm_client=api_client,
    )
    hook_executor = ServerHookExecutor(
        delegate=base_hook_executor,
        pre_tool_guard=lambda tool_name: _enforce_executing_plan_guard(build_context, tool_name),
    )

    engine = QueryEngine(
        api_client=api_client,
        tool_registry=active_registry,
        permission_checker=permission_checker,
        hook_executor=hook_executor,
        cwd=Path.cwd(),
        model=model_name,
        system_prompt=system_prompt,
        max_turns=30,
        permission_prompt=_deny_permission_prompt,
        tool_metadata={
            "tool_registry": full_registry,
            "tool_permissions": tool_permissions,
            "llm_client": api_client,
            "model_name": model_name,
            "tool_repair_policy": ToolRepairPolicy.from_env(),
            "permission_prompt": _deny_permission_prompt,
            "session_id": build_context.session_id,
            "project_id": build_context.project_id,
            "user_id": build_context.actor_user_id,
            "chat_session_id": build_context.chat_session_id,
            "plan_id": build_context.plan_id,
            "agent_mode": build_context.mode.value,
            "plan_phase": plan_phase.value if plan_phase is not None else None,
            "remote_workspace_id": build_context.remote_workspace_id,
            REMOTE_WORKSPACE_RUNTIME_KEY: remote_workspace_runtime_key,
            "remote_workspace": (
                build_context.remote_workspace.redacted_model_dump(by_alias=True)
                if build_context.remote_workspace is not None
                else None
            ),
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
