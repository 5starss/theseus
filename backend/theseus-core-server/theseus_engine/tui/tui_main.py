"""Theseus TUI — 순수 Textual 기반 독자적 에이전트 UI.

OpenHarness 의존 없음. CLI(`theseus_cli.py`)의 자율 복구 루프를
비동기 워커 패턴으로 그대로 이식합니다.

주요 기능:
  - 비동기 워커(`_agent_worker`) 기반 에이전트 루프 — UI 블로킹 없음
  - Auto-Resume: 툴 에러 시 내부 재시도, MaxTurnsExceeded 시 상태 보존
  - SecurityApprovalModal: 파괴적 툴 실행 전 HITL 팝업
  - 사이드바 동적 전환: PLAN → 태스크 체크리스트 / AGENT → 비용 대시보드
  - 슬래시 커맨드 네이티브 렌더링 (/cost, /stats, /tools, /plan 등)
"""

from __future__ import annotations

import asyncio
import json
import os
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from textual import on, events
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Container, Horizontal, Vertical, ScrollableContainer
from textual.widgets import Footer, Header, Input, Label, OptionList, RichLog, Static

from theseus_engine.core.engine_builder import (
    setup_engine,
    get_tracing_tags,
    get_tracing_metadata,
)
from theseus_engine.engine.query_engine import MaxTurnsExceeded
from theseus_engine.engine.stream_events import (
    AssistantTextDelta,
    AssistantTurnComplete,
    CompactProgressEvent,
    ErrorEvent,
    StatusEvent,
    ToolExecutionCompleted,
    ToolExecutionStarted,
)
from theseus_engine.models.rbac import PermissionMode
from theseus_engine.models.sessions import (
    get_session_path,
    list_sessions,
    load_session_history,
    save_plan_state,
    save_session_history,
)
from theseus_engine.models.state import AgentMode, PlanPhase, TheseusStateMachine
from theseus_engine.observability.tracer import tracing_context
from theseus_engine.tui.autocomplete import AutocompleteHelper
from theseus_engine.tui.commands import CommandRegistry, CommandResult, SlashCommand
from theseus_engine.tui.modals import SecurityApprovalModal
from theseus_engine.tui.runtime import TheseusBundle
from theseus_engine.tui.ui_components import THESEUS_TUI_CSS
from theseus_engine.wrappers.llm_clients.theseus_client import TheseusLLMClient

# ──────────────────────────────────────────────────────────────────
# CSS
# ──────────────────────────────────────────────────────────────────

THESEUS_BASE_CSS = """
Screen { padding: 0; }

#app-container  { width: 100%; height: 100%; }
#main-row       { height: 100%; }

/* ── 메인 컬럼 ── */
#transcript-column { width: 1fr; height: 100%; }
#transcript        { height: 1fr; }
#current-response  { height: 3; border: solid $accent; padding: 0 1; }
#autocomplete {
    display: none; max-height: 8;
    border: solid $accent; background: $panel; margin: 0 1;
}
#autocomplete > .option-list--option-highlighted {
    background: $accent !important;
    color: $surface !important;
    text-style: bold reverse !important;
}

/* ── 사이드바 ── */
#side-column {
    width: 36; height: 100%;
    border-left: vkey $accent;
    padding: 0 1;
}
#status-bar    { height: auto; }
#tasks-panel   { height: auto; margin-top: 1; }
#tools-panel   { height: auto; margin-top: 1; color: $text-muted; }
"""


# ──────────────────────────────────────────────────────────────────
# 커스텀 Input — 슬래시 커맨드 인터셉트
# ──────────────────────────────────────────────────────────────────

class TheseusInput(Input):
    """Theseus 슬래시 커맨드를 위젯 레벨에서 선제 차단하는 커스텀 Input."""

    _THESEUS_CMDS = {
        "plan", "agent", "ask", "coordinator",
        "session", "clear", "cost", "stats", "tools", "validate",
        "quit", "exit", "bye",
    }

    @on(Input.Submitted)
    async def intercept_at_source(self, event: Input.Submitted) -> None:
        value = event.value.strip()
        if not value.startswith("/"):
            return

        cmd_name = value.split()[0][1:].lower()
        if cmd_name not in self._THESEUS_CMDS:
            return

        event.stop()
        event.prevent_default()
        self.value = ""
        try:
            autocomplete = self.app.query_one("#autocomplete")
            autocomplete.display = False
        except Exception:
            pass
        # App의 _process_line에 위임 (슬래시 포함 원문 전달)
        asyncio.create_task(self.app._process_line(value))  # type: ignore[attr-defined]


