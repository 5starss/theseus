"""[Phase 2 & 3] RBAC, 3-Mode 상태 머신 및 커스텀 툴 통합 테스트.

상용 AI 코딩 어시스턴트(Cursor Agent / Copilot) 스타일의
3-Mode 아키텍처 + Pydantic 구조화 출력 전략 적용.

사용 가능한 명령어:
  /ask       — Ask 모드로 전환 (질문/답변 전용, 도구 사용 안 함)
  /agent     — Agent 모드로 전환 (자율 실행, 도구 자유 사용)
  /plan      — Plan 모드로 전환 (구조화된 계획 → 블록 리뷰 → 실행)
  /mode      — 현재 모드 및 사용 가능한 모드 목록 표시
  approve    — Plan 리뷰에서 승인 후 실행
  edit N ... — Plan 리뷰에서 특정 블록 수정
  reset      — 현재 모드 유지하며 대화 초기화
  exit/quit  — 종료
"""

import asyncio
import os
import sys

# Windows에서 이모지 출력 시 발생하는 cp949 인코딩 에러 방지
if sys.stdout.encoding.lower() != 'utf-8':
    sys.stdout.reconfigure(encoding='utf-8')

from pathlib import Path

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

from openharness.engine.query_engine import QueryEngine
from openharness.api.openai_client import OpenAICompatibleClient
from openharness.tools.base import ToolRegistry
from openharness.tools import create_default_tool_registry
from openharness.config import load_settings
from openharness.engine.stream_events import (
    AssistantTextDelta,
    ToolExecutionStarted,
    ToolExecutionCompleted,
    ErrorEvent
)

from theseus_engine.monkey_patches import apply_patches
# OpenHarness 소스를 직접 수정하지 않고 런타임 패치 적용
apply_patches()

# Custom Modules
from theseus_engine.rbac import TheseusPermissionChecker
from theseus_engine.state import (
    TheseusStateMachine,
    AgentMode,
    PlanPhase,
    MODE_DESCRIPTIONS,
)
from theseus_engine.tools import DummyTool, SystemRebootTool
from theseus_engine.tool_factory import (
    ToolCreatorTool,
    load_custom_tools,
    build_filtered_registry,
)
from theseus_engine.schemas import PlanBlock
from theseus_engine.structured_planner import StructuredPlanner


# -------------------------------------------------------------------
# UI Helper Functions
# -------------------------------------------------------------------


def _print_mode_help(sm: TheseusStateMachine) -> None:
    """현재 모드와 사용 가능한 명령어를 출력합니다."""
    print("\n" + "=" * 56)
    print(f"  현재 모드: {sm.display_mode}")
    print("=" * 56)
    for mode, desc in MODE_DESCRIPTIONS.items():
        marker = " ◀" if mode == sm.mode else ""
        print(f"  {desc}{marker}")
    print("-" * 56)
    print("  /ask       질문/답변 모드로 전환")
    print("  /agent     자율 실행 모드로 전환")
    print("  /plan      계획 수립 모드로 전환")
    print("  /mode      이 도움말 표시")
    print("  reset      대화 초기화")
    print("  exit       종료")
    print("=" * 56)


def _print_plan_blocks(blocks: list[PlanBlock]) -> None:
    """구조화된 플랜 블록을 리뷰 UI 형태로 출력합니다."""
    print("\n" + "=" * 64)
    print("  📋 Structured Plan (Pydantic Structured Output)")
    print("=" * 64)

    for i, block in enumerate(blocks):
        border = "-" * 58
        print(f"\n  [{i+1:02d}] {block.title}")
        print(f"       ID: {block.block_id}")
        print(f"       {border}")

        # Primary content (summary line)
        if block.content:
            for line in block.content.split("\n"):
                print(f"       {line}")

        # Sub-items with individual IDs
        if block.sub_items:
            if block.content:
                print()  # separator between content and items
            for item in block.sub_items:
                print(
                    f"         {item.index}. {item.content}"
                )
                print(
                    f"            [{item.item_id}]"
                )

    print("\n" + "=" * 64)
    print("[System] Structured plan generated.")
    print(" - Approve and execute: 'approve'")
    print(" - Edit a block:     'edit <N> <new content>'")
    print(" - Edit a sub-item:  'edit <N>.<M> <new content>'")
    print(" - Cancel plan: type anything else -> returns to Agent mode")


