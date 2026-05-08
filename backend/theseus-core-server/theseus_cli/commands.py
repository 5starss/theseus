"""슬래시 명령어 라우터.

반환값: (should_continue: bool, new_line: str | None)
  - (True,  None)     → 메인 루프에서 continue (LLM 호출 없음)
  - (False, str)      → line을 str로 교체한 뒤 LLM으로 전달
  - (False, None)     → 인식되지 않은 명령어, 원문 그대로 처리
"""

from __future__ import annotations

import os
import sys
from typing import TYPE_CHECKING

from theseus_cli.context import CLIContext
from theseus_cli.ui import print_help, print_status

if TYPE_CHECKING:
    pass


async def handle_slash_command(
    cmd: str, args: list[str], ctx: CLIContext
) -> tuple[bool, str | None]:
    from theseus_engine.models.state import AgentMode, PlanPhase
    from theseus_engine.core.engine_builder import setup_engine

    # ── 세션 관리 ──────────────────────────────────────────────
    if cmd == "/clear":
        ctx.engine.clear()
        print("[*] Session cleared.")
        return True, None

    # ── 모드 전환 ───────────────────────────────────────────────
    elif cmd == "/plan":
        ctx.sm.switch_mode(AgentMode.PLAN)
        ctx.engine.set_system_prompt(ctx.sm.get_system_prompt())
        ctx.pending_mode_notification = (
            "[System: Mode switched to PLAN. Research the codebase and produce a structured JSON plan. No code execution yet.]\n\n"
        )
        print_status(ctx.sm.mode.name, ctx.user_level)
        return True, None

    elif cmd == "/agent":
        ctx.sm.switch_mode(AgentMode.AGENT)
        ctx.engine.set_system_prompt(ctx.sm.get_system_prompt())
        ctx.pending_mode_notification = (
            "[System: Mode switched to AGENT. All tools are now available. Ignore any prior restrictions — execute tasks directly using tools.]\n\n"
        )
        print_status(ctx.sm.mode.name, ctx.user_level)
        return True, None

    elif cmd == "/ask":
        ctx.sm.switch_mode(AgentMode.ASK)
        ctx.engine.set_system_prompt(ctx.sm.get_system_prompt())
        ctx.pending_mode_notification = (
            "[System: Mode switched to ASK. Tool use is strictly prohibited. Answer only with text.]\n\n"
        )
        print_status(ctx.sm.mode.name, ctx.user_level)
        return True, None

    elif cmd == "/coordinator":
        ctx.sm.switch_mode(AgentMode.COORDINATOR)
        ctx.engine.set_system_prompt(ctx.sm.get_system_prompt())
        ctx.pending_mode_notification = (
            "[System: Mode switched to COORDINATOR. Decompose the task into parallel sub-agents. "
            "All prior mode restrictions are lifted.]\n\n"
        )
        print_status(ctx.sm.mode.name, ctx.user_level)
        return True, None

    # ── Plan 제어 ───────────────────────────────────────────────
    elif cmd in ("/pause", "/stop"):
        if ctx.sm.mode == AgentMode.PLAN and ctx.sm.plan_phase in (PlanPhase.EXECUTING, PlanPhase.VERIFYING):
            ctx.sm.set_plan_phase(PlanPhase.WAIT_FOR_REVIEW)
            ctx.engine.set_system_prompt(ctx.sm.get_system_prompt())
            ctx.waiting_for_user = True
            print("[*] 실행이 일시 중지되었습니다. (WAIT_FOR_REVIEW 단계로 전환)")
            print("[*] 대화로 문제를 파악한 뒤 'approve'를 입력하면 재개합니다.")
        else:
            print("[!] 현재 실행 중인 계획이 없습니다.")
        return True, None

    elif cmd == "/approve":
        if ctx.sm.mode == AgentMode.PLAN and ctx.sm.plan_phase == PlanPhase.WAIT_FOR_REVIEW:
            ctx.sm.set_plan_phase(PlanPhase.EXECUTING)
            ctx.engine.set_system_prompt(ctx.sm.get_system_prompt())
            ctx.waiting_for_user = False
            print("[*] 계획이 승인되었습니다. 실행 단계를 시작합니다.")
            return False, "The plan has been approved. Execute each step sequentially."
        else:
            print("[*] 현재 검토 중인 계획이 없습니다. /plan 모드에서 계획을 먼저 작성하세요.")
            return True, None

    elif cmd == "/reject":
        if ctx.sm.mode == AgentMode.PLAN:
            ctx.sm.switch_mode(AgentMode.AGENT)
            ctx.engine.set_system_prompt(ctx.sm.get_system_prompt())
            print("[*] 계획이 거부되었습니다. Agent 모드로 전환합니다.")
        return True, None

    # ── RBAC ────────────────────────────────────────────────────
    elif cmd == "/rbac":
        if not args:
            print_status(ctx.sm.mode.name, ctx.user_level)
        else:
            try:
                ctx.user_level = int(args[0])
                print_status(ctx.sm.mode.name, ctx.user_level)
            except ValueError:
                print("[!] User level must be an integer.")
        return True, None

    # ── 도구 목록 ────────────────────────────────────────────────
    elif cmd == "/tools":
        sub = args[0].lower() if args else "all"

        if sub == "custom":
            _print_custom_tools(ctx)
        elif sub in ("all", "list", ""):
            _print_all_tools(ctx)
        elif sub == "help":
            print(
                "\n[🛠️  /tools 사용법]\n"
                "  /tools           — 전체 활성 툴 목록\n"
                "  /tools all       — 전체 활성 툴 목록 (동일)\n"
                "  /tools custom    — 커스텀 툴만 필터링\n"
                "  /tools help      — 이 도움말\n"
            )
        else:
            print(f"[!] 알 수 없는 서브커맨드: '{sub}'. '/tools help'를 입력하면 사용법을 확인할 수 있습니다.")
        return True, None

    # ── 도구 검증 ────────────────────────────────────────────────
    elif cmd == "/validate":
        if not args:
            print("[!] Usage: /validate <tool_name>")
            return True, None
        from theseus_engine.tools.core.tool_factory import ToolValidator, CUSTOM_TOOLS_DIR
        tool_name = args[0]
        file_path = os.path.join(CUSTOM_TOOLS_DIR, f"{tool_name}.py")
        if not os.path.exists(file_path):
            print(f"[!] Tool file not found: {file_path}")
            return True, None
        print(f"[*] Validating tool: {tool_name}...")
        with open(file_path, "r", encoding="utf-8") as f:
            code = f.read()
        ok, msg = ToolValidator.validate_code(code)
        print(f"--- Analysis Result ---\n{msg}")
        if ok:
            ok2, msg2, _ = ToolValidator.validate_and_load_module(tool_name, file_path)
            print(f"--- Runtime Spec Result ---\n{msg2}")
        return True, None

    # ── 지식 베이스 ──────────────────────────────────────────────
    elif cmd == "/kb":
        if not args:
            print("[!] Usage: /kb <query>")
            return True, None
        from theseus_engine.rag.service import get_rag_service
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
        return True, None

    # ── 비용 / 통계 ──────────────────────────────────────────────
    elif cmd == "/cost":
        from theseus_engine.engine.cost_tracker import CostTracker
        report = "\n" + CostTracker.get_or_create().format_report()
        try:
            print(report)
        except UnicodeEncodeError:
            print(report.encode(sys.stdout.encoding, errors="replace").decode(sys.stdout.encoding))
        return True, None

    elif cmd == "/stats":
        from theseus_engine.observability.stats import SessionStats
        report = "\n" + SessionStats.get().format_report()
        try:
            print(report)
        except UnicodeEncodeError:
            print(report.encode(sys.stdout.encoding, errors="replace").decode(sys.stdout.encoding))
        return True, None

    # ── 도움말 ──────────────────────────────────────────────────
    elif cmd == "/help":
        plan_phase = getattr(ctx.sm, "plan_phase", None)
        print_help(
            mode=ctx.sm.mode.name,
            user_level=ctx.user_level,
            plan_phase=plan_phase.name if plan_phase is not None else None,
        )
        return True, None

    # ── 미인식 명령어 ────────────────────────────────────────────
    return False, None


