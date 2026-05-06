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

def setup_engine(
    sm: TheseusStateMachine,
    user_level: int,
    project_tool_permissions: dict,
    permission_prompt_func,
    user_query: Optional[str] = None,
    top_k: int = 10,
    history_messages: Optional[list] = None,
    api_client: Optional[TheseusLLMClient] = None,
    enable_dynamic_tools: bool = THESEUS_DYNAMIC_TOOL_RETRIEVAL,
):
    # 세션 시작 시 통계 및 비용 추적기 초기화
    SessionStats.reset()
    tracker = CostTracker.reset()

    # 3단계 메모리 컨텍스트 로드
    scoped_memory = ScopedMemory(cwd=Path.cwd())
    scoped_memory.ensure_gitignore()
    memory_context = scoped_memory.read_context()

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
    rag_failed = False  # RAG 실패 여부 추적

    if enable_dynamic_tools and user_query:
        try:
            print(f"🔍 질의 기반 도구 최적화 중 (Top-{top_k})...")
            retriever = ToolRetriever(full_registry)
            selected_tools = retriever.retrieve_top_k(
                user_query,
                full_registry,
                k=top_k,
                history_messages=history_messages,
            )

            # ESSENTIAL_TOOL_NAMES만 반환된 경우 = 유사도 기반 선택이 0개 → RAG 실패
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
            rag_failed = True  # 예외 발생도 폴백 트리거
    # --------------------------------------------------------------

    settings = PermissionSettings()
    # require_human_confirm=False: HITL 훅이 이미 is_destructive 툴에 대해 사람 확인을 담당.
    # 권한 체커가 추가로 묻지 않도록 False로 고정. (RBAC 레벨 체크만 수행)
    permission_checker = TheseusPermissionChecker(
        settings, user_level, project_tool_permissions,
        require_human_confirm=False,
    )
    
    # 6단계: Hook Executor 및 Security Validator 주입
    enable_hooks = os.getenv("THESEUS_ENABLE_AGENT_HOOK", "false").lower() == "true"
    hook_executor = None

    # 필터링된 레지스트리 생성
    # create_tool은 PLAN EXECUTING 단계에서만 활성화 — 나머지 모드에서는 제외
    is_plan_executing = (
        sm.mode == AgentMode.PLAN
        and getattr(sm, "plan_phase", None) == PlanPhase.EXECUTING
    )
    exclude = set() if is_plan_executing else {"create_tool"}
    active_registry = build_filtered_registry(
        current_registry, project_tool_permissions, user_level, exclude_tools=exclude
    )

    # RAG 폴백: 유사도 선택 실패 시 ToolSearchTool을 active_registry에 주입
    if rag_failed and active_registry.get("tool_search") is None:
        active_registry.register(ToolSearchTool())
        print("🔧 ToolSearchTool이 폴백으로 활성화되었습니다.")

    if enable_hooks:
        hook_registry = HookRegistry()
        # AgentHook 추가 (파일 수정 감시 - read_file 제외)
        agent_hook = AgentHookDefinition(
            prompt=(
                "You are a security auditor. Does this file modification look safe, non-destructive, and not malicious? "
                "Return strict JSON: {\"ok\": true} or {\"ok\": false, \"reason\": \"...\"}. "
                "IMPORTANT: DO NOT use markdown backticks or any other formatting. Output raw JSON only. "
                "Arguments: $ARGUMENTS"
            ),
            matcher="*_file", # Matches write_file, edit_file (and potentially others, but glob is limited)
            block_on_failure=True
        )
        hook_registry.register(HookEvent.PRE_TOOL_USE, agent_hook)

        # read_file은 감시 대상에서 제외하기 위해 별도 처리 (fnmatch는 exclusion이 어려움)
        # 만약 *_file이 read_file을 포함한다면, TheseusHookExecutor에서 필터링하거나
        # 여기서 구체적인 이름으로 여러 개 등록합니다.
        # 여기서는 가장 확실하게 개별 등록하겠습니다.
        hook_registry = HookRegistry() # Reset to avoid duplicate *file hook if it existed
        for tool_to_audit in ["write_file", "edit_file"]:
            h = AgentHookDefinition(
                prompt=agent_hook.prompt,
                matcher=tool_to_audit,
                block_on_failure=True
            )
            hook_registry.register(HookEvent.PRE_TOOL_USE, h)
        
        hook_context = HookExecutionContext(
            cwd=Path.cwd(),
            api_client=api_client,
            default_model=model_name,
        )
        
        hook_executor = TheseusHookExecutor(
            hook_registry,
            hook_context,
            active_registry=active_registry,
            full_registry=full_registry,
            enable_dynamic_tools=enable_dynamic_tools,
            permission_prompt=permission_prompt_func,
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
