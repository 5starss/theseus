"""CLI 화면 출력 전담 모듈 — 순수 표현 함수만 포함합니다."""

from __future__ import annotations

import sys


_TIER_LABELS = {"T1": "Quick Win", "T2": "Strategic", "T3": "Architecture"}
_TIER_ICONS  = {"T1": "[T1]", "T2": "[T2]", "T3": "[T3]"}


def safe_hr(width: int) -> str:
    try:
        "─".encode(sys.stdout.encoding or "utf-8")
        return "─" * width
    except (UnicodeEncodeError, LookupError):
        return "-" * width


def status_mark(status: str) -> str:
    return {"pending": "[ ]", "done": "[v]", "running": "[~]", "failed": "[x]"}.get(status, "[ ]")


_MODE_LABELS = {
    "AGENT":       "🤖 AGENT       (자율 실행)",
    "ASK":         "💬 ASK         (질의응답 전용)",
    "PLAN":        "📋 PLAN        (계획 → 리뷰 → 실행)",
    "COORDINATOR": "🔀 COORDINATOR (서브 에이전트 오케스트레이션)",
}


def print_status(mode: str, user_level: int, plan_phase: str | None = None) -> None:
    """현재 모드와 권한 레벨을 헤더로 출력합니다."""
    mode_label = _MODE_LABELS.get(mode, f"❓ {mode}")
    phase_str  = f"  /  Phase: {plan_phase}" if plan_phase and mode == "PLAN" else ""
    print(f"\n  현재 모드  : {mode_label}{phase_str}")
    print(f"  권한 레벨  : Lv.{user_level}  (1=최소 / 5=최대)")


def print_help(mode: str = "AGENT", user_level: int = 5, plan_phase: str | None = None) -> None:
    print("\n" + "-" * 50)
    print(" Theseus CLI - 사용 가능한 명령어")
    print("-" * 50)
    print_status(mode, user_level, plan_phase)
    print("  [모드 전환]")
    print("    /agent            자율 실행 모드 (기본)")
    print("    /ask              질문/답변 전용 (도구 사용 안 함)")
    print("    /plan             계획 -> 리뷰 -> 실행 파이프라인")
    print("    /coordinator      병렬 서브 에이전트 오케스트레이션")
    print()
    print("  [도구 및 권한]")
    print("    /tools            전체 활성 툴 목록 (커스텀 툴 [custom] 태그 표시)")
    print("    /tools custom     커스텀 툴만 필터링하여 상세 정보 표시")
    print("    /tools help       /tools 서브커맨드 도움말")
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
    print("    approve           계획 승인 및 실행 시작 (자연어도 인식)")
    print("    /approve          계획 승인 및 실행 시작 (슬래시 버전)")
    print("    /reject           계획 거부 및 Agent 모드 복귀")
    print("    /pause, /stop     실행 중지 → WAIT_FOR_REVIEW 단계 강등")
    print()
    print("  [기타]")
    print("    /help             이 도움말 다시 보기")
    print("    exit / quit       프로그램 종료")
    print("-" * 50 + "\n")