# ──────────────────────────────────────────────────────────────────
# TheseusTUI
# ──────────────────────────────────────────────────────────────────

class TheseusTUI(App):
    """Theseus-native Textual TUI."""

    CSS = THESEUS_BASE_CSS + THESEUS_TUI_CSS
    BINDINGS = [
        Binding("ctrl+p", "switch_plan",        "Plan Mode"),
        Binding("ctrl+a", "switch_agent",       "Agent Mode"),
        Binding("ctrl+s", "switch_ask",         "Ask Mode"),
        Binding("ctrl+q", "quit_session",       "Quit"),
    ]

    def __init__(self, model: str = "gpt-4o", **kwargs):
        super().__init__(**kwargs)
        self._model = model
        self.theseus_sm   = TheseusStateMachine(initial_mode=AgentMode.AGENT)
        self.current_session = "default"
        self._busy        = False
        self._bundle: TheseusBundle | None = None
        self.auto_helper: AutocompleteHelper | None = None
        self._always_approve_tools: set[str] = set()  # approve_all 누적

        self.project_tool_permissions: dict = {
            "bash": 3, "read_file": 1, "write_file": 2, "edit_file": 2,
            "glob": 1, "grep": 1, "web_search": 1, "web_fetch": 1,
            "dummy_echo": 1, "create_tool": 2, "system_reboot": 5,
            "search_knowledge_base": 1, "ingest_document": 2,
        }
        self.user_level = 5
        self.actor_role = "ADMIN"  # standalone: 로컬 사용자 = ADMIN

    # ── 레이아웃 ────────────────────────────────────────────────

    def compose(self) -> ComposeResult:
        yield Header(show_clock=True)
        with Container(id="app-container"):
            with Horizontal(id="main-row"):
                with Vertical(id="transcript-column"):
                    yield RichLog(id="transcript", wrap=True, highlight=True, markup=True)
                    yield Static("", id="current-response")
                    yield OptionList(id="autocomplete")
                    yield TheseusInput(
                        placeholder="Ask Theseus or enter a /command",
                        id="composer",
                    )
                with Vertical(id="side-column"):
                    yield Static("Initializing…", id="status-bar")
                    yield Static("",              id="tasks-panel")
                    yield Static("",              id="tools-panel")
        yield Footer()

    # ── 초기화 ──────────────────────────────────────────────────

    async def on_mount(self) -> None:
        engine, full_registry = await setup_engine(
            sm=self.theseus_sm,
            user_level=self.user_level,
            project_tool_permissions=self.project_tool_permissions,
            permission_prompt_func=self._ask_permission,
            reset_stats=True,
        )

        self._bundle = TheseusBundle(
            engine=engine,
            tool_registry=full_registry,
            api_client=TheseusLLMClient(self._model),
        )
        self._bundle.app_state.model = self._model

        self.auto_helper = AutocompleteHelper(self._bundle)

        history = load_session_history(self.current_session)
        if history:
            engine._messages = history
            self._append_line(
                f"system> Loaded [bold]{len(history)}[/bold] messages "
                f"from session [bold]'{self.current_session}'[/bold]."
            )

        self._register_commands()
        self.query_one("#composer").focus()
        self._refresh_sidebars(force=True)
        self._append_line(
            "system> [bold green]Theseus Engine Initialized.[/bold green] "
            f"Mode: [bold]{self.theseus_sm.mode.value}[/bold] | "
            f"Role: [bold]{self.actor_role}[/bold] | "
            f"RBAC: Lv.{self.user_level}"
        )

    def _register_commands(self) -> None:
        cmds = [
            SlashCommand("plan",        "Switch to PLAN mode",        self._cmd_plan),
            SlashCommand("agent",       "Switch to AGENT mode",       self._cmd_agent),
            SlashCommand("ask",         "Switch to ASK mode",         self._cmd_ask),
            SlashCommand("coordinator", "Switch to COORDINATOR mode", self._cmd_coordinator),
            SlashCommand("session",     "Manage sessions",            self._cmd_session),
            SlashCommand("clear",       "Clear session history",      self._cmd_clear),
            SlashCommand("cost",        "Token usage & cost report",  self._cmd_cost),
            SlashCommand("stats",       "Tool execution statistics",  self._cmd_stats),
            SlashCommand("tools",       "List tools",                 self._cmd_tools),
            SlashCommand("validate",    "Validate a custom tool",     self._cmd_validate),
            SlashCommand("quit",        "Save session and quit",      self._cmd_quit),
            SlashCommand("exit",        "Save session and quit",      self._cmd_quit),
            SlashCommand("bye",         "Save session and quit",      self._cmd_quit),
        ]
        for cmd in cmds:
            self._bundle.commands.register(cmd)  # type: ignore[union-attr]

    # ── HITL 보안 승인 ──────────────────────────────────────────

    async def _ask_permission(self, tool_name: str, tool_input: dict) -> bool:
        """파괴적 툴 실행 전 모달로 사용자 승인을 요청합니다."""
        if tool_name in self._always_approve_tools:
            return True

        _DESTRUCTIVE = {"bash", "write_file", "edit_file", "system_reboot", "create_tool"}
        if tool_name not in _DESTRUCTIVE:
            return True

        result = await self.push_screen_wait(
            SecurityApprovalModal(tool_name, tool_input)
        )
        if result == "approve_all":
            self._always_approve_tools.add(tool_name)
            return True
        return result == "approve"

    # ── 비동기 에이전트 워커 ────────────────────────────────────

    async def _process_line(self, line: str) -> None:
        """Input 핸들러 → 워커 진입점."""
        if not line.strip() or self._bundle is None or self._busy:
            return
        self._busy = True
        composer = self.query_one("#composer", Input)
        composer.disabled = True

        try:
            await self._agent_worker(line)
        finally:
            self._busy = False
            composer.disabled = False
            composer.focus()

    async def _agent_worker(self, line: str) -> None:
        """CLI의 자율 복구 루프를 TUI에 이식한 비동기 워커.

        - 슬래시 커맨드 → CommandRegistry 디스패치
        - 일반 메시지  → engine.submit_message() 스트리밍
        - 툴 에러      → 내부 재시도 (auto-resume)
        - MaxTurnsExceeded → save_plan_state + WAIT_FOR_REVIEW 강등
        """
        assert self._bundle is not None

        # ── 슬래시 커맨드 처리 ────────────────────────────────
        if line.strip().startswith("/"):
            parts  = line.strip().split(None, 1)
            cmd    = parts[0][1:].lower()
            args   = parts[1] if len(parts) > 1 else ""
            result = await self._bundle.commands.dispatch(cmd, args)
            if result is None:
                await self._print_system(f"Unknown command: /{cmd}")
            elif result.message:
                await self._print_system(result.message)
                if result.exit_app:
                    self.exit()
            self._refresh_sidebars()
            return

        # ── 일반 메시지 스트리밍 ─────────────────────────────
        self._append_line(f"user> {line}")
        self._set_current_response("[dim]Working…[/dim]")

        max_auto_resume = 5
        auto_resume_count = 0
        current_line = line

        while True:
            accumulated_text = ""
            tool_called      = False
            tool_error       = False

            self._bundle.engine.set_system_prompt(
                self.theseus_sm.get_system_prompt()
            )

            model_name = getattr(self._bundle.engine, "_model", self._model)
            tags     = get_tracing_tags(self.user_level, model_name, self.current_session)
            metadata = get_tracing_metadata(self.user_level, model_name, self.current_session)

            try:
                with tracing_context(tags=tags, metadata=metadata):
                    async for event in self._bundle.engine.submit_message(current_line):
                        await self._render_event(event)
                        if isinstance(event, AssistantTextDelta):
                            accumulated_text += event.text
                        elif isinstance(event, ToolExecutionStarted):
                            tool_called = True
                        elif isinstance(event, ToolExecutionCompleted):
                            if event.is_error:
                                tool_error = True

            except MaxTurnsExceeded as exc:
                await self._print_system(
                    f"⚠️  최대 턴({exc.max_turns}) 도달 — 상태를 저장하고 WAIT_FOR_REVIEW로 전환합니다."
                )
                if self.theseus_sm.mode == AgentMode.PLAN:
                    save_plan_state("default", {
                        "phase": "Executing",
                        "plan_json": self.theseus_sm.plan,
                        "last_error": f"MaxTurnsExceeded({exc.max_turns})",
                    })
                    self.theseus_sm.set_plan_phase(PlanPhase.WAIT_FOR_REVIEW)
                    self._bundle.engine.set_system_prompt(self.theseus_sm.get_system_prompt())
                break

            except Exception as exc:
                await self._print_system(f"[bold red]ENGINE ERROR:[/bold red] {exc}")
                break

            # ── PLAN 단계 전환 ────────────────────────────────
            if self.theseus_sm.mode == AgentMode.PLAN:
                self._handle_plan_turn(accumulated_text)

            # ── Auto-Resume 판단 ──────────────────────────────
            should_resume = False
            resume_prompt = "Continue. Execute the next step immediately."

            if (
                self.theseus_sm.mode == AgentMode.PLAN
                and self.theseus_sm.plan_phase in (PlanPhase.EXECUTING, PlanPhase.VERIFYING)
            ):
                if tool_error:
                    should_resume = True
                    resume_prompt = "A tool error occurred. Analyze and retry."
                elif not tool_called:
                    should_resume = True

            elif self.theseus_sm.mode == AgentMode.AGENT and tool_error:
                should_resume = True
                resume_prompt = "A tool error occurred. Analyze the root cause and retry."

            if should_resume and auto_resume_count < max_auto_resume:
                auto_resume_count += 1
                current_line = resume_prompt
                await asyncio.sleep(0)
                continue

            break

        save_session_history(self.current_session, self._bundle.engine._messages)
        self._set_current_response("")
        self._refresh_sidebars()

    # ── PLAN 단계 전환 헬퍼 ─────────────────────────────────────

    def _handle_plan_turn(self, text: str) -> None:
        """PLAN 모드 단계별 상태 전환 처리."""
        from theseus_cli.parsers import extract_plan_json, handle_plan_draft

        phase = self.theseus_sm.plan_phase
        if phase == PlanPhase.DRAFTING:
            drafted = handle_plan_draft(self.theseus_sm, text)
            if drafted:
                self._bundle.engine.set_system_prompt(  # type: ignore[union-attr]
                    self.theseus_sm.get_system_prompt()
                )
                self._refresh_sidebars(force=True)
        elif phase == PlanPhase.EXECUTING:
            lower = text.lower()
            if any(kw in lower for kw in ("plan complete", "all steps complete", "execution complete")):
                self.theseus_sm.set_plan_phase(PlanPhase.VERIFYING)
                self._append_line("system> ✅ 실행 완료 — Verifying 단계로 전환합니다.")
                self._refresh_sidebars(force=True)

    # ── 슬래시 커맨드 핸들러 ────────────────────────────────────

    async def _cmd_plan(self, args: str, ctx: object) -> CommandResult:
        self.action_switch_plan()
        return CommandResult(message="Switched to PLAN mode.")

    async def _cmd_agent(self, args: str, ctx: object) -> CommandResult:
        self.action_switch_agent()
        return CommandResult(message="Switched to AGENT mode.")

    async def _cmd_ask(self, args: str, ctx: object) -> CommandResult:
        self.action_switch_ask()
        return CommandResult(message="Switched to ASK mode.")

    async def _cmd_coordinator(self, args: str, ctx: object) -> CommandResult:
        self.action_switch_coordinator()
        return CommandResult(message="Switched to COORDINATOR mode.")

    async def _cmd_clear(self, args: str, ctx: object) -> CommandResult:
        if self._bundle:
            self._bundle.engine._messages = []
        p = get_session_path(self.current_session)
        if p.exists():
            p.unlink()
        self._append_line(f"system> 🧹 Session [bold]'{self.current_session}'[/bold] cleared.")
        self._refresh_sidebars(force=True)
        return CommandResult(message="Session cleared.")

    async def _cmd_quit(self, args: str, ctx: object) -> CommandResult:
        """세션을 저장하고 TUI를 종료합니다."""
        if self._bundle:
            save_session_history(self.current_session, self._bundle.engine._messages)
        self._append_line("system> 👋 Goodbye! Session saved.")
        # call_after_refresh 로 한 프레임 뒤 종료 (마지막 메시지가 화면에 표시된 후)
        self.call_after_refresh(self.exit)
        return CommandResult()

    async def _cmd_session(self, args: str, ctx: object) -> CommandResult:
        parts = args.split()
        if not parts:
            return CommandResult(message="Usage: /session [list|new|switch] <name>")
        sub = parts[0].lower()
        if sub == "list":
            names = list_sessions()
            lines = "\n".join(
                f"  {'*' if n == self.current_session else ' '} {n}" for n in names
            )
            return CommandResult(message=f"Sessions:\n{lines}")
        if sub in ("new", "switch") and len(parts) >= 2:
            new_name = parts[1]
            if self._bundle:
                save_session_history(self.current_session, self._bundle.engine._messages)
                self.current_session = new_name
                self._bundle.engine._messages = load_session_history(new_name)
            self._append_line(f"system> Switched to session [bold]'{new_name}'[/bold].")
            self._refresh_sidebars(force=True)
            return CommandResult(message=f"Switched to {new_name}")
        return CommandResult(message="Unknown session subcommand.")

    async def _cmd_cost(self, args: str, ctx: object) -> CommandResult:
        from theseus_engine.engine.cost_tracker import CostTracker
        report = CostTracker.get_or_create().format_report()
        self._append_line(f"\n[bold cyan]💰 Cost Report[/bold cyan]\n{report}")
        return CommandResult()

    async def _cmd_stats(self, args: str, ctx: object) -> CommandResult:
        from theseus_engine.observability.stats import SessionStats
        report = SessionStats.get().format_report()
        self._append_line(f"\n[bold cyan]📊 Stats Report[/bold cyan]\n{report}")
        return CommandResult()

    async def _cmd_tools(self, args: str, ctx: object) -> CommandResult:
        if not self._bundle:
            return CommandResult(message="Engine not initialized.")
        sub = args.strip().lower() if args else "all"
        if sub in ("", "all"):
            lines = _format_tools_table(self._bundle.tool_registry)
        elif sub == "custom":
            lines = _format_custom_tools(self._bundle.tool_registry)
        else:
            lines = "Usage: /tools [all|custom]"
        self._append_line(f"\n{lines}")
        return CommandResult()

    async def _cmd_validate(self, args: str, ctx: object) -> CommandResult:
        if not args:
            return CommandResult(message="Usage: /validate <tool_name>")
        import os as _os
        from theseus_engine.tools.core.tool_factory import ToolValidator, CUSTOM_TOOLS_DIR
        tool_name = args.strip()
        file_path = _os.path.join(CUSTOM_TOOLS_DIR, f"{tool_name}.py")
        if not _os.path.exists(file_path):
            return CommandResult(message=f"[red]Tool file not found:[/red] {file_path}")
        with open(file_path, encoding="utf-8") as f:
            code = f.read()
        ok, msg = ToolValidator.validate_code(code)
        status = "✅ PASS" if ok else "❌ FAIL"
        self._append_line(f"\n[bold]Validation [{tool_name}][/bold] {status}\n{msg}")
        return CommandResult()

    # ── 모드 전환 액션 ──────────────────────────────────────────

    def action_switch_plan(self) -> None:
        if not self._bundle: return
        from theseus_engine.tools.core.tool_factory import build_filtered_registry
        self.theseus_sm.switch_mode(AgentMode.PLAN)
        self._bundle.engine.set_system_prompt(self.theseus_sm.get_system_prompt())
        self._bundle.engine._tool_registry = build_filtered_registry(
            self._bundle.tool_registry, self.project_tool_permissions, self.user_level, exclude_tools=set()
        )
        self._sync_permission_mode()
        self._append_line("system> Switched to [bold yellow]PLAN[/bold yellow] mode.")
        self._refresh_sidebars(force=True)

    def action_switch_agent(self) -> None:
        if not self._bundle: return
        from theseus_engine.tools.core.tool_factory import build_filtered_registry
        self.theseus_sm.switch_mode(AgentMode.AGENT)
        self._bundle.engine.set_system_prompt(self.theseus_sm.get_system_prompt())
        self._bundle.engine._tool_registry = build_filtered_registry(
            self._bundle.tool_registry, self.project_tool_permissions, self.user_level,
            exclude_tools={"create_tool"}
        )
        self._sync_permission_mode()
        self._append_line("system> Switched to [bold green]AGENT[/bold green] mode.")
        self._refresh_sidebars(force=True)

    def action_switch_ask(self) -> None:
        if not self._bundle: return
        from theseus_engine.tools.core.tool_factory import build_filtered_registry
        self.theseus_sm.switch_mode(AgentMode.ASK)
        self._bundle.engine.set_system_prompt(self.theseus_sm.get_system_prompt())
        all_names = {t.name for t in self._bundle.tool_registry.list_tools()}
        self._bundle.engine._tool_registry = build_filtered_registry(
            self._bundle.tool_registry, self.project_tool_permissions, self.user_level,
            exclude_tools=all_names
        )
        self._sync_permission_mode()
        self._append_line("system> Switched to [bold blue]ASK[/bold blue] mode.")
        self._refresh_sidebars(force=True)

    def action_switch_coordinator(self) -> None:
        if not self._bundle: return
        from theseus_engine.tools.core.tool_factory import build_filtered_registry
        self.theseus_sm.switch_mode(AgentMode.COORDINATOR)
        self._bundle.engine.set_system_prompt(self.theseus_sm.get_system_prompt())
        self._bundle.engine._tool_registry = build_filtered_registry(
            self._bundle.tool_registry, self.project_tool_permissions, self.user_level,
            exclude_tools={"create_tool"}
        )
        self._sync_permission_mode()
        self._append_line("system> Switched to [bold magenta]COORDINATOR[/bold magenta] mode.")
        self._refresh_sidebars(force=True)

    def action_quit_session(self) -> None:
        if self._bundle:
            save_session_history(self.current_session, self._bundle.engine._messages)
        self.exit()

    def _sync_permission_mode(self) -> None:
        if not self._bundle: return
        mapping = {
            AgentMode.AGENT:       PermissionMode.FULL_AUTO,
            AgentMode.PLAN:        PermissionMode.PLAN,
            AgentMode.ASK:         PermissionMode.DEFAULT,
            AgentMode.COORDINATOR: PermissionMode.FULL_AUTO,
        }
        target = mapping.get(self.theseus_sm.mode, PermissionMode.FULL_AUTO)
        checker = self._bundle.engine._permission_checker
        if hasattr(checker, "_settings"):
            checker._settings.mode = target
        self._bundle.app_state.permission_mode = target.value

    # ── UI 렌더링 헬퍼 ──────────────────────────────────────────

    def _append_line(self, text: str) -> None:
        try:
            self.query_one("#transcript", RichLog).write(text)
        except Exception:
            pass

    def _set_current_response(self, text: str) -> None:
        try:
            self.query_one("#current-response", Static).update(text)
        except Exception:
            pass

    async def _print_system(self, message: str) -> None:
        self._append_line(f"system> {message}")

    async def _render_event(self, event: object) -> None:
        if isinstance(event, AssistantTextDelta):
            self._set_current_response(event.text)
        elif isinstance(event, AssistantTurnComplete):
            full_text = getattr(event.message, "text", "") if event.message else ""
            if full_text:
                self._append_line(f"assistant> {full_text}")
            self._set_current_response("")
        elif isinstance(event, ToolExecutionStarted):
            self._append_line(f"[dim]🔧 {event.tool_name}({json.dumps(event.tool_input, ensure_ascii=False)[:80]})[/dim]")
        elif isinstance(event, ToolExecutionCompleted):
            icon = "❌" if event.is_error else "✅"
            self._append_line(f"[dim]{icon} {event.tool_name}: {event.output[:100]}[/dim]")
        elif isinstance(event, ErrorEvent):
            self._append_line(f"[bold red]ERROR:[/bold red] {event.message}")
        elif isinstance(event, StatusEvent):
            self._append_line(f"[dim italic]{event.message}[/dim italic]")
        elif isinstance(event, CompactProgressEvent):
            self._append_line(f"[dim]♻️  [{event.phase}] {event.message or ''}[/dim]")

    # ── 사이드바 동적 업데이트 ──────────────────────────────────

    def _refresh_sidebars(self, *, force: bool = False) -> None:
        if self._bundle is None:
            return

        state      = self._bundle.app_state.get()
        usage      = getattr(self._bundle.engine, "total_usage", None)
        tokens_str = (
            str(usage.total_tokens)
            if usage and getattr(usage, "total_tokens", 0) > 0
            else "N/A"
        )
        msgs = len(getattr(self._bundle.engine, "_messages", []))

        # ── 상태 바 ──────────────────────────────────────────
        mode_color = {
            AgentMode.AGENT:       "green",
            AgentMode.PLAN:        "yellow",
            AgentMode.ASK:         "blue",
            AgentMode.COORDINATOR: "magenta",
        }.get(self.theseus_sm.mode, "white")

        plan_phase_str = ""
        if self.theseus_sm.mode == AgentMode.PLAN:
            plan_phase_str = f"\n  phase     : {self.theseus_sm.plan_phase.name}"

        role_color = "bold cyan" if self.actor_role.upper() == "ADMIN" else "dim"
        status_lines = (
            "[b]● Status[/b]\n"
            f"  model     : {state.model}\n"
            f"  mode      : [{mode_color}]{self.theseus_sm.mode.value}[/{mode_color}]{plan_phase_str}\n"
            f"  role      : [{role_color}]{self.actor_role}[/{role_color}]\n"
            f"  RBAC      : Lv.{self.user_level}\n"
            f"  tokens    : {tokens_str}\n"
            f"  messages  : {msgs}\n"
            f"  session   : {self.current_session}"
        )
        try:
            self.query_one("#status-bar", Static).update(status_lines)
        except Exception:
            pass

        # ── PLAN 모드 사이드바: 태스크 체크리스트 ────────────
        if self.theseus_sm.mode == AgentMode.PLAN and self.theseus_sm.plan:
            tasks_text = _render_plan_tasks(self.theseus_sm.plan)
        else:
            tasks_text = ""

        try:
            self.query_one("#tasks-panel", Static).update(tasks_text)
        except Exception:
            pass

        # ── 커스텀 툴 목록 (AGENT 모드) ──────────────────────
        if self.theseus_sm.mode == AgentMode.AGENT:
            tools_text = _render_custom_tool_names(self._bundle.tool_registry)
        else:
            tools_text = ""

        try:
            self.query_one("#tools-panel", Static).update(tools_text)
        except Exception:
            pass

    # ── Input 이벤트 ─────────────────────────────────────────────

    @on(Input.Submitted, "#composer")
    async def handle_submitted(self, event: Input.Submitted) -> None:
        line = event.value.strip()
        if not line:
            return
        event.input.value = ""
        # 슬래시 커맨드는 TheseusInput.intercept_at_source가 처리
        # 그 외 일반 메시지만 여기서 처리
        if not line.startswith("/"):
            asyncio.create_task(self._process_line(line))

    def on_key(self, event: events.Key) -> None:
        if not self.focused or self.focused.id != "composer":
            return
        autocomplete = self.query_one("#autocomplete", OptionList)
        if event.key == "tab" and autocomplete.display:
            event.prevent_default()
            idx = autocomplete.highlighted if autocomplete.highlighted is not None else 0
            if autocomplete.option_count > 0:
                self._apply_suggestion(idx)
        elif event.key == "down" and autocomplete.display:
            event.prevent_default()
            autocomplete.highlighted = (
                ((autocomplete.highlighted + 1) % autocomplete.option_count)
                if autocomplete.highlighted is not None else 0
            )
        elif event.key == "up" and autocomplete.display:
            event.prevent_default()
            autocomplete.highlighted = (
                ((autocomplete.highlighted - 1) % autocomplete.option_count)
                if autocomplete.highlighted is not None
                else autocomplete.option_count - 1
            )

    @on(Input.Changed, "#composer")
    def handle_input_changed(self, event: Input.Changed) -> None:
        if self.auto_helper is None:
            return
        value       = event.value
        autocomplete = self.query_one("#autocomplete", OptionList)
        if value.startswith("/"):
            opts, _ = self.auto_helper.get_command_suggestions(value[1:])
        elif "@" in value:
            opts, _ = self.auto_helper.get_file_suggestions(value.split("@")[-1])
        else:
            opts = []
        if opts:
            autocomplete.clear_options()
            for opt in opts:
                autocomplete.add_option(opt)
            autocomplete.styles.display = "block"
        else:
            autocomplete.styles.display = "none"

    @on(OptionList.OptionSelected, "#autocomplete")
    def handle_suggestion_selected(self, event: OptionList.OptionSelected) -> None:
        self._apply_suggestion(event.option_index)

    def _apply_suggestion(self, index: int) -> None:
        autocomplete = self.query_one("#autocomplete", OptionList)
        if index < 0 or index >= autocomplete.option_count:
            return
        composer = self.query_one("#composer", Input)
        option_text = str(autocomplete.get_option_at_index(index).prompt)
        composer.value = self.auto_helper.process_selection(option_text, composer.value)  # type: ignore[union-attr]
        composer.cursor_position = len(composer.value)
        composer.focus()
        autocomplete.display = False


