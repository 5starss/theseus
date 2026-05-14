import os
from pathlib import Path
from typing import Optional

from theseus_engine.engine.query_engine import QueryEngine
from theseus_engine.tools.core.base_tools import ToolRegistry

from theseus_engine.wrappers.llm_clients.theseus_client import TheseusLLMClient
from theseus_engine.models.modes import AgentMode
from theseus_engine.models.state import TheseusStateMachine
from theseus_engine.tools.core import (
    ALL_CORE_TOOLS,
    load_custom_tools,
    load_custom_tools_for_project,
    ToolSearchTool,
)
from theseus_engine.tools.tool_repair import ToolRepairPolicy
from theseus_engine.core.tool_retriever import ESSENTIAL_TOOL_NAMES
from theseus_engine.core.tool_visibility import (
    ToolVisibilityPolicy,
    active_tool_names,
    build_visible_registry,
    can_create_tool_for_state,
)
from theseus_engine.models.rbac import TheseusPermissionChecker
from theseus_engine.wrappers.hooks.theseus_hook_executor import (
    TheseusHookExecutor,
)
from theseus_engine.observability.tracer import is_tracing_enabled
from theseus_engine.observability.stats import SessionStats  # noqa: F401 (reset_stats 경로에서 사용)
from theseus_engine.engine.cost_tracker import CostTracker
from theseus_engine.memory.scoped_memory import ScopedMemory
from theseus_engine.core.tool_retriever import ToolRetriever, build_retrieved_registry
from theseus_engine.skills.injection import SkillInjectionConfig

# 동적 도구 활성화 여부 (기본값 True)
THESEUS_DYNAMIC_TOOL_RETRIEVAL = (
    os.getenv("THESEUS_DYNAMIC_TOOL_RETRIEVAL", "true").lower() == "true"
)


def _workspace_custom_tool_dirs(cwd: Path) -> list[Path]:
    """Return custom tool dirs owned by the active workspace."""
    candidates = [cwd / "custom_tools", cwd / "theseus_engine" / "custom_tools"]
    seen: set[str] = set()
    result: list[Path] = []
    for path in candidates:
        resolved = path.resolve()
        key = os.path.normcase(str(resolved))
        if key in seen:
            continue
        seen.add(key)
        result.append(resolved)
    return result


def _resolve_skill_injection_enabled(value: Optional[bool]) -> bool:
    if value is not None:
        return bool(value)
    raw = os.getenv("THESEUS_SKILL_AUTO_INJECTION", "true").strip().lower()
    return raw not in {"0", "false", "no", "off"}