# -------------------------------------------------------------------
# Main
# -------------------------------------------------------------------


async def main():
    """메인 에이전트 루프."""
    print(
        "🚀 [Phase 2 & 3] RBAC, 3-Mode 상태 머신 "
        "+ Structured Output 테스트 시작\n"
    )

    # ----- 1. 환경 설정 및 클라이언트 준비 -----
    api_key = os.getenv("OPENAI_API_KEY") or os.getenv("GEMINI_API_KEY")
    base_url = os.getenv("OPENAI_BASE_URL")
    model_name = os.getenv("OPENHARNESS_MODEL", "gpt-4o")
    if not base_url and "gemini" in model_name.lower():
        base_url = (
            "https://generativelanguage.googleapis.com/v1beta/openai/"
        )

    api_client = OpenAICompatibleClient(
        api_key=api_key, base_url=base_url
    )
    settings = load_settings()

    # ----- 2. 프로젝트별 툴 권한 설정 (RBAC) -----
    project_tool_permissions = {
        # OpenHarness 빌트인 도구 권한
        "bash": 3,           # 셸 실행 — 관리자만
        "read_file": 1,      # 파일 읽기 — 모두
        "write_file": 2,     # 파일 쓰기 — 중급
        "edit_file": 2,      # 파일 편집 — 중급
        "glob": 1,           # 파일 검색 — 모두
        "grep": 1,           # 텍스트 검색 — 모두
        "web_search": 1,     # 웹 검색 — 모두
        "web_fetch": 1,      # URL 페치 — 모두
        # Theseus 전용 도구 권한
        "dummy_echo": 1,
        "create_tool": 2,    # 도구 생성 — 중급 (Plan 모드 전용)
        "system_reboot": 5,  # 시스템 — 최고 관리자
    }
    user_level = 5  # 테스트용 (빌트인 도구 대부분 사용 가능)

    # ----- 3. Full Tool Registry -----
    # OpenHarness 빌트인 42개 도구 포함 레지스트리
    full_registry = create_default_tool_registry()

    # Theseus 전용 도구 추가 등록
    full_registry.register(DummyTool())
    full_registry.register(SystemRebootTool())
    full_registry.register(ToolCreatorTool())

    loaded_tools = load_custom_tools(
        full_registry, project_tool_permissions
    )
    if loaded_tools:
        print(f"📦 자동 로드된 커스텀 툴: {', '.join(loaded_tools)}")
    else:
        print("📦 로드할 커스텀 툴이 없습니다.")

    # ----- 4. Filtered Tool Registry (초기) -----
    filtered_registry = build_filtered_registry(
        full_registry, project_tool_permissions, user_level
    )
    visible_tools = [t.name for t in filtered_registry.list_tools()]
    hidden_tools = [
        t.name for t in full_registry.list_tools()
        if t.name not in visible_tools
    ]
    print(f"✅ 사용자 권한 레벨: {user_level}")
    print(f"   👁️ LLM에 노출되는 툴: {visible_tools}")
    if hidden_tools:
        print(f"   🚫 권한 부족으로 숨겨진 툴: {hidden_tools}")

    # ----- 5. RBAC Permission Checker -----
    permission_checker = TheseusPermissionChecker(
        settings=settings.permission,
        user_level=user_level,
        tool_permissions=project_tool_permissions,
    )

    # ----- 6. State Machine 초기화 -----
    sm = TheseusStateMachine(initial_mode=AgentMode.AGENT)

    # ----- 7. Engine 인스턴스 (루프 외부에서 1회 생성) -----
    engine = QueryEngine(
        api_client=api_client,
        tool_registry=filtered_registry,
        permission_checker=permission_checker,
        cwd=Path.cwd(),
        model=model_name,
        system_prompt=sm.get_system_prompt(),
        max_turns=99,
        tool_metadata={
            "tool_registry": full_registry,
            "tool_permissions": project_tool_permissions,
        },
    )

    # ----- 8. Structured Planner 초기화 -----
    planner = StructuredPlanner(
        api_key=api_key,
        base_url=base_url,
        model=model_name,
    )

    # 시작 시 모드 안내
    _print_mode_help(sm)

    # ===== Main Loop =====
    while True:
        # 매 턴: 시스템 프롬프트 & 툴 레지스트리 갱신
        engine.set_system_prompt(sm.get_system_prompt())

        # 모드별 동적 도구 필터링
        exclude = set()
        is_plan_executing = (
            sm.mode == AgentMode.PLAN
            and sm.plan_phase == PlanPhase.EXECUTING
        )
        if not is_plan_executing:
            # Plan Executing 모드가 아니면 create_tool 숨김
            exclude.add("create_tool")

        filtered_registry = build_filtered_registry(
            full_registry, project_tool_permissions, user_level,
            exclude_tools=exclude,
        )
        engine._tool_registry = filtered_registry

        # 프롬프트에 현재 모드 표시
        prompt_label = f"[{sm.display_mode}] > "
        user_input = input(f"\n{prompt_label}")

        # ----- 시스템 명령어 처리 -----
        cmd = user_input.strip().lower()

        if cmd in ("exit", "quit"):
            print("👋 세션을 종료합니다.")
            break

        if cmd == "/mode":
            _print_mode_help(sm)
            continue

        if cmd in ("/ask", "/agent", "/plan"):
            mode_map = {
                "/ask": AgentMode.ASK,
                "/agent": AgentMode.AGENT,
                "/plan": AgentMode.PLAN,
            }
            sm.switch_mode(mode_map[cmd])
            if cmd == "/plan":
                print("[System] 계획할 작업을 입력해주세요.")
            continue

        if cmd.startswith("/plan "):
            sm.switch_mode(AgentMode.PLAN)
            user_input = user_input[6:].strip()
            print(f"[System] Plan 모드 진입. 목표: {user_input}")
            # fall through — Drafting 분기로 진입

        if cmd == "reset":
            sm.switch_mode(sm.mode)
            engine.clear()
            print("[System] 대화가 초기화되었습니다.")
            continue

        # --------------------------------------------------------
        # Plan / Drafting: Pydantic 구조화 출력으로 플랜 생성
        # --------------------------------------------------------
        if sm.is_plan_drafting:
            print(
                "\n⏳ [System] 구조화된 플랜을 생성하고 있습니다...",
                flush=True,
            )
            try:
                plan_doc = planner.generate_plan(user_input)
                sm.plan = StructuredPlanner.to_markdown(plan_doc)
                sm.plan_blocks = StructuredPlanner.to_blocks(plan_doc)
                sm.plan_document = plan_doc

                # temp 폴더에 마크다운과 JSON 저장
                temp_dir = Path("temp")
                temp_dir.mkdir(exist_ok=True)
                with open(temp_dir / "plan.md", "w", encoding="utf-8") as f:
                    f.write(sm.plan)
                with open(temp_dir / "plan.json", "w", encoding="utf-8") as f:
                    f.write(plan_doc.model_dump_json(indent=2))
                
                print(f"[System] 플랜이 temp/plan.md 및 temp/plan.json 에 저장되었습니다.")

                # Security Policy Violation 체크
                is_violation = any(
                    "Security Policy Violation" in step.title 
                    for step in plan_doc.steps
                )

                if is_violation:
                    _print_plan_blocks(sm.plan_blocks)
                    print("\n" + "!" * 64)
                    print("⚠️ [System] 요청이 보안 정책에 의해 거부되었습니다.")
                    print("! [System] Agent 모드로 즉시 복귀합니다.")
                    print("!" * 64)
                    sm.switch_mode(AgentMode.AGENT)
                else:
                    sm.set_plan_phase(PlanPhase.WAIT_FOR_REVIEW)
                    _print_plan_blocks(sm.plan_blocks)

            except ValueError as e:
                print(f"\n❌ 플랜 생성 실패: {e}")
                print(
                    "[System] Agent 모드로 복귀합니다. "
                    "다시 시도해주세요."
                )
                sm.switch_mode(AgentMode.AGENT)
            continue

        # --------------------------------------------------------
        # Plan / Review: 블록 단위 승인·수정·취소
        # --------------------------------------------------------
        if sm.is_plan_reviewing:
            if cmd == "approve":
                sm.set_plan_phase(PlanPhase.EXECUTING)
                user_input = (
                    "Plan approved. Please proceed with execution "
                    "based on the following plan:\n"
                    f"{sm.plan}"
                )
                # fall through → LLM 호출
            elif cmd.startswith("edit "):
                parts = user_input.split(" ", 2)
                if (
                    len(parts) >= 3
                    and hasattr(sm, "plan_blocks")
                ):
                    target = parts[1]
                    new_content = parts[2]

                    # Sub-item edit: "edit 3.2 new content"
                    if "." in target:
                        try:
                            block_num, item_num = (
                                target.split(".", 1)
                            )
                            b_idx = int(block_num) - 1
                            s_idx = int(item_num) - 1
                            block = sm.plan_blocks[b_idx]
                            if 0 <= s_idx < len(block.sub_items):
                                old = block.sub_items[s_idx].content
                                block.sub_items[s_idx].content = (
                                    new_content
                                )
                                sm.plan = (
                                    _rebuild_markdown_from_blocks(
                                        sm.plan_blocks
                                    )
                                )
                                print(
                                    f"\n✅ [System] Block {block_num}"
                                    f", item {item_num} updated."
                                )
                                print(f"   Before: {old}")
                                print(
                                    f"   After:  {new_content}"
                                )
                                _print_plan_blocks(sm.plan_blocks)
                                continue
                        except (ValueError, IndexError):
                            pass

                    # Block-level edit: "edit 3 new content"
                    elif target.isdigit():
                        idx = int(target) - 1
                        if 0 <= idx < len(sm.plan_blocks):
                            sm.plan_blocks[idx].content = (
                                new_content
                            )
                            sm.plan = (
                                _rebuild_markdown_from_blocks(
                                    sm.plan_blocks
                                )
                            )
                            print(
                                "\n✅ [System] Block updated."
                            )
                            _print_plan_blocks(sm.plan_blocks)
                            continue

                print(
                    "[System] Invalid format. "
                    "Usage: edit <N> <content> or "
                    "edit <N>.<M> <content>"
                )
                continue
            else:
                print(
                    "[System] 플랜이 취소되었습니다. "
                    "Agent 모드로 복귀합니다."
                )
                sm.switch_mode(AgentMode.AGENT)
                continue

        # --------------------------------------------------------
        # LLM 스트리밍 호출 (Ask / Agent / Plan-Executing)
        # --------------------------------------------------------
        print("[Assistant]: ", end="", flush=True)
        response_accumulator = ""
        error_encountered = None

        try:
            async for event in engine.submit_message(user_input):
                if isinstance(event, AssistantTextDelta):
                    print(event.text, end="", flush=True)
                    response_accumulator += event.text
                elif isinstance(event, ToolExecutionStarted):
                    print(
                        f"\n  ⚙️ [Tool Started: {event.tool_name}]",
                        end="", flush=True,
                    )
                elif isinstance(event, ToolExecutionCompleted):
                    icon = "❌" if event.is_error else "✅"
                    print(
                        f"\n  {icon} [Tool Completed: "
                        f"{event.tool_name} / Result: {event.output}]",
                        end="\n", flush=True,
                    )
                elif isinstance(event, ErrorEvent):
                    print(
                        f"\n❌ [Error: {event.message}]",
                        end="", flush=True,
                    )
                    error_encountered = event.message
            print()  # 줄바꿈
            
            # API 단의 ErrorEvent 가 발생했을 경우 에이전트 스스로 복구 루프 시도
            if error_encountered:
                print("\n[System] 에이전트 실행 중 시스템 에러가 발생했습니다. 자동 복구를 시도합니다...")
                recovery_prompt = (
                    f"System Error Encountered: {error_encountered}\n"
                    "The last operation failed due to the error above. "
                    "Please analyze why it failed and suggest or attempt an alternative approach."
                )
                print("[Assistant (Auto-Recovery)]: ", end="", flush=True)
                try:
                    async for ev in engine.submit_message(recovery_prompt):
                        if isinstance(ev, AssistantTextDelta):
                            print(ev.text, end="", flush=True)
                    print()
                except Exception as ex_recovery:
                    print(f"\n❌ 자동 복구 실패: {ex_recovery}")
                    if sm.mode == AgentMode.PLAN:
                        sm.switch_mode(AgentMode.AGENT)

            # Plan Executing 완료 후: Agent 모드로 자동 복귀
            elif (
                sm.mode == AgentMode.PLAN
                and sm.plan_phase == PlanPhase.EXECUTING
                and response_accumulator.strip()
            ):
                print(
                    "\n✅ [System] 플랜 실행이 완료되었습니다. "
                    "Agent 모드로 복귀합니다."
                )
                sm.switch_mode(AgentMode.AGENT)

        except Exception as e:
            err_msg = str(e)
            print(f"\n❌ 실행 중 에러 발생: {err_msg}")
            
            if "Exceeded maximum turn limit" in err_msg:
                print(
                    "\n[System] 턴 제한 초과를 감지했습니다. "
                    "에이전트에게 상황 분석 및 복구 방안을 요청합니다..."
                )
                recovery_prompt = (
                    "System Error: Exceeded maximum turn limit. "
                    "You have taken too many steps without completing the task. "
                    "Please provide a concise summary of:\n"
                    "1. What exactly went wrong or caused the infinite loop?\n"
                    "2. What steps have been successfully completed so far?\n"
                    "3. How can we resolve this bottleneck moving forward?"
                )
                print("[Assistant (Recovery Report)]: \n", end="", flush=True)
                try:
                    async for event in engine.submit_message(recovery_prompt):
                        if isinstance(event, AssistantTextDelta):
                            print(event.text, end="", flush=True)
                    print()
                except Exception as ex_recovery:
                    print(f"\n❌ 복구 리포트 생성 중 추가 에러 발생: {ex_recovery}")
                
                # 에러 발생 시 플랜 모드였다면 안전을 위해 요약 후 Agent 모드로 복귀
                if sm.mode == AgentMode.PLAN:
                    print("\n[System] Plan 모드에서 안전하게 Agent 모드로 복귀합니다.")
                    sm.switch_mode(AgentMode.AGENT)


