import os
import sys
import json
import asyncio
from pathlib import Path

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

os.environ.setdefault("HF_HUB_DISABLE_SYMLINKS_WARNING", "1")
os.environ.setdefault("TOKENIZERS_PARALLELISM", "false")

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))
sys.path.insert(0, str(PROJECT_ROOT / "OpenHarness" / "src"))

from openharness.engine.stream_events import (
    AssistantTextDelta, AssistantTurnComplete,
    ToolExecutionStarted, ToolExecutionCompleted, ErrorEvent,
)
from theseus_engine.core.engine_builder import setup_engine
from theseus_engine.core.tool_usage_logger import record_tool_call_async as record_tool_call
from theseus_engine.core.context_compressor import maybe_compress
from theseus_engine.models.state import TheseusStateMachine, AgentMode, PlanPhase
from theseus_engine.engine.cost_tracker import CostTracker
from theseus_engine.models.sessions import (
    save_session_history_async as save_session_history,
    load_session_history,
    save_plan_state,
    load_plan_state,
    clear_plan_state,
)
from theseus_engine.wrappers.llm_clients.theseus_client import TheseusLLMClient

from theseus_cli.context import CLIContext
from theseus_cli.ui import print_help, display_plan
from theseus_cli.parsers import extract_plan_json, parse_plan_feedback, build_feedback_prompt, handle_plan_draft
from theseus_cli.intent import llm_is_approval
from theseus_cli.commands import handle_slash_command


