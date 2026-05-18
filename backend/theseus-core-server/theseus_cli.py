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

from theseus_engine.engine.stream_events import (
    AssistantTextDelta, AssistantTurnComplete,
    ToolExecutionStarted, ToolExecutionCompleted, ErrorEvent,
)
from theseus_engine.core.engine_builder import setup_engine
from theseus_engine.core.tool_usage_logger import record_tool_call_async as record_tool_call
from theseus_engine.core.context_compressor import maybe_compress
from theseus_engine.models.modes import AgentMode, PlanPhase
from theseus_engine.models.state import TheseusStateMachine
from theseus_engine.engine.cost_tracker import CostTracker
from theseus_engine.models.sessions import (
    save_session_history_async as save_session_history,
    load_session_history,
    save_plan_state,
    load_plan_state,
    clear_plan_state,
)
from theseus_engine.wrappers.llm_clients.theseus_client import TheseusLLMClient

from theseus_engine.client.project_client import init_project_session, get_project_client
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

    # ── 프로젝트 설정 (standalone 기본값 → 서버 연동 시 덮어씀) ──────
    user_level = 5
    actor_role = "ADMIN"  # standalone: 로컬 사용자 = ADMIN
    project_tool_permissions = {
        "bash": 3, "read_file": 1, "write_file": 2, "edit_file": 2,
        "local_write_report": 2,
        "glob": 1, "grep": 1, "web_search": 1, "web_fetch": 1,
        "dummy_echo": 1, "create_tool": 2, "system_reboot": 5,
        "search_knowledge_base": 1, "ingest_document": 2,
    }
    _project_id = os.getenv("THESEUS_PROJECT_ID", "local")
    _session_token = os.getenv("THESEUS_SESSION_TOKEN", "")
    _session_id = ""

    proj_client = get_project_client()
    if proj_client.is_enabled:
        print("[*] 서버 연동 활성화 — 프로젝트 설정을 가져오는 중...")
        try:
            proj_cfg = await init_project_session(_project_id, token=_session_token)
            user_level = proj_cfg.user_level
            actor_role = proj_cfg.actor_role
            if proj_cfg.tool_permissions:
                project_tool_permissions.update(proj_cfg.tool_permissions)
            _session_id = proj_cfg.session_id
            print(f"[*] 프로젝트 설정 로드 완료 (role={actor_role}, level={user_level})")
        except Exception as _e:
            print(f"[!] 프로젝트 설정 로드 실패 — standalone 기본값 사용: {_e}")

    model_name = os.getenv("THESEUS_MODEL", "google/gemini-3.1-pro-preview-customtools")
    os.environ["THESEUS_MODEL"] = model_name

    async def ask_permission(tool_name: str, prompt_msg: str) -> str:
        print(prompt_msg, end="", flush=True)
        return input().strip()

    client = TheseusLLMClient(model_name)
    engine, full_registry = await setup_engine(
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
        actor_role=actor_role,
    )

    ctx = CLIContext(
        sm=sm, engine=engine, client=client,
        user_level=user_level,
        actor_role=actor_role,
        project_tool_permissions=project_tool_permissions,
        ask_permission=ask_permission,
        full_registry=full_registry,
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
                    ctx.auto_resume_count = 0  # 턴 단위 카운터만 리셋 (session_resume_total 유지)
                    ctx.repeated_error_count = 0
                    ctx.last_error_sig = ""
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

            runtime_reminders = ctx.pending_mode_reminders
            ctx.pending_mode_reminders = ()
            if ctx.sm.mode == AgentMode.PLAN and ctx.sm.plan_phase == PlanPhase.DRAFTING:
                runtime_reminders = (
                    *runtime_reminders,
                    (
                        "You are in PLAN DRAFTING mode. If this is a question "
                        "or clarification, answer it directly in natural language. "
                        "If this is an implementation request, research the codebase "
                        "first, then output a JSON plan."
                    ),
                )

            ctx.engine, new_full_registry = await setup_engine(
                ctx.sm, ctx.user_level, ctx.project_tool_permissions, ctx.ask_permission,
                api_client=ctx.client, user_query=line, top_k=8,
                history_messages=current_messages,
                runtime_reminders=runtime_reminders,
            )
            ctx.full_registry = new_full_registry
            ctx.engine.load_messages(current_messages)

            # ── 스트리밍 입력 준비 ──────────────────────────────────
            actual_line = line

            # ── 스트리밍 실행 ──────────────────────────────────────────
            print("assistant> ", end="", flush=True)
            accumulated_text = ""
            tool_called_this_turn = False
            tool_error_occurred = False
            plan_complete = False
            newly_created_tools: list[str] = []  # 이번 턴에 create_tool로 등록된 툴 이름 목록

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
                    elif event.tool_name == "create_tool":
                        # 성공적으로 생성된 툴 이름을 output에서 파싱
                        import re as _re
                        m = _re.search(r"Tool '([^']+)' created", event.output)
                        if m:
                            newly_created_tools.append(m.group(1))
                elif isinstance(event, AssistantTurnComplete):
                    print("\n", flush=True)
                    # ── 커스텀 툴 자동 등록 알림 ──────────────────────────
                    if newly_created_tools:
                        _auto_print_created_tools(newly_created_tools, ctx)
                        # full_registry를 최신 상태로 갱신 (다음 /tools custom 조회 반영)
                        ctx.full_registry = ctx.engine._tool_metadata.get(
                            "tool_registry", ctx.full_registry
                        )
                        newly_created_tools.clear()
                    if ctx.sm.mode == AgentMode.PLAN:
                        if ctx.sm.plan_phase == PlanPhase.DRAFTING:
                            drafted = handle_plan_draft(ctx.sm, accumulated_text)
                            if drafted:
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
                # 실제 에러 내용을 시그니처로 사용 (고정 resume_prompt 대신)
                if tool_error_occurred:
                    error_sig = accumulated_text[-200:].strip()[:80]
                else:
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
                ctx.session_resume_total += 1

                # 세션 전체 절대 상한 초과 — 무한루프 최종 차단
                if ctx.session_resume_total > ctx.MAX_SESSION_RESUMES:
                    print(f"[!] 세션 전체 자동 재개 {ctx.MAX_SESSION_RESUMES}회 초과. 강제 종료합니다.")
                    ctx.waiting_for_user = True
                    if ctx.sm.mode == AgentMode.PLAN and ctx.sm.plan_phase in (PlanPhase.EXECUTING, PlanPhase.VERIFYING):
                        ctx.sm.set_plan_phase(PlanPhase.WAIT_FOR_REVIEW)
                        ctx.engine.set_system_prompt(ctx.sm.get_system_prompt())
                    print("[*] 반복 실패로 인해 실행이 중단되었습니다. 문제를 직접 파악한 후 'approve'로 재개하세요.")
                    await save_session_history("default", ctx.engine.messages)
                elif ctx.auto_resume_count > ctx.MAX_AUTO_RESUME:
                    print(f"[!] 자동 재개 {ctx.MAX_AUTO_RESUME}회 초과. 사용자 입력을 기다립니다.")
                    ctx.auto_resume_count = 0
                    ctx.waiting_for_user = True
                    if ctx.sm.mode == AgentMode.PLAN and ctx.sm.plan_phase in (PlanPhase.EXECUTING, PlanPhase.VERIFYING):
                        ctx.sm.set_plan_phase(PlanPhase.WAIT_FOR_REVIEW)
                        ctx.engine.set_system_prompt(ctx.sm.get_system_prompt())
                        print("[*] 계획 검토(Review) 단계로 전환됩니다. 대화로 문제를 파악하고 'approve'로 재개하세요.")
                    await save_session_history("default", ctx.engine.messages)
                else:
                    print(f"[auto] {resume_prompt[:30]}... (자동 재개 {ctx.auto_resume_count}/{ctx.MAX_AUTO_RESUME}, 세션 누적 {ctx.session_resume_total}/{ctx.MAX_SESSION_RESUMES})")
                    auto_resume_line = resume_prompt
                    await save_session_history("default", ctx.engine.messages)
                    continue

            await save_session_history("default", ctx.engine.messages)
            if proj_client.is_enabled and _session_id:
                await proj_client.sync_history(_session_id, list(ctx.engine.messages), token=_session_token)
                _cost = CostTracker.get_or_create()
                await proj_client.report_usage(
                    _session_id,
                    {"inputTokens": _cost.total_input_tokens, "outputTokens": _cost.total_output_tokens},
                    token=_session_token,
                )

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
                    ctx.session_resume_total += 1
                    if ctx.session_resume_total > ctx.MAX_SESSION_RESUMES:
                        print(f"[!] 세션 전체 자동 재개 {ctx.MAX_SESSION_RESUMES}회 초과. 강제 중단합니다.")
                        ctx.waiting_for_user = True
                        ctx.sm.set_plan_phase(PlanPhase.WAIT_FOR_REVIEW)
                        ctx.engine.set_system_prompt(ctx.sm.get_system_prompt())
                        print("[*] 반복 실패로 인해 실행이 중단되었습니다. 'approve'로 재개하세요.")
                    elif ctx.auto_resume_count > ctx.MAX_AUTO_RESUME:
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
                ctx.session_resume_total += 1

                if ctx.session_resume_total > ctx.MAX_SESSION_RESUMES:
                    print(f"[!] 세션 전체 자동 재개 {ctx.MAX_SESSION_RESUMES}회 초과. 강제 중단합니다.")
                    ctx.waiting_for_user = True
                    ctx.sm.set_plan_phase(PlanPhase.WAIT_FOR_REVIEW)
                    ctx.engine.set_system_prompt(ctx.sm.get_system_prompt())
                    print("[*] 반복 실패로 인해 실행이 중단되었습니다. 'approve'로 재개하세요.")
                elif ctx.auto_resume_count > ctx.MAX_AUTO_RESUME:
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


def _auto_print_created_tools(tool_names: list[str], ctx) -> None:
    """create_tool 성공 직후 자동으로 등록된 툴 정보를 출력합니다."""
    import json, os
    from theseus_engine.tools.core.tool_factory import CUSTOM_TOOLS_DIR

    print("\n" + "─" * 60)
    print(f"  ✨ 새 커스텀 툴 등록 완료 ({len(tool_names)}개)")
    print("─" * 60)

    for tool_name in tool_names:
        # meta.json 읽기 (모듈명 = tool_name 또는 snake_case 변환 시도)
        module_name = tool_name.replace("-", "_")
        meta_path = os.path.join(CUSTOM_TOOLS_DIR, f"{module_name}.meta.json")
        meta: dict = {}
        if os.path.exists(meta_path):
            try:
                with open(meta_path, encoding="utf-8") as f:
                    meta = json.load(f)
            except (json.JSONDecodeError, OSError):
                pass

        perm   = meta.get("permissionLevel", ctx.project_tool_permissions.get(tool_name, 1))
        status = meta.get("status", "active")
        fname  = meta.get("fileName", f"{module_name}.py")

        # registry에서 인스턴스 조회 → description
        description = ""
        registry = ctx.full_registry or (
            ctx.engine._tool_metadata.get("tool_registry") if ctx.engine else None
        )
        if registry:
            instance = registry.get(tool_name)
            if instance:
                description = getattr(instance, "description", "")
        desc_short = (description[:55] + "…") if len(description) > 56 else description

        print(f"\n  🔧 {tool_name}")
        print(f"     권한 레벨   : Lv.{perm}")
        print(f"     상태        : {status}")
        print(f"     파일        : custom_tools/{fname}")
        if desc_short:
            print(f"     설명        : {desc_short}")

        # validation 결과
        v = meta.get("validationResult") or {}
        if v.get("status") == "validated":
            print(f"     검증        : ✅ 통과")
        elif v.get("status"):
            print(f"     검증        : ⚠️  {v.get('status')} — {v.get('message', '')}")

    print("\n  💡 '/tools custom' 으로 전체 커스텀 툴 목록을 확인할 수 있습니다.")
    print("─" * 60 + "\n")


if __name__ == "__main__":
    asyncio.run(run_cli())