# ──────────────────────────────────────────────────────────────────
# 사이드바 렌더링 헬퍼 함수
# ──────────────────────────────────────────────────────────────────

def _render_plan_tasks(plan_json_str: str) -> str:
    """plan JSON에서 태스크 체크리스트를 렌더링합니다."""
    try:
        plan = json.loads(plan_json_str) if isinstance(plan_json_str, str) else plan_json_str
    except Exception:
        return ""
    tasks = plan.get("tasks", [])
    if not tasks:
        return ""
    lines = ["[b]📋 Plan Tasks[/b]"]
    _MARK = {"done": "✅", "running": "🔄", "failed": "❌", "pending": "⬜"}
    for t in tasks[:12]:  # 최대 12개
        status = t.get("status", "pending")
        mark   = _MARK.get(status, "⬜")
        tid    = t.get("id", "")
        title  = t.get("title", "")[:28]
        lines.append(f"  {mark} [{tid}] {title}")
    if len(tasks) > 12:
        lines.append(f"  … (+{len(tasks)-12} more)")
    return "\n".join(lines)


def _render_custom_tool_names(registry) -> str:
    """커스텀 툴 이름 목록을 사이드바용으로 렌더링합니다."""
    import os
    from theseus_engine.tools.core.tool_factory import CUSTOM_TOOLS_DIR

    if not os.path.isdir(CUSTOM_TOOLS_DIR):
        return ""
    custom = {f[:-3] for f in os.listdir(CUSTOM_TOOLS_DIR) if f.endswith(".py") and not f.startswith("_")}
    if not custom:
        return ""
    lines = ["[b]🔧 Custom Tools[/b]"]
    for name in sorted(custom)[:8]:
        lines.append(f"  • {name}")
    if len(custom) > 8:
        lines.append(f"  … (+{len(custom)-8} more)")
    return "\n".join(lines)


