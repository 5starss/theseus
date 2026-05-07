import os
import sys
import json
import re
import asyncio
from pathlib import Path

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

# HuggingFace 비인증 경고 및 symlinks 경고 억제
os.environ.setdefault("HF_HUB_DISABLE_SYMLINKS_WARNING", "1")
os.environ.setdefault("TOKENIZERS_PARALLELISM", "false")

# 프로젝트 루트 및 OpenHarness 경로 추가
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))
sys.path.insert(0, str(PROJECT_ROOT / "OpenHarness" / "src"))

from openharness.engine.stream_events import (
    AssistantTextDelta, AssistantTurnComplete, ToolExecutionStarted, ToolExecutionCompleted, ErrorEvent
)
from theseus_engine.core.engine_builder import setup_engine
from theseus_engine.core.tool_usage_logger import record_tool_call
from theseus_engine.core.context_compressor import maybe_compress
from theseus_engine.models.state import TheseusStateMachine, AgentMode, CoordinatorPhase, PlanPhase
from theseus_engine.engine.cost_tracker import CostTracker
from theseus_engine.observability.stats import SessionStats
from theseus_engine.models.sessions import load_session_history, save_session_history
from theseus_engine.wrappers.llm_clients.theseus_client import TheseusLLMClient
from theseus_engine.tools.core.tool_factory import ToolValidator, CUSTOM_TOOLS_DIR
from theseus_engine.rag.service import get_rag_service

# --- Gemini thought_signature Monkey-Patch ---
from theseus_engine.wrappers.llm_clients.gemini_patch import apply_gemini_patch
apply_gemini_patch()

def _print_help() -> None:
    print("\n" + "-" * 50)
    print(" Theseus CLI - 사용 가능한 명령어")
    print("-" * 50)
    print("  [모드 전환]")
    print("    /agent            자율 실행 모드 (기본)")
    print("    /ask              질문/답변 전용 (도구 사용 안 함)")
    print("    /plan             계획 -> 리뷰 -> 실행 파이프라인")
    print("    /coordinator      병렬 서브 에이전트 오케스트레이션")
    print()
    print("  [도구 및 권한]")
    print("    /tools            현재 사용 가능한 도구 목록")
    print("    /rbac <level>     RBAC 권한 레벨 변경 (1~5)")
    print("    /validate <name>  커스텀 도구 보안/규격 검증")
    print()
    print("  [지식 베이스]")
    print("    /kb <query>       지식 베이스(RAG) 직접 검색")
    print()
    print("  [세션 관리]")
    print("    /cost             세션 토큰 사용량 및 USD 비용 보고서")
    print("    /stats            툴 실행 시간 및 성능 통계")
    print("    /clear            세션 대화 기록 초기화")
    print()
    print("  [계획 모드 전용]")
    print("    approve           계획 승인 및 실행 시작 (PLAN 모드에서)")
    print("    /approve          계획 승인 및 실행 시작 (슬래시 버전)")
    print("    /reject           계획 거부 및 Agent 모드 복귀")
    print()
    print("  [기타]")
    print("    /help             이 도움말 다시 보기")
    print("    exit / quit       프로그램 종료")
    print("-" * 50 + "\n")


def _extract_plan_json(response_text: str) -> dict | None:
    """LLM 응답에서 JSON 계획 블록을 추출합니다."""
    match = re.search(r'```json\s*(\{.*?\})\s*```', response_text, re.DOTALL)
    if match:
        try:
            return json.loads(match.group(1))
        except json.JSONDecodeError:
            pass
    return None