async def run_cli():
    print("\n" + "=" * 50)
    print(" 🧩 Theseus Core CLI Agent (Gemini 3.1 Ready)")
    print("=" * 50)

    sm = TheseusStateMachine(initial_mode=AgentMode.AGENT)
    user_level = 5
    project_tool_permissions = {
        "bash": 3, "read_file": 1, "write_file": 2, "edit_file": 2,
        "glob": 1, "grep": 1, "web_search": 1, "web_fetch": 1,
        "dummy_echo": 1, "create_tool": 2, "system_reboot": 5,
        "search_knowledge_base": 1, "ingest_document": 2,
    }

    model_name = os.getenv("OPENHARNESS_MODEL", "google/gemini-3.1-pro-preview-customtools")
    os.environ["OPENHARNESS_MODEL"] = model_name

    async def ask_permission(tool_name: str, prompt_msg: str) -> str:
        print(prompt_msg, end="", flush=True)
        return input().strip()

    client = TheseusLLMClient(model_name)
    engine, _ = await setup_engine(
        sm, user_level, project_tool_permissions, ask_permission,
        api_client=client, reset_stats=True,
    )

    history = load_session_history("default")
    if history:
        engine.load_messages(history)
        print(f"[*] Loaded {len(history)} messages from previous session.")

    # 미완료 Plan 재개 제안
    auto_resume_line = None
    incomplete_plan = load_plan_state("default")
    if incomplete_plan and incomplete_plan.get("phase") == "Executing":
        last_err = incomplete_plan.get("last_error", "알 수 없는 오류")
        print(f"\n[!] 이전에 중단된 계획이 있습니다. (마지막 에러: {last_err})")
        print("[?] 이어서 실행하시겠습니까? [y/n]: ", end="", flush=True)
        if input().strip().lower() in ("y", "yes"):
            sm.switch_mode(AgentMode.PLAN)
            sm.set_plan_phase(PlanPhase.EXECUTING)
            sm.plan = incomplete_plan.get("plan_json", "")
            engine.set_system_prompt(sm.get_system_prompt())
            auto_resume_line = (
                f"[System Alert] Previous execution was interrupted due to: '{last_err}'. "
                "Resume from the point of interruption and execute remaining steps immediately."
            )
            print("[*] Plan 실행을 재개합니다...")
        else:
            clear_plan_state("default")
            print("[*] 이전 계획을 폐기했습니다.")

    print_help(
        mode=sm.mode.name,
        user_level=user_level,
        plan_phase=getattr(sm, "plan_phase", None) and sm.plan_phase.name,
    )

    ctx = CLIContext(
        sm=sm, engine=engine, client=client,
        user_level=user_level,
        project_tool_permissions=project_tool_permissions,
        ask_permission=ask_permission,
    )

    while True:
        try:
            # ── 입력 수신 ──────────────────────────────────────────
            if auto_resume_line:
                line = auto_resume_line
                auto_resume_line = None
            else:
                line = input("user> ").strip()
                if not line:
                    continue
                ctx.auto_resume_count = 0
                ctx.waiting_for_user = False

            if line.lower() in ("exit", "quit"):
                break

            # ── 슬래시 명령어 처리 ─────────────────────────────────
            if line.startswith("/"):
                parts = line.split()
                cmd, args = parts[0].lower(), parts[1:]
                should_continue, new_line = await handle_slash_command(cmd, args, ctx)
                if should_continue:
                    continue
                if new_line is not None:
                    line = new_line
                # new_line=None → 미인식 명령어, 원문 그대로 LLM에 전달

            # ── Plan WAIT_FOR_REVIEW: 승인 또는 피드백 처리 ─────────
            if ctx.sm.mode == AgentMode.PLAN and ctx.sm.plan_phase == PlanPhase.WAIT_FOR_REVIEW:
                if await llm_is_approval(line, ctx.client):
                    ctx.sm.set_plan_phase(PlanPhase.EXECUTING)
                    ctx.engine.set_system_prompt(ctx.sm.get_system_prompt())
                    ctx.waiting_for_user = False
                    print("[*] ✅ 사용자의 긍정적 동의를 확인했습니다. 계획 실행 단계를 시작합니다.")
                    line = f"{line}\n(계획이 승인되었습니다. 즉시 단계별 실행을 시작하세요.)"
                else:
                    parsed_fb = parse_plan_feedback(line, ctx.sm.plan)
                    if parsed_fb:
                        _label = f"{parsed_fb['target']}.{parsed_fb['field']}" if parsed_fb.get("field") else parsed_fb["target"]
                        print(f"[*] [{_label}] 피드백 반영 중...")
                        line = build_feedback_prompt(parsed_fb, ctx.sm.plan)

            # ── 자동 재개 초과 후 EXECUTING 진입 차단 ─────────────────
            if ctx.waiting_for_user and ctx.sm.mode == AgentMode.PLAN and ctx.sm.plan_phase == PlanPhase.EXECUTING:
                ctx.waiting_for_user = False  # 사용자가 입력했으므로 플래그 해제 후 정상 처리

            # ── 엔진 재구성 + 메시지 압축 ─────────────────────────────
            current_messages = list(ctx.engine.messages)
            current_messages, did_compress = await maybe_compress(current_messages)
            if did_compress:
                print(f"[*] 컨텍스트 압축 완료: {len(current_messages)}개 메시지로 축약")

            ctx.engine, _ = await setup_engine(
                ctx.sm, ctx.user_level, ctx.project_tool_permissions, ctx.ask_permission,
                api_client=ctx.client, user_query=line, top_k=8,
                history_messages=current_messages,
            )
            ctx.engine.load_messages(current_messages)

            # ── 모드 전환 알림 + DRAFTING 형식 강제 주입 ──────────────
            actual_line = line
            if ctx.pending_mode_notification:
                actual_line = ctx.pending_mode_notification + actual_line
                ctx.pending_mode_notification = ""
            if ctx.sm.mode == AgentMode.PLAN and ctx.sm.plan_phase == PlanPhase.DRAFTING:
                actual_line = (
                    f"{actual_line}\n\n"
                    "IMPORTANT: You are in PLAN DRAFTING mode. "
                    "Output ONLY the JSON block following the strict schema. "
                    "No conversational prose allowed."
                )

            # ── 스트리밍 실행 ──────────────────────────────────────────
            print("assistant> ", end="", flush=True)
            accumulated_text = ""
            tool_called_this_turn = False
            tool_error_occurred = False
            plan_complete = False

            async for event in ctx.engine.submit_message(actual_line):
                if isinstance(event, AssistantTextDelta):
                    accumulated_text += event.text
                    print(event.text, end="", flush=True)
                elif isinstance(event, ToolExecutionStarted):
                    tool_called_this_turn = True
                    print(f"\n[*] Executing tool: {event.tool_name}...", flush=True)
                    await record_tool_call(line, event.tool_name)
                elif isinstance(event, ToolExecutionCompleted):
                    print(f"[*] Tool '{event.tool_name}' result received.", flush=True)
                    if event.is_error:
                        tool_error_occurred = True
                elif isinstance(event, AssistantTurnComplete):
                    print("\n", flush=True)
                    if ctx.sm.mode == AgentMode.PLAN:
                        if ctx.sm.plan_phase == PlanPhase.DRAFTING:
                            handle_plan_draft(ctx.sm, accumulated_text)
                            ctx.engine.set_system_prompt(ctx.sm.get_system_prompt())
                        elif ctx.sm.plan_phase == PlanPhase.WAIT_FOR_REVIEW:
                            updated = extract_plan_json(accumulated_text)
                            if updated:
                                ctx.sm.plan = json.dumps(updated, ensure_ascii=False, indent=2)
                                try:
                                    Path("temp").mkdir(exist_ok=True)
                                    with open("temp/plan_refactored.json", "w", encoding="utf-8") as f:
                                        json.dump(updated, f, ensure_ascii=False, indent=2)
                                except Exception:
                                    pass
                                display_plan(updated)
                                print("[*] 계획이 업데이트되었습니다.")
                        elif ctx.sm.plan_phase == PlanPhase.EXECUTING:
                            lower = accumulated_text.lower()
                            if any(kw in lower for kw in ("plan complete", "all steps complete", "execution complete", "all tasks done")):
                                ctx.sm.set_plan_phase(PlanPhase.VERIFYING)
                                print("[*] 실행 완료 — 검증(Verifying) 단계로 전환합니다.")
                                line = "Execution is complete. Please verify the changes."
                        elif ctx.sm.plan_phase == PlanPhase.VERIFYING:
                            lower = accumulated_text.lower()
                            if any(kw in lower for kw in ("verification complete", "all verified", "verified successfully")):
                                plan_complete = True
                                clear_plan_state("default")
                elif isinstance(event, ErrorEvent):
                    print(f"\n[API ERROR] {event.message}", flush=True)
                else:
                    print(f"\n[EVENT] {type(event).__name__}: {event}", flush=True)

            # ── 자동 재개 판단 ─────────────────────────────────────────
            should_auto_resume = False
            resume_prompt = "Continue. Execute the next step immediately."

            is_asking_user = any(
                kw in accumulated_text
                for kw in ["?", "should I", "would you", "do you want", "please confirm", "let me know"]
            )

            if ctx.sm.mode == AgentMode.PLAN and ctx.sm.plan_phase in (PlanPhase.EXECUTING, PlanPhase.VERIFYING):
                if is_asking_user:
                    print("\n[*] 에이전트가 사용자 결정을 대기 중입니다. (자동 재개 취소)")
                elif not tool_called_this_turn and not plan_complete:
                    should_auto_resume = True
                elif tool_error_occurred:
                    should_auto_resume = True
                    resume_prompt = "A tool execution error occurred. Review the error, find a solution, and retry."
            elif ctx.sm.mode == AgentMode.AGENT and tool_error_occurred:
                should_auto_resume = True
                resume_prompt = "A tool execution error just occurred. Analyze the root cause and retry with a different approach."

            if should_auto_resume and not plan_complete:
                error_sig = resume_prompt[:80]
                if error_sig == ctx.last_error_sig:
                    ctx.repeated_error_count += 1
                else:
                    ctx.repeated_error_count = 1
                    ctx.last_error_sig = error_sig

                if ctx.repeated_error_count > ctx.MAX_REPEATED_ERRORS:
                    print(f"[!] 동일한 에러가 {ctx.repeated_error_count}회 반복되었습니다. 접근 방식 전환을 요청합니다.")
                    resume_prompt = (
                        f"The same error has occurred {ctx.repeated_error_count} times consecutively. "
                        "You MUST completely change your approach. "
                        "If you cannot resolve it alone, report the situation to the user and ask for help."
                    )
                    ctx.repeated_error_count = 0
                    ctx.last_error_sig = ""

                ctx.auto_resume_count += 1
                if ctx.auto_resume_count > ctx.MAX_AUTO_RESUME:
                    print(f"[!] 자동 재개 {ctx.MAX_AUTO_RESUME}회 초과. 사용자 입력을 기다립니다.")
                    ctx.auto_resume_count = 0
                    ctx.waiting_for_user = True
                    if ctx.sm.mode == AgentMode.PLAN and ctx.sm.plan_phase in (PlanPhase.EXECUTING, PlanPhase.VERIFYING):
                        ctx.sm.set_plan_phase(PlanPhase.WAIT_FOR_REVIEW)
                        ctx.engine.set_system_prompt(ctx.sm.get_system_prompt())
                        print("[*] 계획 검토(Review) 단계로 전환됩니다. 대화로 문제를 파악하고 'approve'로 재개하세요.")
                    await save_session_history("default", ctx.engine.messages)
                else:
                    print(f"[auto] {resume_prompt[:30]}... (자동 재개 {ctx.auto_resume_count}/{ctx.MAX_AUTO_RESUME})")
                    auto_resume_line = resume_prompt
                    await save_session_history("default", ctx.engine.messages)
                    continue

            await save_session_history("default", ctx.engine.messages)

        except KeyboardInterrupt:
            break
        except Exception as e:
            print(f"\n[ERROR] {e}")
            await save_session_history("default", ctx.engine.messages)

            error_str = str(e).lower()
            if any(kw in error_str for kw in ("max turns", "turn limit", "maximum", "limit")):
                if ctx.sm.mode == AgentMode.PLAN and ctx.sm.plan_phase == PlanPhase.EXECUTING:
                    save_plan_state("default", plan_json=getattr(ctx.sm, "plan", ""), phase="Executing", last_error=str(e))
                    print("[*] Plan 상태가 저장되었습니다. 자동으로 재개합니다...")
                    auto_resume_line = (
                        f"[System Alert] Previous execution was interrupted due to turn limit: {e}\n"
                        "Resume from the point of interruption. Do NOT repeat the same approach."
                    )
                    ctx.auto_resume_count += 1
                    if ctx.auto_resume_count > ctx.MAX_AUTO_RESUME:
                        print(f"[!] 자동 재개 {ctx.MAX_AUTO_RESUME}회 초과. 사용자 입력을 기다립니다.")
                        ctx.auto_resume_count = 0
                        ctx.waiting_for_user = True
                        ctx.sm.set_plan_phase(PlanPhase.WAIT_FOR_REVIEW)
                        ctx.engine.set_system_prompt(ctx.sm.get_system_prompt())
                        print("[*] 계획 검토(Review) 단계로 전환됩니다. 'approve'로 재개하세요.")
                    else:
                        continue

            if ctx.sm.mode == AgentMode.PLAN and ctx.sm.plan_phase == PlanPhase.EXECUTING:
                err_sig = str(e)[:80]
                ctx.repeated_error_count = ctx.repeated_error_count + 1 if err_sig == ctx.last_error_sig else 1
                ctx.last_error_sig = err_sig

                ctx.auto_resume_count += 1
                if ctx.auto_resume_count > ctx.MAX_AUTO_RESUME:
                    print(f"[!] 자동 재개 {ctx.MAX_AUTO_RESUME}회 초과. 사용자 입력을 기다립니다.")
                    ctx.auto_resume_count = 0
                    ctx.waiting_for_user = True
                    ctx.sm.set_plan_phase(PlanPhase.WAIT_FOR_REVIEW)
                    ctx.engine.set_system_prompt(ctx.sm.get_system_prompt())
                    print("[*] 계획 검토(Review) 단계로 전환됩니다. 'approve'로 재개하세요.")
                elif ctx.repeated_error_count > ctx.MAX_REPEATED_ERRORS:
                    print(f"[!] 동일 에러 {ctx.repeated_error_count}회 반복. 접근 방식 전환을 요청합니다.")
                    auto_resume_line = (
                        f"The same error '{str(e)[:100]}' has repeated {ctx.repeated_error_count} times. "
                        "Completely change your approach, or report the situation to the user if you cannot."
                    )
                    ctx.repeated_error_count = 0
                    ctx.last_error_sig = ""
                    continue
                else:
                    print("[*] 에러 발생 후 자동으로 복구 시도 중 (PLAN 모드)...")
                    auto_resume_line = f"An error occurred: {e}\nAnalyze the root cause and continue with the next step or fix the error."
                    continue

    print("\n[*] Saving session and exiting...")
    await save_session_history("default", ctx.engine.messages)
    try:
        await CostTracker.get_or_create().save_async()
    except Exception:
        pass
    print("Done. Goodbye!")


if __name__ == "__main__":
    asyncio.run(run_cli())