def _rebuild_markdown_from_blocks(
    blocks: list[PlanBlock],
) -> str:
    """블록 리스트에서 마크다운을 재구성합니다.

    edit 명령 후 수정된 블록 내용을 반영하여
    에이전트 프롬프트 주입용 마크다운을 재생성합니다.
    sub_items도 bullet point로 포함됩니다.
    동시에 temp/plan.md 에 최신 버전을 동기화합니다.
    """
    md = ""
    for block in blocks:
        md += f"## {block.title}\n\n"
        if block.content:
            md += f"{block.content}\n\n"
        if block.sub_items:
            for item in block.sub_items:
                md += f"- {item.content}\n"
            md += "\n"
    
    final_md = md.strip()
    
    # temp 파일 동기화
    try:
        temp_dir = Path("temp")
        temp_dir.mkdir(exist_ok=True)
        with open(temp_dir / "plan.md", "w", encoding="utf-8") as f:
            f.write(final_md)
    except Exception:
        pass
        
    return final_md


if __name__ == "__main__":
    from openharness.platforms import get_platform
    
    if get_platform() == "windows":
        # Windows 환경에서 bash tool(하위 프로세스)을 정상적으로 사용하기 위해
        # 반드시 ProactorEventLoopPolicy를 설정해야 합니다.
        asyncio.set_event_loop_policy(
            asyncio.WindowsProactorEventLoopPolicy()
        )
    asyncio.run(main())
