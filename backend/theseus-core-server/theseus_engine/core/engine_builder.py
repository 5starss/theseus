import os
from pathlib import Path
from typing import Optional

# OpenHarness / Theseus imports
from openharness.engine.query_engine import QueryEngine
from openharness.tools import create_default_tool_registry
from openharness.config.settings import PermissionSettings
from openharness.hooks.events import HookEvent
from openharness.hooks.loader import HookRegistry
from openharness.hooks.schemas import AgentHookDefinition
from openharness.hooks.executor import HookExecutionContext

from theseus_engine.wrappers.llm_clients.theseus_client import TheseusLLMClient
from theseus_engine.models.state import TheseusStateMachine
from theseus_engine.tools.core import (
    ALL_CORE_TOOLS,
    build_filtered_registry,
    load_custom_tools,
)
from theseus_engine.models.rbac import TheseusPermissionChecker
from theseus_engine.wrappers.hooks.theseus_hook_executor import (
    TheseusHookExecutor,
)
from theseus_engine.observability.tracer import is_tracing_enabled
from theseus_engine.core.tool_retriever import ToolRetriever, build_retrieved_registry

def setup_engine(
    sm: TheseusStateMachine,
    user_level: int,
    project_tool_permissions: dict,
    permission_prompt_func,
    user_query: Optional[str] = None,
    top_k: int = 10,
    history_messages: Optional[list] = None,
    api_client: Optional[TheseusLLMClient] = None,
):
    model_name = os.getenv("OPENHARNESS_MODEL", "gpt-4o")
    if api_client is None:
        api_client = TheseusLLMClient(model_name)

    full_registry = create_default_tool_registry()

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
    if user_query:
        try:
            print(f"🔍 질의 기반 도구 최적화 중 (Top-{top_k})...")
            retriever = ToolRetriever(full_registry)
            selected_tools = retriever.retrieve_top_k(
                user_query,
                full_registry,
                k=top_k,
                history_messages=history_messages,
            )

            if selected_tools:
                current_registry = build_retrieved_registry(selected_tools)
                print(f"🎯 선택된 도구: {', '.join([t.name for t in selected_tools])}")
            else:
                print("⚠️ 관련 도구를 찾지 못했습니다. 전체 레지스트리를 사용합니다.")
        except Exception as _e:
            import logging as _logging
            _logging.getLogger(__name__).warning(
                "[ToolRetriever] 도구 검색 실패, 전체 레지스트리 사용: %s", _e,
            )
            print("⚠️ 도구 검색 중 오류 발생. 전체 레지스트리를 사용합니다.")
    # --------------------------------------------------------------

    settings = PermissionSettings()
    permission_checker = TheseusPermissionChecker(settings, user_level, project_tool_permissions)

    # ==============================================================
    # [Task 1.2] OpenHarness Official Hook Pipeline Integration
    # ==============================================================
    hook_registry = HookRegistry()
    
    # Optional: Enable Agent validation hook for file writing tools
    if os.getenv("THESEUS_ENABLE_AGENT_HOOK", "false").lower() == "true":
        agent_hook = AgentHookDefinition(
            prompt="You are a security auditor. Does this file modification look safe, non-destructive, and not malicious? Arguments: $ARGUMENTS",
            matcher="*file*", # matches write_file, edit_file, read_file
            block_on_failure=True
        )
        hook_registry.register(HookEvent.PRE_TOOL_USE, agent_hook)
        print("✅ Registered AgentHookDefinition for file operations.")

    hook_context = HookExecutionContext(
        cwd=Path.cwd(), 
        api_client=api_client, 
        default_model=model_name
    )

    # 필터링된 레지스트리를 먼저 생성하여 HookExecutor에 전달
    active_registry = build_filtered_registry(
        current_registry, project_tool_permissions, user_level, exclude_tools={"create_tool"}
    )
    
    hook_executor = TheseusHookExecutor(
        hook_registry, 
        hook_context,
        active_registry=active_registry,
        full_registry=full_registry
    )
    # ==============================================================

    engine = QueryEngine(
        api_client=api_client,
        tool_registry=active_registry,
        permission_checker=permission_checker,
        hook_executor=hook_executor,
        cwd=Path.cwd(),
        model=model_name,
        system_prompt=sm.get_system_prompt(),
        max_turns=30,
        permission_prompt=permission_prompt_func,
        tool_metadata={
            "tool_registry": full_registry,
            "tool_permissions": project_tool_permissions,
        }
    )

    # ==============================================================
    # [Task 1.4] Observability: 트레이싱 메타데이터 로깅
    # ==============================================================
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
