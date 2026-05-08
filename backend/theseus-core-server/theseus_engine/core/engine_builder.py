import os
from pathlib import Path
from typing import Optional

from theseus_engine.engine.query_engine import QueryEngine
from theseus_engine.tools.core.base_tools import ToolRegistry

from theseus_engine.wrappers.llm_clients.theseus_client import TheseusLLMClient
from theseus_engine.models.state import TheseusStateMachine, AgentMode, PlanPhase
from theseus_engine.tools.core import (
    ALL_CORE_TOOLS,
    build_filtered_registry,
    load_custom_tools,
    ToolSearchTool,
)
from theseus_engine.core.tool_retriever import ESSENTIAL_TOOL_NAMES
from theseus_engine.models.rbac import TheseusPermissionChecker
from theseus_engine.wrappers.hooks.theseus_hook_executor import (
    TheseusHookExecutor,
)
from theseus_engine.observability.tracer import is_tracing_enabled
from theseus_engine.observability.stats import SessionStats
from theseus_engine.engine.cost_tracker import CostTracker
from theseus_engine.memory.scoped_memory import ScopedMemory
from theseus_engine.core.tool_retriever import ToolRetriever, build_retrieved_registry

# 동적 도구 활성화 여부 (기본값 True)
THESEUS_DYNAMIC_TOOL_RETRIEVAL = (
    os.getenv("THESEUS_DYNAMIC_TOOL_RETRIEVAL", "true").lower() == "true"
)

async def setup_engine(
    sm: TheseusStateMachine,
    user_level: int,
    project_tool_permissions: dict,
    permission_prompt_func,
    user_query: Optional[str] = None,
    top_k: int = 10,
    history_messages: Optional[list] = None,
    api_client: Optional[TheseusLLMClient] = None,
    enable_dynamic_tools: bool = THESEUS_DYNAMIC_TOOL_RETRIEVAL,
    reset_stats: bool = False,
):
    if reset_stats:
        SessionStats.reset()
        CostTracker.reset()
    tracker = CostTracker.get_or_create()

    scoped_memory = ScopedMemory(cwd=Path.cwd())
    scoped_memory.ensure_gitignore()
    memory_context = scoped_memory.read_context()

    model_name = os.getenv("OPENHARNESS_MODEL", "gpt-4o")
    if api_client is None:
        api_client = TheseusLLMClient(model_name)

    # Theseus 자체 ToolRegistry로 시작 — create_default_tool_registry() 사용하지 않음
    full_registry = ToolRegistry()

    # ALL_CORE_TOOLS에서 모든 핵심 도구를 자동 등록
    for tool_cls in ALL_CORE_TOOLS:
        full_registry.register(tool_cls())

    loaded_tools = load_custom_tools(full_registry, project_tool_permissions)
    if loaded_tools:
        print(f"✅ Loaded {len(loaded_tools)} custom tools.")

    # --------------------------------------------------------------
    # 동적 도구 선택 (Top-K Tool Retrieval)
    # --------------------------------------------------------------
    current_registry = full_registry
    rag_failed = False

    if enable_dynamic_tools and user_query:
        try:
            print(f"🔍 질의 기반 도구 최적화 중 (Top-{top_k})...")
            retriever = ToolRetriever(full_registry)
            selected_tools = await retriever.retrieve_top_k(
                user_query,
                full_registry,
                k=top_k,
                history_messages=history_messages,
            )

            selected_names = {t.name for t in selected_tools}
            similarity_added = len(selected_names - ESSENTIAL_TOOL_NAMES)
            rag_failed = similarity_added == 0

            if selected_tools:
                current_registry = build_retrieved_registry(selected_tools)
                print(f"🎯 선택된 도구: {', '.join([t.name for t in selected_tools])}")

            if rag_failed:
                print("⚠️ RAG 유사도 선택 실패 (필수 도구만 반환) → ToolSearchTool 활성화")
            else:
                print("⚠️ 관련 도구를 찾지 못했습니다. 전체 레지스트리를 사용합니다.")
        except Exception as _e:
            import logging as _logging
            _logging.getLogger(__name__).warning(
                "[ToolRetriever] 도구 검색 실패, 전체 레지스트리 사용: %s", _e,
            )
            print("⚠️ 도구 검색 중 오류 발생. 전체 레지스트리를 사용합니다.")
            rag_failed = True
    # --------------------------------------------------------------

    # Theseus 자체 PermissionSettings — OpenHarness PermissionSettings 제거
    from theseus_engine.models.rbac import TheseusPermissionSettings
    settings = TheseusPermissionSettings()
    permission_checker = TheseusPermissionChecker(
        settings, user_level, project_tool_permissions,
        require_human_confirm=False,
    )

    enable_hooks = os.getenv("THESEUS_ENABLE_AGENT_HOOK", "false").lower() == "true"
    hook_executor = None

    # create_tool은 PLAN EXECUTING 단계에서만 활성화
    is_plan_executing = (
        sm.mode == AgentMode.PLAN
        and getattr(sm, "plan_phase", None) == PlanPhase.EXECUTING
    )
    if is_plan_executing and current_registry.get("create_tool") is None:
        creator = full_registry.get("create_tool")
        if creator is not None:
            current_registry.register(creator)
    exclude = set() if is_plan_executing else {"create_tool"}
    active_registry = build_filtered_registry(
        current_registry, project_tool_permissions, user_level, exclude_tools=exclude
    )

    if rag_failed and active_registry.get("tool_search") is None:
        active_registry.register(ToolSearchTool())
        print("🔧 ToolSearchTool이 폴백으로 활성화되었습니다.")

    if enable_hooks:
        hook_executor = TheseusHookExecutor(
            active_registry=active_registry,
            full_registry=full_registry,
            enable_dynamic_tools=enable_dynamic_tools,
            permission_prompt=permission_prompt_func,
            llm_client=api_client,
            audit_tools={"write_file", "edit_file"},
        )

    # ==============================================================

    engine = QueryEngine(
        api_client=api_client,
        tool_registry=active_registry,
        permission_checker=permission_checker,
        hook_executor=hook_executor,
        cwd=Path.cwd(),
        model=model_name,
        system_prompt=(
            sm.get_system_prompt()
            + ("\n\n" + memory_context if memory_context else "")
        ),
        max_turns=30,
        permission_prompt=permission_prompt_func if callable(permission_prompt_func) else None,
        tool_metadata={
            "tool_registry": full_registry,
            "tool_permissions": project_tool_permissions,
            "active_registry": active_registry,
            "cost_tracker": tracker,
            "scoped_memory": scoped_memory,
            "user_rbac_level": user_level,
            "agent_mode": sm.mode.value if hasattr(sm, "mode") else "normal",
        }
    )

    if is_tracing_enabled():
        import logging
        _log = logging.getLogger(__name__)
        _log.info(
            "[Observability] LangSmith 트레이싱 활성화. "
            "RBAC Lv.%d | Model: %s | Mode: %s",
            user_level, model_name, sm.mode.value,
        )

    return engine, full_registry


def get_tracing_tags(
    user_level: int,
    model_name: str,
    session_name: str = "default",
) -> list[str]:
    """LangSmith Run에 부착할 태그 목록을 생성합니다."""
    return [
        f"rbac_lv{user_level}",
        f"model:{model_name}",
        f"session:{session_name}",
    ]


def get_tracing_metadata(
    user_level: int,
    model_name: str,
    session_name: str = "default",
) -> dict:
    """LangSmith Run에 부착할 메타데이터를 생성합니다."""
    return {
        "rbac_level": user_level,
        "model": model_name,
        "session": session_name,
        "platform": "theseus-core-server",
    }