def _display_plan(plan_data: dict) -> None:
    """JSON 계획을 계층적으로 콘솔에 출력합니다."""
    print("\n" + "=" * 60)
    print(f"[Plan] {plan_data.get('goal', '(목표 없음)')}")
    print("=" * 60)
    tasks = plan_data.get("tasks", [])
    main_tasks = [t for t in tasks if not t.get("parent_id")]
    for mt in main_tasks:
        status_mark = _status_mark(mt.get("status", "pending"))
        print(f"\n  {status_mark} [{mt['id']}] {mt['title']}")
        if mt.get("description") and mt["description"] != mt["title"]:
            print(f"        {mt['description']}")
        sub_tasks = [t for t in tasks if t.get("parent_id") == mt["id"]]
        for st in sub_tasks:
            st_mark = _status_mark(st.get("status", "pending"))
            print(f"    {st_mark} [{st['id']}] {st['title']}")
    print("\n" + "-" * 60)
    print("[*] 'approve' 또는 '/approve'         : 계획 승인 및 실행")
    print("[*] '<task-id>: <피드백>'              : 특정 태스크 수정 요청")
    print("[*] 일반 텍스트 입력                   : 전체 계획 수정 요청")
    print("-" * 60 + "\n")


def _status_mark(status: str) -> str:
    return {"pending": "[ ]", "done": "[v]", "running": "[~]", "failed": "[x]"}.get(status, "[ ]")


def _parse_task_feedback(line: str, plan_json_str: str) -> tuple[str, str] | None:
    """'<task-id>: <피드백>' 패턴을 파싱합니다.

    Returns (task_id, feedback) if matched, else None.
    """
    if not plan_json_str:
        return None
    try:
        plan_data = json.loads(plan_json_str)
    except json.JSONDecodeError:
        return None

    task_ids = {t["id"] for t in plan_data.get("tasks", [])}

    # "<task-id>: <feedback>" 또는 "<task-id> <feedback>" 형태 모두 지원
    m = re.match(r'^([a-zA-Z0-9_-]+)\s*:\s*(.+)$', line.strip(), re.DOTALL)
    if m and m.group(1) in task_ids:
        return m.group(1), m.group(2).strip()

    return None


def _build_task_feedback_prompt(task_id: str, feedback: str, plan_json_str: str) -> str:
    """태스크 ID 기반 피드백을 LLM에 보낼 프롬프트로 변환합니다."""
    return (
        f"아래 계획에서 태스크 ID '{task_id}'에 대한 수정 요청입니다:\n\n"
        f"피드백: {feedback}\n\n"
        f"현재 계획:\n```json\n{plan_json_str}\n```\n\n"
        f"위 피드백을 반영하여 해당 태스크(및 필요한 경우 관련 서브태스크)만 수정한 뒤, "
        f"전체 계획을 동일한 JSON 형식으로 다시 출력해 주세요."
    )


def _handle_plan_draft(sm: "TheseusStateMachine", response_text: str) -> None:
    """LLM 응답에서 JSON 계획을 추출하고 상태를 WAIT_FOR_REVIEW로 전환합니다."""
    plan_data = _extract_plan_json(response_text)
    if plan_data:
        sm.plan = json.dumps(plan_data, ensure_ascii=False, indent=2)
        # temp 디렉토리에 저장
        try:
            Path("temp").mkdir(exist_ok=True)
            with open("temp/plan_refactored.json", "w", encoding="utf-8") as f:
                json.dump(plan_data, f, ensure_ascii=False, indent=2)
        except Exception:
            pass
        _display_plan(plan_data)
    else:
        # JSON을 찾지 못하면 원문 텍스트를 plan으로 저장
        sm.plan = response_text
        print("\n[!] 계획 JSON 파싱 실패. 원문을 계획으로 저장합니다.")
        print("[*] 'approve' 또는 '/approve'로 실행하거나 피드백을 입력하세요.\n")
    sm.set_plan_phase(PlanPhase.WAIT_FOR_REVIEW)