def _format_tools_table(registry) -> str:
    """전체 툴 목록 텍스트 테이블 (RichLog용)."""
    import os
    from theseus_engine.tools.core.tool_factory import CUSTOM_TOOLS_DIR

    custom = {f[:-3] for f in os.listdir(CUSTOM_TOOLS_DIR) if f.endswith(".py") and not f.startswith("_")} \
        if os.path.isdir(CUSTOM_TOOLS_DIR) else set()

    tools = registry.list_tools() if registry else []
    if not tools:
        return "[italic]등록된 툴이 없습니다.[/italic]"
    lines = [f"[bold cyan]🛠️  All Tools ({len(tools)})[/bold cyan]"]
    lines.append(f"{'이름':<24} {'구분'}")
    lines.append("─" * 36)
    for t in sorted(tools, key=lambda x: x.name):
        tag = "[yellow][custom][/yellow]" if t.name in custom else "[dim][core][/dim]  "
        lines.append(f"  {t.name:<22} {tag}")
    return "\n".join(lines)


def _format_custom_tools(registry) -> str:
    """커스텀 툴 상세 목록 텍스트 (RichLog용)."""
    import json as _json, os
    from theseus_engine.tools.core.tool_factory import CUSTOM_TOOLS_DIR

    if not os.path.isdir(CUSTOM_TOOLS_DIR):
        return "[italic]커스텀 툴 디렉토리가 없습니다.[/italic]"

    custom = [f[:-3] for f in sorted(os.listdir(CUSTOM_TOOLS_DIR)) if f.endswith(".py") and not f.startswith("_")]
    if not custom:
        return "[italic]등록된 커스텀 툴이 없습니다.[/italic]"

    lines = [f"[bold cyan]🔧 Custom Tools ({len(custom)})[/bold cyan]"]
    for mod in custom:
        meta_path = os.path.join(CUSTOM_TOOLS_DIR, f"{mod}.meta.json")
        meta: dict = {}
        if os.path.exists(meta_path):
            try:
                with open(meta_path, encoding="utf-8") as f:
                    meta = _json.load(f)
            except Exception:
                pass
        tool_name = meta.get("toolName", mod)
        perm      = meta.get("permissionLevel", 1)
        status    = "✅" if meta.get("isActive", True) else "⏸️"
        instance  = registry.get(tool_name) if registry else None
        desc      = (getattr(instance, "description", "") or "")[:50]
        lines.append(f"  {status} [bold]{tool_name}[/bold] [dim]Lv.{perm}[/dim]")
        if desc:
            lines.append(f"     [dim]{desc}[/dim]")
    return "\n".join(lines)


# ──────────────────────────────────────────────────────────────────
# 엔트리포인트
# ──────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    try:
        from dotenv import load_dotenv
        load_dotenv()
    except ImportError:
        pass

    model_name = os.getenv("OPENHARNESS_MODEL", "gpt-4o")
    TheseusTUI(model=model_name).run()
