import os
import sys
import asyncio
from pathlib import Path

# Add project root to sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from textual.app import App, ComposeResult
from textual.widgets import Static, RichLog, OptionList, Input, Header, Footer
from textual.containers import Horizontal, Vertical, Container
from textual.binding import Binding
from textual import on, events

from theseus_engine.models.state import TheseusStateMachine, AgentMode, CoordinatorPhase
from theseus_engine.models.sessions import (
    load_session_history, save_session_history,
    list_sessions, get_session_path,
)
from theseus_engine.core.engine_builder import setup_engine, get_tracing_tags, get_tracing_metadata
from theseus_engine.wrappers.llm_clients.theseus_client import TheseusLLMClient
from theseus_engine.models.rbac import PermissionMode
from theseus_engine.tools.core.tool_factory import build_filtered_registry
from theseus_engine.engine.query_engine import MaxTurnsExceeded
from theseus_engine.engine.stream_events import (
    AssistantTextDelta, AssistantTurnComplete,
    ToolExecutionStarted, ToolExecutionCompleted,
    ErrorEvent, StatusEvent, CompactProgressEvent,
)
from theseus_engine.tui.autocomplete import AutocompleteHelper
from theseus_engine.tui.ui_components import THESEUS_TUI_CSS, THESEUS_BINDINGS
from theseus_engine.tui.commands import SlashCommand, CommandResult, CommandRegistry
from theseus_engine.tui.runtime import TheseusBundle, build_theseus_runtime, start_theseus_runtime
from theseus_engine.observability.tracer import tracing_context

print(
    f"\n[DEBUG] TheseusLLMClient loaded from: {TheseusLLMClient.__init__.__code__.co_filename}\n",
    file=sys.stderr,
)

# ──────────────────────────────────────────────────────────
# CSS & 기본 설정
# ──────────────────────────────────────────────────────────

THESEUS_BASE_CSS = """
Screen { padding: 0; }
#app-container { width: 100%; height: 100%; }
#main-row { height: 100%; }
#transcript-column { width: 1fr; height: 100%; }
#side-column {
    width: 35; height: 100%;
    border-left: vkey $accent;
    padding: 0 1;
}
#transcript { height: 1fr; }
#current-response { height: 3; border: solid $accent; padding: 0 1; }
#autocomplete {
    display: none; max-height: 8;
    border: solid $accent; background: $panel; margin: 0 1;
}
#autocomplete > .option-list--option-highlighted {
    background: $accent !important;
    color: $surface !important;
    text-style: bold reverse !important;
}
#autocomplete > .option-list--option-hover { background: $accent 50%; }
"""


# ──────────────────────────────────────────────────────────
# 커스텀 Input (슬래시 커맨드 인터셉트)
# ──────────────────────────────────────────────────────────

class TheseusInput(Input):
    """Theseus 슬래시 커맨드를 위젯 레벨에서 선제 차단하는 커스텀 Input."""

    @on(Input.Submitted)
    async def intercept_at_source(self, event: Input.Submitted) -> None:
        value = event.value.strip()
        if not value.startswith("/"):
            return  # 일반 텍스트는 그대로 앱으로 흘려보냄

        parts = value.split()
        cmd_name = parts[0][1:].lower()
        args = " ".join(parts[1:])

        theseus_cmds = {"plan", "agent", "ask", "coordinator", "session", "clear"}
        if cmd_name not in theseus_cmds:
            return

        event.stop()
        event.prevent_default()

        app: TheseusTUI = self.app  # type: ignore[assignment]
        handlers = {
            "plan": app._cmd_plan,
            "agent": app._cmd_agent,
            "ask": app._cmd_ask,
            "coordinator": app._cmd_coordinator,
            "session": app._cmd_session,
            "clear": app._cmd_clear,
        }
        await handlers[cmd_name](args, None)

        self.value = ""
        try:
            autocomplete = app.query_one("#autocomplete")
            if autocomplete:
                autocomplete.display = False
        except Exception:
            pass


# ──────────────────────────────────────────────────────────
# 메인 TUI App
# ──────────────────────────────────────────────────────────

