import os
import sys
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
from theseus_engine.models.state import TheseusStateMachine, AgentMode
from theseus_engine.models.sessions import load_session_history, save_session_history
from theseus_engine.wrappers.llm_clients.theseus_client import TheseusLLMClient
from theseus_engine.tools.core.tool_factory import ToolValidator, CUSTOM_TOOLS_DIR
from theseus_engine.rag.service import get_rag_service

# --- Gemini thought_signature Monkey-Patch ---
from theseus_engine.wrappers.llm_clients.gemini_patch import apply_gemini_patch
apply_gemini_patch()

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

    print("\n- /plan, /agent, /ask: 모드 변경")
    print("- /tools: 사용 가능한 도구 목록 확인")
    print("- /rbac <level>: 사용자 권한 레벨 변경")
    print("- /validate <tool_name>: 생성된 도구 보안/규격 검증")
    print("- /kb <query>: 지식 베이스(RAG) 직접 검색")
    print("- /clear: 세션 초기화")
    print("- 'exit' 또는 'quit': 종료\n")

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
                elif cmd in ("/approve", "/reject"):
                    print(f"[*] Workflow command '{cmd}' received. (Async approval server not connected)")
                    continue

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
            async for event in engine.submit_message(line):
                if isinstance(event, AssistantTextDelta):
                    print(event.text, end="", flush=True)
                elif isinstance(event, ToolExecutionStarted):
                    print(f"\n[*] Executing tool: {event.tool_name}...", flush=True)
                    record_tool_call(line, event.tool_name)
                elif isinstance(event, ToolExecutionCompleted):
                    print(f"[*] Tool '{event.tool_name}' result received.", flush=True)
                elif isinstance(event, AssistantTurnComplete):
                    print("\n", flush=True)
                elif isinstance(event, ErrorEvent):
                    print(f"\n[API ERROR] {event.message}", flush=True)
                else:
                    print(f"\n[EVENT] {type(event).__name__}: {event}", flush=True)
            
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