async def run_cli():
    print("\n" + "="*50)
    print(" 🧩 Theseus Core CLI Agent (Gemini 3.1 Ready)")
    print("="*50)
    
    # 설정 초기화
    sm = TheseusStateMachine(initial_mode=AgentMode.AGENT)
    user_level = 5
    project_tool_permissions = {
        "bash": 3, "read_file": 1, "write_file": 2, "edit_file": 2, 
        "glob": 1, "grep": 1, "web_search": 1, "web_fetch": 1,
        "dummy_echo": 1, "create_tool": 2, "system_reboot": 5,
        "search_knowledge_base": 1, "ingest_document": 2,
    }
    
    # 명시적으로 모델 설정
    model_name = os.getenv("OPENHARNESS_MODEL", "google/gemini-3.1-pro-preview-customtools")
    os.environ["OPENHARNESS_MODEL"] = model_name
    
    # 도구 승인 콜백 (Human-in-the-loop)
    async def ask_permission(tool_name: str, args_str: str) -> bool:
        print(f"\n[⚠️  PERMISSION] Allow tool '{tool_name}' with args: {args_str}?")
        choice = input("Allow this action? (y/N): ").strip().lower()
        return choice == 'y'

    # 엔진 생성 (TheseusLLMClient 사용)
    client = TheseusLLMClient(model_name)
    engine, _ = setup_engine(
        sm, user_level, project_tool_permissions, ask_permission,
        api_client=client
    )
    
    # 이전 세션 로드
    history = load_session_history("default")
    if history:
        engine.load_messages(history)
        print(f"[*] Loaded {len(history)} messages from previous session.")

    _print_help()

    while True:
        try:
            line = input("user> ").strip()
            if not line: continue
            
            if line.lower() in ('exit', 'quit'):
                break
                
            # 1. Theseus 전용 슬래시 명령어 처리 (Intercept)
            if line.startswith("/"):
                parts = line.split()
                cmd = parts[0].lower()
                args = parts[1:] if len(parts) > 1 else []

                if cmd == "/clear":
                    engine.clear()
                    print("[*] Session cleared.")
                    continue
                elif cmd == "/plan":
                    sm.switch_mode(AgentMode.PLAN)
                    engine.set_system_prompt(sm.get_system_prompt())
                    print("[*] Switched to PLAN mode.")
                    continue
                elif cmd == "/agent":
                    sm.switch_mode(AgentMode.AGENT)
                    engine.set_system_prompt(sm.get_system_prompt())
                    print("[*] Switched to AGENT mode.")
                    continue
                elif cmd == "/ask":
                    sm.switch_mode(AgentMode.ASK)
                    engine.set_system_prompt(sm.get_system_prompt())
                    print("[*] Switched to ASK mode. (Tools disabled)")
                    continue
                elif cmd == "/rbac":
                    if not args:
                        print(f"[*] Current user_level: {user_level}")
                    else:
                        try:
                            user_level = int(args[0])
                            print(f"[*] User level changed to: {user_level}")
                        except ValueError:
                            print("[!] User level must be an integer.")
                    continue
                elif cmd == "/tools":
                    print("\n[🛠️  Available Tools]")
                    _, current_registry = setup_engine(sm, user_level, project_tool_permissions, ask_permission)
                    for tool in current_registry.list_tools():
                        perm = project_tool_permissions.get(tool.name, 1)
                        print(f"- {tool.name:<20} [Lv.{perm}]")
                    print("")
                    continue
                elif cmd == "/validate":
                    if not args:
                        print("[!] Usage: /validate <tool_name>")
                        continue
                    tool_name = args[0]
                    file_path = os.path.join(CUSTOM_TOOLS_DIR, f"{tool_name}.py")
                    if not os.path.exists(file_path):
                        print(f"[!] Tool file not found: {file_path}")
                        continue
                    
                    print(f"[*] Validating tool: {tool_name}...")
                    with open(file_path, "r", encoding="utf-8") as f:
                        code = f.read()
                    
                    # 1단계: 정적 분석 및 보안 검증
                    ok, msg = ToolValidator.validate_code(code)
                    print(f"--- Analysis Result ---\n{msg}")
                    
                    # 2단계: 모듈 로드 및 구조 검증
                    if ok:
                        ok2, msg2, _ = ToolValidator.validate_and_load_module(tool_name, file_path)
                        print(f"--- Runtime Spec Result ---\n{msg2}")
                    continue
                elif cmd == "/kb":
                    if not args:
                        print("[!] Usage: /kb <query>")
                        continue
                    query = " ".join(args)
                    print(f"[*] Searching Knowledge Base for: '{query}'...")
                    try:
                        results = get_rag_service().search(query, top_k=3)
                        if not results:
                            print("[*] No matching results found.")
                        for i, res in enumerate(results):
                            print(f"\n[{i+1}] Score: {res.get('score', 0):.4f}")
                            print(f"Content: {res.get('content', '')[:200]}...")
                    except Exception as e:
                        print(f"[!] KB Search failed: {e}")
                    continue
                elif cmd == "/coordinator":
                    sm.switch_mode(AgentMode.COORDINATOR)
                    engine.set_system_prompt(sm.get_system_prompt())
                    print("[*] Switched to COORDINATOR mode. (Decompose -> Dispatch -> Synthesize -> Verify)")
                    continue
                elif cmd == "/cost":
                    tracker = CostTracker.get_or_create()
                    report = "\n" + tracker.format_report()
                    try:
                        print(report)
                    except UnicodeEncodeError:
                        print(report.encode(sys.stdout.encoding, errors="replace").decode(sys.stdout.encoding))
                    continue
                elif cmd == "/stats":
                    stats_inst = SessionStats.get()
                    report = "\n" + stats_inst.format_report()
                    try:
                        print(report)
                    except UnicodeEncodeError:
                        print(report.encode(sys.stdout.encoding, errors="replace").decode(sys.stdout.encoding))
                    continue
                elif cmd == "/help":
                    _print_help()
                    continue
                elif cmd == "/approve":
                    if sm.mode == AgentMode.PLAN and sm.plan_phase == PlanPhase.WAIT_FOR_REVIEW:
                        sm.set_plan_phase(PlanPhase.EXECUTING)
                        engine.set_system_prompt(sm.get_system_prompt())
                        print("[*] 계획이 승인되었습니다. 실행 단계를 시작합니다.")
                        # 승인 메시지를 LLM에 전달하여 실행 시작
                        line = "승인된 계획을 단계별로 실행해 주세요."
                        # 슬래시 처리 이후의 일반 메시지 흐름으로 넘어감
                    else:
                        print("[*] 현재 검토 중인 계획이 없습니다. /plan 모드에서 계획을 먼저 작성하세요.")
                        continue
                elif cmd == "/reject":
                    if sm.mode == AgentMode.PLAN:
                        sm.switch_mode(AgentMode.AGENT)
                        engine.set_system_prompt(sm.get_system_prompt())
                        print("[*] 계획이 거부되었습니다. Agent 모드로 전환합니다.")
                    continue

            # Plan WAIT_FOR_REVIEW: 입력 가로채기
            if sm.mode == AgentMode.PLAN and sm.plan_phase == PlanPhase.WAIT_FOR_REVIEW:
                if line.strip().lower() in ("approve", "승인"):
                    # 계획 승인 → EXECUTING 단계로 전환
                    sm.set_plan_phase(PlanPhase.EXECUTING)
                    engine.set_system_prompt(sm.get_system_prompt())
                    print("[*] 계획이 승인되었습니다. 실행 단계를 시작합니다.")
                    line = "승인된 계획을 단계별로 실행해 주세요."
                else:
                    # 태스크 ID 기반 피드백 감지: "task-1-1: 수정 내용"
                    task_feedback = _parse_task_feedback(line, sm.plan)
                    if task_feedback:
                        task_id, feedback = task_feedback
                        print(f"[*] 태스크 [{task_id}] 피드백 반영 중...")
                        line = _build_task_feedback_prompt(task_id, feedback, sm.plan)
                    # 일반 텍스트: 전체 계획 수정 요청 (그대로 LLM에 전달)

            # 2. 메시지 전송 및 스트리밍 출력
            current_messages = list(engine.messages)

            # 메시지 누적 시 자동 압축 (30개 초과 → 최근 10개 보존)
            current_messages, did_compress = await maybe_compress(current_messages)
            if did_compress:
                print(f"[*] 컨텍스트 압축 완료: {len(current_messages)}개 메시지로 축약")

            # [Dynamic Tool Selection] 매 메시지마다 최적화된 도구 셋으로 엔진 재구성
            engine, _ = setup_engine(
                sm,
                user_level,
                project_tool_permissions,
                ask_permission,
                api_client=client,
                user_query=line,
                top_k=8,
                history_messages=current_messages,
            )
            engine.load_messages(current_messages)

            print("assistant> ", end="", flush=True)
            accumulated_text = ""
            tool_called_this_turn = False
            plan_complete = False

            async for event in engine.submit_message(line):
                if isinstance(event, AssistantTextDelta):
                    accumulated_text += event.text
                    print(event.text, end="", flush=True)
                elif isinstance(event, ToolExecutionStarted):
                    tool_called_this_turn = True
                    print(f"\n[*] Executing tool: {event.tool_name}...", flush=True)
                    record_tool_call(line, event.tool_name)
                elif isinstance(event, ToolExecutionCompleted):
                    print(f"[*] Tool '{event.tool_name}' result received.", flush=True)
                elif isinstance(event, AssistantTurnComplete):
                    print("\n", flush=True)
                    if sm.mode == AgentMode.PLAN:
                        if sm.plan_phase == PlanPhase.DRAFTING:
                            _handle_plan_draft(sm, accumulated_text)
                            engine.set_system_prompt(sm.get_system_prompt())
                        elif sm.plan_phase == PlanPhase.WAIT_FOR_REVIEW:
                            updated = _extract_plan_json(accumulated_text)
                            if updated:
                                sm.plan = json.dumps(updated, ensure_ascii=False, indent=2)
                                try:
                                    Path("temp").mkdir(exist_ok=True)
                                    with open("temp/plan_refactored.json", "w", encoding="utf-8") as f:
                                        json.dump(updated, f, ensure_ascii=False, indent=2)
                                except Exception:
                                    pass
                                _display_plan(updated)
                                print("[*] 계획이 업데이트되었습니다.")
                        elif sm.plan_phase == PlanPhase.EXECUTING:
                            # 완료 키워드 감지
                            lower = accumulated_text.lower()
                            if any(kw in lower for kw in ("plan complete", "계획 실행 완료", "모든 계획 완료", "all steps complete")):
                                plan_complete = True
                elif isinstance(event, ErrorEvent):
                    print(f"\n[API ERROR] {event.message}", flush=True)
                else:
                    print(f"\n[EVENT] {type(event).__name__}: {event}", flush=True)

            # PLAN EXECUTING: 도구 호출 없이 턴이 끝나면 자동으로 다음 단계 트리거
            if (
                sm.mode == AgentMode.PLAN
                and sm.plan_phase == PlanPhase.EXECUTING
                and not tool_called_this_turn
                and not plan_complete
            ):
                print("[auto] 다음 단계를 계속 실행합니다...\n")
                line = "계속 진행해줘. 다음 단계를 즉시 실행해."
                # 현재 메시지 저장 후 루프 재진입 (continue로 while 처음으로)
                save_session_history("default", engine.messages)
                continue

            # 세션 자동 저장
            save_session_history("default", engine.messages)
            
        except KeyboardInterrupt:
            break
        except Exception as e:
            print(f"\n[ERROR] {e}")

    print("\n[*] Saving session and exiting...")
    save_session_history("default", engine.messages)
    print("Done. Goodbye!")

if __name__ == "__main__":
    asyncio.run(run_cli())