def display_plan(plan_data: dict) -> None:
    w = 70
    print("\n" + "=" * w)
    print(f"  THESEUS PLAN: {plan_data.get('goal', '(목표 없음)')}")
    print("=" * w)

    ctx = plan_data.get("context")
    if isinstance(ctx, dict):
        if ctx.get("problem_analysis"):
            print(f"\n  [Problem]  {ctx['problem_analysis']}")
        if ctx.get("current_state"):
            print(f"  [Context]  {ctx['current_state']}")
        affected = ctx.get("affected_files", [])
        if affected:
            print(f"  [Scope]    {', '.join(affected[:5])}"
                  + (f" (+{len(affected)-5} more)" if len(affected) > 5 else ""))
        if ctx.get("risks"):
            print(f"  [Risks]    {ctx['risks']}")
    elif isinstance(ctx, str) and ctx:
        print(f"\n  [Context]  {ctx}")

    tasks = plan_data.get("tasks", [])
    main_tasks = [t for t in tasks if not t.get("parent_id")]

    tier_groups: dict[str, list] = {}
    for mt in main_tasks:
        tier_groups.setdefault(mt.get("tier", "T2"), []).append(mt)

    for tier_key in ["T1", "T2", "T3"]:
        group = tier_groups.get(tier_key)
        if not group:
            continue
        label = _TIER_LABELS.get(tier_key, tier_key)
        print(f"\n  {safe_hr(w - 4)}")
        print(f"  {_TIER_ICONS.get(tier_key, tier_key)} {label}")
        print(f"  {safe_hr(w - 4)}")

        for mt in group:
            mark = status_mark(mt.get("status", "pending"))
            print(f"\n  {mark} [{mt['id']}] {mt['title']}")
            if mt.get("problem"):
                print(f"        Problem:  {mt['problem']}")
            if mt.get("solution"):
                print(f"        Solution: {mt['solution']}")
            if mt.get("target_files"):
                print(f"        Files:    {', '.join(mt['target_files'][:4])}")
            if mt.get("expected_effect"):
                print(f"        Effect:   {mt['expected_effect']}")
            if mt.get("integration_points"):
                print(f"        Integr:   {mt['integration_points']}")
            elif mt.get("description") and mt["description"] != mt["title"]:
                print(f"        Desc:     {mt['description']}")
            for st in [t for t in tasks if t.get("parent_id") == mt["id"]]:
                st_mark = status_mark(st.get("status", "pending"))
                print(f"      {st_mark} [{st['id']}] {st['title']}")
                if st.get("target_files"):
                    print(f"            Files: {', '.join(st['target_files'][:3])}")

    no_tier = [t for t in main_tasks if t.get("tier") not in _TIER_LABELS]
    if no_tier and not tier_groups:
        for mt in no_tier:
            mark = status_mark(mt.get("status", "pending"))
            print(f"\n  {mark} [{mt['id']}] {mt['title']}")
            if mt.get("description") and mt["description"] != mt["title"]:
                print(f"        {mt['description']}")
            for st in [t for t in tasks if t.get("parent_id") == mt["id"]]:
                print(f"    {status_mark(st.get('status', 'pending'))} [{st['id']}] {st['title']}")

    verif = plan_data.get("verification")
    if isinstance(verif, dict):
        print(f"\n  {safe_hr(w - 4)}")
        print("  [Verification Plan]")
        for cmd in verif.get("test_commands", []):
            print(f"    $ {cmd}")
        for chk in verif.get("manual_checks", []):
            print(f"    - {chk}")
        if verif.get("success_criteria"):
            print(f"    Success: {verif['success_criteria']}")

    action = plan_data.get("action_plan")
    if isinstance(action, dict):
        print(f"\n  {safe_hr(w - 4)}")
        print("  [Action Plan]")
        if action.get("immediate"):
            print(f"    Immediate: {', '.join(action['immediate'])}")
        if action.get("sequential_dependencies"):
            print(f"    Deps:      {action['sequential_dependencies']}")
        if action.get("estimated_turns"):
            print(f"    Est turns: {action['estimated_turns']}")

    print("\n" + "-" * w)
    print("  [*] 'approve' / '/approve'            : 계획 승인 및 실행")
    print("  [*] '<task-id>: <피드백>'              : 태스크 전체 수정")
    print("  [*] '<task-id>.<field>: <피드백>'      : 태스크 필드 수정")
    print("       fields: problem, solution, target_files,")
    print("               expected_effect, description, tier")
    print("  [*] '<section>.<field>: <피드백>'      : 섹션 필드 수정")
    print("       sections: context, verification, action_plan")
    print("  [*] 일반 텍스트 입력                   : 전체 계획 수정 요청")
    print("-" * w + "\n")