# ── 내부 헬퍼 ────────────────────────────────────────────────────

def _print_all_tools(ctx: CLIContext) -> None:
    """전체 활성 툴 목록 출력 (커스텀 툴은 [custom] 태그 표시)."""
    from theseus_engine.tools.core.tool_factory import CUSTOM_TOOLS_DIR

    custom_names = _get_custom_tool_names()
    tools = ctx.full_registry.list_tools() if ctx.full_registry else []

    if not tools:
        print("\n[!] 등록된 툴이 없습니다.")
        return

    print(f"\n[🛠️  All Tools] ({len(tools)}개)")
    print(f"{'이름':<24} {'레벨':<6} {'구분'}")
    print("─" * 46)
    for tool in sorted(tools, key=lambda t: t.name):
        perm = ctx.project_tool_permissions.get(tool.name, 1)
        tag = "[custom]" if tool.name in custom_names else "[core]  "
        print(f"  {tool.name:<22} Lv.{perm:<3}  {tag}")
    print()


def _print_custom_tools(ctx: CLIContext) -> None:
    """커스텀 툴만 필터링하여 상세 정보와 함께 출력."""
    import json
    from theseus_engine.tools.core.tool_factory import CUSTOM_TOOLS_DIR

    custom_names = _get_custom_tool_names()

    if not custom_names:
        print("\n[ℹ️ ] 등록된 커스텀 툴이 없습니다.")
        print(f"     커스텀 툴 디렉토리: {CUSTOM_TOOLS_DIR}")
        return

    # full_registry에서 커스텀 툴 인스턴스 조회
    registry_map: dict = {}
    if ctx.full_registry:
        for tool in ctx.full_registry.list_tools():
            if tool.name in custom_names:
                registry_map[tool.name] = tool

    print(f"\n[🔧  Custom Tools] ({len(custom_names)}개)")
    print(f"{'이름':<24} {'레벨':<6} {'상태':<10} {'설명'}")
    print("─" * 80)

    for module_name in sorted(custom_names):
        meta = _load_meta(CUSTOM_TOOLS_DIR, module_name)
        tool_name   = meta.get("toolName", module_name)
        perm        = meta.get("permissionLevel", ctx.project_tool_permissions.get(tool_name, 1))
        status      = meta.get("status", "active")
        is_active   = meta.get("isActive", True)
        status_tag  = f"{'✅' if is_active else '⏸️ '} {status}"

        # description은 registry의 인스턴스에서 읽음
        instance = registry_map.get(tool_name)
        description = getattr(instance, "description", "") if instance else ""
        desc_short  = (description[:38] + "…") if len(description) > 39 else description

        print(f"  {tool_name:<22} Lv.{perm:<3}  {status_tag:<10}  {desc_short}")

        # 상세 정보 (validation 결과)
        validation = meta.get("validationResult") or {}
        v_status = validation.get("status", "")
        if v_status and v_status != "validated":
            print(f"    {'':2}⚠️  validation: {v_status} — {validation.get('message','')}")

    print()
    from theseus_engine.tools.core.tool_factory import CUSTOM_TOOLS_DIR as _DIR
    print(f"  📁 디렉토리: {_DIR}")
    print()


def _get_custom_tool_names() -> set[str]:
    """custom_tools/ 디렉토리에서 .py 파일 기반으로 모듈명 집합을 반환."""
    import os
    from theseus_engine.tools.core.tool_factory import CUSTOM_TOOLS_DIR

    if not os.path.isdir(CUSTOM_TOOLS_DIR):
        return set()
    names: set[str] = set()
    for fname in os.listdir(CUSTOM_TOOLS_DIR):
        if fname.endswith(".py") and not fname.startswith("_"):
            names.add(fname[:-3])  # 모듈명 (확장자 제거)
    return names


def _load_meta(custom_tools_dir: str, module_name: str) -> dict:
    """module_name.meta.json을 읽어 dict로 반환. 파일 없으면 빈 dict."""
    import json, os
    path = os.path.join(custom_tools_dir, f"{module_name}.meta.json")
    if not os.path.exists(path):
        return {}
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError):
        return {}