async def setup_engine(
    sm: TheseusStateMachine,
    user_level: int,
    project_tool_permissions: dict,
    permission_prompt_func,
    # ── 프로젝트/역할 기반 툴 가시성 ─────────────────────
    project_id: Optional[str] = None,
    actor_role: str = "MEMBER",
    project_disabled_tools: Optional[set] = None,
    # ── 기존 파라미터 ────────────────────────────────────
    user_query: Optional[str] = None,
    top_k: int = 10,
    history_messages: Optional[list] = None,
    api_client: Optional[TheseusLLMClient] = None,
    enable_dynamic_tools: bool = THESEUS_DYNAMIC_TOOL_RETRIEVAL,
    enable_skill_injection: Optional[bool] = None,
    reset_stats: bool = False,
    # ── Kafka 실행 추적 ID (선택) ─────────────────────────
    run_id: Optional[str] = None,
    tool_draft_id: Optional[str] = None,
    # ── 워크스페이스 경로 (멀티유저 서버 모드) ─────────────
    cwd: Optional[Path] = None,
):
    # ── 워크스페이스 경로 결정 ─────────────────────────────
    # cwd 파라미터 우선, 없으면 프로세스 현재 디렉토리 (standalone 호환)
    resolved_cwd = cwd if cwd is not None else Path.cwd()

    # ── 통계/비용 추적기: 요청 스코프 인스턴스 ─────────────
    # 싱글톤 reset()을 사용하면 동시 요청 간 통계가 뒤섞이므로
    # 항상 새 인스턴스를 생성한다. standalone CLI/TUI는 reset_stats=True
    # 로 호출하던 것을 그대로 유지하되 전역 싱글톤은 건드리지 않는다.
    tracker = CostTracker()
    stats = SessionStats()
    if reset_stats:
        # standalone 모드: 전역 싱글톤도 동기화 (CLI /cost, /stats 명령용)
        CostTracker._instance = tracker
        SessionStats._instance = stats

    scoped_memory = ScopedMemory(cwd=resolved_cwd)
    scoped_memory.ensure_gitignore()
    memory_context = scoped_memory.read_context()

    model_name = os.getenv("THESEUS_MODEL") or "gpt-4o"
    if api_client is None:
        api_client = TheseusLLMClient(model_name)

    # Theseus 자체 ToolRegistry로 시작 — create_default_tool_registry() 사용하지 않음
    full_registry = ToolRegistry()

    # ALL_CORE_TOOLS에서 모든 핵심 도구를 자동 등록
    for tool_cls in ALL_CORE_TOOLS:
        full_registry.register(tool_cls())

    # ── 커스텀 툴 로딩: project_id 유무에 따라 경로 분기 ──────
    if project_id:
        loaded_tools = load_custom_tools_for_project(
            full_registry, project_id, project_tool_permissions,
        )
    else:
        loaded_tools = load_custom_tools(
            full_registry,
            project_tool_permissions,
            extra_dirs=_workspace_custom_tool_dirs(resolved_cwd),
        )
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
                print(f"✅ RAG 도구 선택 성공 ({similarity_added}개 유사도 매칭)")
        except Exception as _e:
            import logging as _logging
            _logging.getLogger(__name__).warning(
                "[ToolRetriever] 도구 검색 실패, 전체 레지스트리 사용: %s", _e,
            )
            print("⚠️ 도구 검색 중 오류 발생. 전체 레지스트리를 사용합니다.")
            rag_failed = True
    # --------------------------------------------------------------

    # Theseus 자체 PermissionSettings 사용
    from theseus_engine.models.rbac import TheseusPermissionSettings
    settings = TheseusPermissionSettings()
    permission_checker = TheseusPermissionChecker(
        settings, user_level, project_tool_permissions,
        require_human_confirm=False,
    )

    enable_hooks = os.getenv("THESEUS_ENABLE_AGENT_HOOK", "false").lower() == "true"
    hook_executor = None

    can_create_tool = can_create_tool_for_state(
        mode=sm.mode,
        plan_phase=getattr(sm, "plan_phase", None),
        project_id=project_id,
        actor_role=actor_role,
    )
    if can_create_tool and current_registry.get("create_tool") is None:
        creator = full_registry.get("create_tool")
        if creator is not None:
            current_registry.register(creator)

    active_registry = build_visible_registry(
        current_registry,
        ToolVisibilityPolicy(
            mode=sm.mode,
            plan_phase=getattr(sm, "plan_phase", None),
            user_level=user_level,
            tool_permissions=project_tool_permissions,
            can_create_tool=can_create_tool,
            disabled_tools=frozenset(project_disabled_tools or set()),
        ),
    )

    if rag_failed and active_registry.get("tool_search") is None:
        active_registry.register(ToolSearchTool())
        print("🔧 ToolSearchTool이 폴백으로 활성화되었습니다.")

    active_tool_names_tuple = active_tool_names(active_registry)
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
        cwd=resolved_cwd,
        model=model_name,
        system_prompt=(
            sm.get_system_prompt(available_tools=active_tool_names_tuple)
            + ("\n\n" + memory_context if memory_context else "")
        ),
        max_turns=30,
        permission_prompt=permission_prompt_func if callable(permission_prompt_func) else None,
        skill_injection_config=SkillInjectionConfig(
            enabled=_resolve_skill_injection_enabled(enable_skill_injection),
        ),
        tool_metadata={
            "tool_registry": full_registry,
            "tool_permissions": project_tool_permissions,
            "active_registry": active_registry,
            "llm_client": api_client,
            "model_name": model_name,
            "tool_repair_policy": ToolRepairPolicy.from_env(),
            "cost_tracker": tracker,
            "session_stats": stats,
            "scoped_memory": scoped_memory,
            "user_rbac_level": user_level,
            "agent_mode": sm.mode.value if hasattr(sm, "mode") else "normal",
            "project_id": project_id,
            "actor_role": actor_role,
            "active_skills": [],
            # Kafka 실행 추적 ID — ToolExecutionContext.run_id/tool_draft_id로 전달됨
            "run_id": run_id,
            "tool_draft_id": tool_draft_id,
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