class TheseusTUI(App):
    """Theseus-native Textual TUI — OpenHarness 의존 없음."""

    CSS = THESEUS_BASE_CSS + THESEUS_TUI_CSS
    BINDINGS = [
        Binding("ctrl+p", "switch_plan", "Plan Mode"),
        Binding("ctrl+a", "switch_agent", "Agent Mode"),
        Binding("ctrl+s", "switch_ask", "Ask Mode"),
        Binding("ctrl+c", "quit_session", "Quit"),
        *THESEUS_BINDINGS,
    ]

    def __init__(self, model: str = "gpt-4o", **kwargs):
        super().__init__(**kwargs)
        self._model = model
        self.theseus_sm = TheseusStateMachine(initial_mode=AgentMode.AGENT)
        self.current_session = "default"
        self._busy = False
        self._bundle: TheseusBundle | None = None
        self.auto_helper: AutocompleteHelper | None = None

        self.project_tool_permissions: dict = {
            "bash": 3, "read_file": 1, "write_file": 2, "edit_file": 2,
            "glob": 1, "grep": 1, "web_search": 1, "web_fetch": 1,
            "dummy_echo": 1, "create_tool": 2, "system_reboot": 5,
            "search_knowledge_base": 1, "ingest_document": 2,
        }
        self.user_level = 5

    # ── 레이아웃 ────────────────────────────────────────────

    def compose(self) -> ComposeResult:
        yield Header(show_clock=True)
        with Container(id="app-container"):
            with Horizontal(id="main-row"):
                with Vertical(id="transcript-column"):
                    yield RichLog(id="transcript", wrap=True, highlight=True, markup=True)
                    yield Static("Ready.", id="current-response")
                    yield OptionList(id="autocomplete")
                    yield TheseusInput(
                        placeholder="Ask Theseus or enter a /command",
                        id="composer",
                    )
                with Vertical(id="side-column"):
                    yield Static("Starting...", id="status-bar")
                    yield Static("No tasks yet.", id="tasks-panel")
                    yield Static("No MCP servers configured.", id="mcp-panel")
        yield Footer()

    # ── 초기화 ──────────────────────────────────────────────

    async def on_mount(self) -> None:
        api_client = TheseusLLMClient(self._model)

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
            api_client=api_client,
        )
        self._bundle.app_state.model = self._model

        self.auto_helper = AutocompleteHelper(self._bundle)

        # 세션 복원
        history = load_session_history(self.current_session)
        if history:
            engine._messages = history
            self._append_line(
                f"system> Loaded {len(history)} messages from session "
                f"[bold]'{self.current_session}'[/bold]."
            )

        # 커맨드 등록
        self._register_commands()

        await start_theseus_runtime(self._bundle)

        self.query_one("#composer").focus()
        self._refresh_sidebars(force=True)
        self._append_line(
            f"system> [bold green]Theseus Engine Initialized.[/bold green] "
            f"Mode: [bold]{self.theseus_sm.mode.value}[/bold]"
        )

    def _register_commands(self) -> None:
        registry = self._bundle.commands  # type: ignore[union-attr]
        cmds = [
            SlashCommand("plan", "Switch to PLAN mode", self._cmd_plan),
            SlashCommand("agent", "Switch to AGENT mode", self._cmd_agent),
            SlashCommand("ask", "Switch to ASK mode", self._cmd_ask),
            SlashCommand("coordinator", "Switch to COORDINATOR mode", self._cmd_coordinator),
            SlashCommand("session", "Manage sessions", self._cmd_session),
            SlashCommand("clear", "Clear session history", self._cmd_clear),
        ]
        for cmd in cmds:
            registry.register(cmd)
        self._append_line(
            f"system> [bold cyan]Registered {len(cmds)} Theseus slash commands.[/bold cyan]"
        )

    # ── 슬래시 커맨드 핸들러 ────────────────────────────────

    async def _cmd_plan(self, args: str, context: object) -> CommandResult:
        self.action_switch_plan()
        return CommandResult(message="Switched to PLAN mode.")

    async def _cmd_agent(self, args: str, context: object) -> CommandResult:
        self.action_switch_agent()
        return CommandResult(message="Switched to AGENT mode.")

    async def _cmd_ask(self, args: str, context: object) -> CommandResult:
        self.action_switch_ask()
        return CommandResult(message="Switched to ASK mode.")

    async def _cmd_coordinator(self, args: str, context: object) -> CommandResult:
        self.action_switch_coordinator()
        return CommandResult(message="Switched to COORDINATOR mode.")

    async def _cmd_clear(self, args: str, context: object) -> CommandResult:
        if self._bundle:
            self._bundle.engine._messages = []
        session_path = get_session_path(self.current_session)
        if session_path.exists():
            session_path.unlink()
        self._append_line(
            f"system> 🧹 Session [bold]'{self.current_session}'[/bold] history cleared."
        )
        self._refresh_sidebars(force=True)
        return CommandResult(message="Session cleared.")

    async def _cmd_session(self, args: str, context: object) -> CommandResult:
        parts = args.split()
        if not parts:
            return CommandResult(message="Usage: /session [list|new|switch] [name]")

        sub = parts[0].lower()
        if sub == "list":
            sessions = list_sessions()
            msg = "Available sessions:\n" + "\n".join(f"- {n}" for n in sessions)
            return CommandResult(message=msg)

        if sub in ("new", "switch"):
            if len(parts) < 2:
                return CommandResult(message=f"Usage: /session {sub} <session_name>")
            new_name = parts[1]
            if self._bundle:
                save_session_history(self.current_session, self._bundle.engine._messages)
                self.current_session = new_name
                self._bundle.engine._messages = load_session_history(new_name)
            self._append_line(f"system> Switched to session [bold]'{new_name}'[/bold].")
            self._refresh_sidebars(force=True)
            return CommandResult(message=f"Switched to {new_name}")

        return CommandResult(message="Unknown session command.")

    # ── 모드 전환 액션 ──────────────────────────────────────

    def action_switch_plan(self) -> None:
        if not self._bundle:
            return
        self.theseus_sm.switch_mode(AgentMode.PLAN)
        self._bundle.engine.set_system_prompt(self.theseus_sm.get_system_prompt())
        self._bundle.engine._tool_registry = build_filtered_registry(
            self._bundle.tool_registry, self.project_tool_permissions,
            self.user_level, exclude_tools=set(),
        )
        self._sync_permission_mode()
        self._append_line("system> Switched to [bold yellow]PLAN[/bold yellow] mode.")
        self._refresh_sidebars(force=True)

    def action_switch_agent(self) -> None:
        if not self._bundle:
            return
        self.theseus_sm.switch_mode(AgentMode.AGENT)
        self._bundle.engine.set_system_prompt(self.theseus_sm.get_system_prompt())
        self._bundle.engine._tool_registry = build_filtered_registry(
            self._bundle.tool_registry, self.project_tool_permissions,
            self.user_level, exclude_tools={"create_tool"},
        )
        self._sync_permission_mode()
        self._append_line("system> Switched to [bold green]AGENT[/bold green] mode.")
        self._refresh_sidebars(force=True)

    def action_switch_ask(self) -> None:
        if not self._bundle:
            return
        self.theseus_sm.switch_mode(AgentMode.ASK)
        self._bundle.engine.set_system_prompt(self.theseus_sm.get_system_prompt())
        all_names = {t.name for t in self._bundle.tool_registry.list_tools()}
        self._bundle.engine._tool_registry = build_filtered_registry(
            self._bundle.tool_registry, self.project_tool_permissions,
            self.user_level, exclude_tools=all_names,
        )
        self._sync_permission_mode()
        self._append_line("system> Switched to [bold blue]ASK[/bold blue] mode.")
        self._refresh_sidebars(force=True)

    def action_switch_coordinator(self) -> None:
        if not self._bundle:
            return
        self.theseus_sm.switch_mode(AgentMode.COORDINATOR)
        self._bundle.engine.set_system_prompt(self.theseus_sm.get_system_prompt())
        self._bundle.engine._tool_registry = build_filtered_registry(
            self._bundle.tool_registry, self.project_tool_permissions,
            self.user_level, exclude_tools={"create_tool"},
        )
        self._sync_permission_mode()
        self._append_line("system> Switched to [bold magenta]COORDINATOR[/bold magenta] mode.")
        self._refresh_sidebars(force=True)

    def action_quit_session(self) -> None:
        if self._bundle:
            save_session_history(self.current_session, self._bundle.engine._messages)
        self.exit()

    # ── 권한 동기화 ─────────────────────────────────────────

    def _sync_permission_mode(self) -> None:
        if not self._bundle:
            return
        mode_map = {
            AgentMode.AGENT: PermissionMode.FULL_AUTO,
            AgentMode.PLAN: PermissionMode.PLAN,
            AgentMode.ASK: PermissionMode.DEFAULT,
            AgentMode.COORDINATOR: PermissionMode.FULL_AUTO,
        }
        target = mode_map.get(self.theseus_sm.mode, PermissionMode.FULL_AUTO)
        checker = self._bundle.engine._permission_checker
        if hasattr(checker, "_settings"):
            checker._settings.mode = target
        self._bundle.app_state.permission_mode = target.value

    # ── 메시지 처리 루프 ────────────────────────────────────

    async def _process_line(self, line: str) -> None:
        if not line.strip() or self._bundle is None or self._busy:
            return

        self._busy = True
        composer = self.query_one("#composer", Input)
        composer.disabled = True
        self._append_line(f"user> {line}")
        self._set_current_response("[dim]Working...[/dim]")

        try:
            if line.strip().startswith("/"):
                parts = line.strip().split(None, 1)
                cmd_name = parts[0][1:].lower()
                args = parts[1] if len(parts) > 1 else ""

                result = await self._bundle.commands.dispatch(cmd_name, args)
                if result is None:
                    await self._print_system(f"Unknown command: /{cmd_name}")
                elif result.message:
                    await self._print_system(result.message)
                    if result.exit_app:
                        self.exit()
                self._refresh_sidebars()
                return

            # 일반 메시지
            self._bundle.engine.set_system_prompt(self.theseus_sm.get_system_prompt())

            model_name = getattr(self._bundle.engine, "_model", "unknown")
            tags = get_tracing_tags(self.user_level, model_name, self.current_session)
            metadata = get_tracing_metadata(self.user_level, model_name, self.current_session)

            try:
                with tracing_context(tags=tags, metadata=metadata):
                    async for event in self._bundle.engine.submit_message(line):
                        await self._render_event(event)
            except MaxTurnsExceeded as exc:
                await self._print_system(f"Stopped after {exc.max_turns} turns (max_turns).")

            save_session_history(self.current_session, self._bundle.engine._messages)
            self._refresh_sidebars()

        finally:
            self._busy = False
            composer.disabled = False
            composer.focus()

    # ── 권한 프롬프트 (HITL) ────────────────────────────────

    async def _ask_permission(self, tool_name: str, tool_input: dict) -> bool:
        """Permission prompt — 기본값 자동 승인. 필요 시 Textual 다이얼로그로 교체."""
        return True

    # ── UI 헬퍼 ─────────────────────────────────────────────

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

    def _clear_transcript(self) -> None:
        try:
            self.query_one("#transcript", RichLog).clear()
        except Exception:
            pass

    async def _render_event(self, event: object) -> None:
        if isinstance(event, AssistantTextDelta):
            self._set_current_response(event.text)
        elif isinstance(event, AssistantTurnComplete):
            if event.message:
                # message는 ConversationMessage; .text 프로퍼티로 full text 추출
                full_text = getattr(event.message, "text", str(event.message))
                self._append_line(f"assistant> {full_text}")
            self._set_current_response("")
        elif isinstance(event, ToolExecutionStarted):
            self._append_line(
                f"[dim]🔧 {event.tool_name}({event.tool_input})[/dim]"
            )
        elif isinstance(event, ToolExecutionCompleted):
            status = "❌" if event.is_error else "✅"
            self._append_line(
                f"[dim]{status} {event.tool_name}: {event.output[:120]}[/dim]"
            )
        elif isinstance(event, ErrorEvent):
            self._append_line(f"[bold red]ERROR:[/bold red] {event.message}")
        elif isinstance(event, StatusEvent):
            self._append_line(f"[dim italic]{event.message}[/dim italic]")
        elif isinstance(event, CompactProgressEvent):
            self._append_line(
                f"[dim]♻️  compact [{event.phase}] {event.message or ''}[/dim]"
            )

    def _refresh_sidebars(self, *, force: bool = False) -> None:
        if self._bundle is None:
            return
        state = self._bundle.app_state.get()

        usage = getattr(self._bundle.engine, "total_usage", None)
        tokens_str = (
            str(usage.total_tokens)
            if usage and getattr(usage, "total_tokens", 0) > 0
            else "N/A"
        )
        messages_count = len(getattr(self._bundle.engine, "_messages", []))

        status_lines = [
            "[b]Status[/b]",
            f"model: {state.model}",
            f"permissions: RBAC (Lv.{self.user_level})",
            f"tokens: {tokens_str}",
            f"messages: {messages_count}",
            "",
            "[b]Theseus Context[/b]",
            f"mode: [bold]{self.theseus_sm.mode.value}[/bold]",
            f"user_level: {self.user_level}",
            f"session: {self.current_session}",
        ]
        try:
            self.query_one("#status-bar", Static).update("\n".join(status_lines))
        except Exception:
            pass

    # ── Input 이벤트 ─────────────────────────────────────────

    @on(Input.Submitted, "#composer")
    async def handle_submitted(self, event: Input.Submitted) -> None:
        line = event.value.strip()
        if not line:
            return
        event.input.value = ""
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
                if autocomplete.highlighted is not None
                else 0
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
        value = event.value
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


# ──────────────────────────────────────────────────────────
# 엔트리포인트
# ──────────────────────────────────────────────────────────

if __name__ == "__main__":
    try:
        from dotenv import load_dotenv
        load_dotenv()
    except ImportError:
        pass

    model_name = os.getenv("OPENHARNESS_MODEL", "gpt-4o")
    app = TheseusTUI(model=model_name)
    app.run()
