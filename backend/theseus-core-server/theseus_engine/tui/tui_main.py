import os
import sys
import asyncio
from pathlib import Path

# Add project root and OpenHarness/src to sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))
sys.path.insert(0, str(PROJECT_ROOT / "OpenHarness" / "src"))

from textual.widgets import Static, RichLog, OptionList, Input, Header, Footer
from textual.containers import Horizontal, Vertical, Container
from textual import on, events

from openharness.ui.textual_app import OpenHarnessTerminalApp
from openharness.ui.runtime import build_runtime, start_runtime, handle_line
from openharness.engine.query import MaxTurnsExceeded
from openharness.commands.registry import SlashCommand, CommandResult

from theseus_engine.models.state import TheseusStateMachine, AgentMode
from theseus_engine.models.sessions import load_session_history, save_session_history, list_sessions, get_session_path
from theseus_engine.core.engine_builder import setup_engine
from theseus_engine.wrappers.llm_clients.theseus_client import TheseusLLMClient
print(f"\n[DEBUG] TheseusLLMClient loaded from: {TheseusLLMClient.__init__.__code__.co_filename}\n", file=sys.stderr)
from openharness.permissions.modes import PermissionMode
from theseus_engine.tools.core.tool_factory import build_filtered_registry

from theseus_engine.tui.autocomplete import AutocompleteHelper
from theseus_engine.tui.ui_components import THESEUS_TUI_CSS, THESEUS_BINDINGS
from theseus_engine.observability.tracer import tracing_context
from theseus_engine.core.engine_builder import (
    setup_engine, get_tracing_tags, get_tracing_metadata,
)

# --- Gemini thought_signature Monkey-Patch ---
# OpenHarness 코어를 수정하지 않고, 런타임에 OpenAICompatibleClient의
# _stream_once 를 Gemini thought_signature 처리 버전으로 교체합니다.
from theseus_engine.wrappers.llm_clients.gemini_patch import apply_gemini_patch
apply_gemini_patch()



class TheseusInput(Input):
    """오픈하네스(App)로 이벤트가 올라가기 전에, 가장 밑단 위젯에서
    Theseus 슬래시 커맨드 이벤트를 선제 차단(Intercept)하는 커스텀 입력창.

    Architecture:
        Textual의 이벤트 버블링 구조에서 Input.Submitted 이벤트는
        Widget → Container → ... → App 순으로 올라갑니다.
        TheseusTUI와 OpenHarnessTerminalApp 모두 App 레벨이므로
        App에서 event.stop()을 해도 Race Condition이 발생합니다.
        이 위젯은 이벤트가 App에 도달하기 전 Widget 레벨에서
        완벽히 차단하여 OpenHarness가 이벤트의 존재조차 모르게 합니다.
    """

    @on(Input.Submitted)
    async def intercept_at_source(
        self, event: Input.Submitted,
    ) -> None:
        """Theseus 전용 커맨드를 위젯 레벨에서 가로채 처리합니다."""
        value = event.value.strip()
        if not value.startswith("/"):
            # 일반 텍스트 대화는 건드리지 않고 위로(오픈하네스로) 흘려보냄
            return

        parts = value.split()
        cmd_name = parts[0][1:].lower()
        args = " ".join(parts[1:])

        theseus_cmds = {"plan", "agent", "ask", "session", "clear"}

        if cmd_name in theseus_cmds:
            # [핵심] 이벤트가 App(OpenHarness)으로 버블링되는 것을 완벽히 차단
            event.stop()
            event.prevent_default()

            # TheseusTUI(App) 인스턴스에 접근하여 핸들러를 다이렉트 실행
            app = self.app
            if cmd_name == "plan":
                await app._cmd_plan(args, None)
            elif cmd_name == "agent":
                await app._cmd_agent(args, None)
            elif cmd_name == "ask":
                await app._cmd_ask(args, None)
            elif cmd_name == "session":
                await app._cmd_session(args, None)
            elif cmd_name == "clear":
                await app._cmd_clear(args, None)

            # 입력창 비우기 및 자동완성 닫기
            self.value = ""
            try:
                autocomplete = app.query_one("#autocomplete")
                if autocomplete:
                    autocomplete.display = False
            except Exception:
                pass


class TheseusTUI(OpenHarnessTerminalApp):
    CSS = OpenHarnessTerminalApp.CSS + THESEUS_TUI_CSS
    BINDINGS = [*OpenHarnessTerminalApp.BINDINGS, *THESEUS_BINDINGS]

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.theseus_sm = TheseusStateMachine(initial_mode=AgentMode.AGENT)
        self.current_session = "default"
        
        self.project_tool_permissions = {
            "bash": 3, "read_file": 1, "write_file": 2, "edit_file": 2, 
            "glob": 1, "grep": 1, "web_search": 1, "web_fetch": 1,
            "dummy_echo": 1, "create_tool": 2, "system_reboot": 5,
            "search_knowledge_base": 1, "ingest_document": 2,
        }
        self.user_level = 5
        self.auto_helper = None

    def compose(self):
        yield Header(show_clock=True)
        with Container(id="app-container"):
            with Horizontal(id="main-row"):
                with Vertical(id="transcript-column"):
                    yield RichLog(id="transcript", wrap=True, highlight=True, markup=True)
                    yield Static("Ready.", id="current-response")
                    yield OptionList(id="autocomplete")
                    yield TheseusInput(placeholder="Ask Theseus or enter a /command", id="composer")
                with Vertical(id="side-column"):
                    yield Static("Starting...", id="status-bar")
                    yield Static("No tasks yet.", id="tasks-panel")
                    yield Static("No MCP servers configured.", id="mcp-panel")
        yield Footer()

    async def on_mount(self) -> None:
        client = TheseusLLMClient(self._config.model)
        
        self._bundle = await build_runtime(
            prompt=self._config.prompt,
            cwd=str(self.app.cwd) if hasattr(self.app, 'cwd') else str(Path.cwd()),
            model=client.model_name,
            max_turns=30,
            base_url=self._config.base_url,
            system_prompt=self.theseus_sm.get_system_prompt(),
            api_key=self._config.api_key,
            api_client=client,
            permission_prompt=self._ask_permission,
            ask_user_prompt=self._ask_question,
        )
        
        self.auto_helper = AutocompleteHelper(self._bundle)
        
        history = load_session_history(self.current_session)
        if history:
            self._bundle.engine.load_messages(history)
            self._append_line(f"system> Loaded {len(history)} messages from session [bold]'{self.current_session}'[/bold].")
        
        self._customize_runtime()
        await start_runtime(self._bundle)
        
        self.query_one("#composer").focus()
        self._refresh_sidebars(force=True)
        self._append_line(f"system> [bold green]Theseus Engine Initialized.[/bold green] Mode: [bold]{self.theseus_sm.mode.value}[/bold]")

        if self._config.prompt:
            self.call_later(lambda: asyncio.create_task(self._process_line(self._config.prompt or "")))

    def _customize_runtime(self):
        if not self._bundle: return
        
        # We reuse part of the engine_builder logic here conceptually, but inject directly into Textual bundle
        from theseus_engine.core.engine_builder import setup_engine
        engine, full_registry = setup_engine(self.theseus_sm, self.user_level, self.project_tool_permissions, self._ask_permission)
        
        # Replace bundle components with Theseus configured ones
        self._bundle.engine._permission_checker = engine._permission_checker
        self._bundle.tool_registry = full_registry
        self._bundle.engine._tool_registry = engine._tool_registry
        self._bundle.engine._tool_metadata = engine._tool_metadata
        self._bundle.engine._hook_executor = engine._hook_executor
        self._bundle.engine.set_system_prompt(self.theseus_sm.get_system_prompt())
        # Force inject TheseusLLMClient to prevent bypass
        actual_model = self._bundle.app_state.get().model
        theseus_client = TheseusLLMClient(actual_model)
        
        # 1. Update the engine's client
        self._bundle.engine.set_api_client(theseus_client)
        # 2. Update the bundle's client
        self._bundle.api_client = theseus_client
        # 3. Mark as external to prevent OpenHarness from overwriting it on refresh
        self._bundle.external_api_client = True
        
        self._append_line(f"system> [bold green]Force injected TheseusLLMClient[/bold green] (Model: {actual_model}, Type: {type(self._bundle.engine.api_client)})")
        print(f"\n[DEBUG] Final Engine Client Type: {type(self._bundle.engine._api_client)}\n", file=sys.stderr)
        
        # Synchronize initial PermissionMode
        self._sync_permission_mode()
        
        theseus_cmds = [
            SlashCommand(name="plan", description="Switch to Theseus PLAN mode", handler=self._cmd_plan),
            SlashCommand(name="agent", description="Switch to Theseus AGENT mode", handler=self._cmd_agent),
            SlashCommand(name="ask", description="Switch to Theseus ASK mode", handler=self._cmd_ask),
            SlashCommand(name="session", description="Manage sessions (/session [list|new|switch] [name])", handler=self._cmd_session),
            SlashCommand(name="clear", description="Clear session history", handler=self._cmd_clear),
        ]
        
        for cmd in theseus_cmds:
            self._bundle.commands._commands[cmd.name] = cmd
            if cmd.name in self._bundle.commands._canonical_names:
                self._bundle.commands._canonical_names.remove(cmd.name)
            self._bundle.commands._canonical_names.insert(0, cmd.name)
            
        self._append_line(f"system> [bold cyan]Registered {len(theseus_cmds)} Theseus slash commands.[/bold cyan]")

    async def _cmd_plan(self, args: str, context: object) -> object:
        self.action_switch_plan()
        return CommandResult(message="Switched to PLAN mode.")

    async def _cmd_agent(self, args: str, context: object) -> object:
        self.action_switch_agent()
        return CommandResult(message="Switched to AGENT mode.")

    async def _cmd_ask(self, args: str, context: object) -> object:
        self.action_switch_ask()
        return CommandResult(message="Switched to ASK mode.")

    async def _cmd_clear(self, args: str, context: object) -> object:
        self._bundle.engine.clear()
        session_path = get_session_path(self.current_session)
        if session_path.exists():
            session_path.unlink()
        self._append_line(f"system> 🧹 Session [bold]'{self.current_session}'[/bold] history cleared.")
        self._refresh_sidebars(force=True)
        return CommandResult(message="Session cleared.")

    async def _cmd_session(self, args: str, context: object) -> object:
        parts = args.split()
        if not parts:
            return CommandResult(message="Usage: /session [list|new|switch] [name]")
            
        sub_cmd = parts[0].lower()
        if sub_cmd == "list":
            sessions = list_sessions()
            msg = "Available sessions:\n" + "\n".join([f"- {name}" for name in sessions])
            return CommandResult(message=msg)
        elif sub_cmd in ("new", "switch"):
            if len(parts) < 2:
                return CommandResult(message=f"Usage: /session {sub_cmd} <session_name>")
            
            new_name = parts[1]
            save_session_history(self.current_session, self._bundle.engine.messages)
            
            self.current_session = new_name
            self._bundle.engine.load_messages(load_session_history(new_name))
            self._append_line(f"system> Switched to session [bold]'{new_name}'[/bold].")
            self._refresh_sidebars(force=True)
            return CommandResult(message=f"Switched to {new_name}")
        return CommandResult(message="Unknown session command.")

    def action_switch_plan(self) -> None:
        self.theseus_sm.switch_mode(AgentMode.PLAN)
        self._bundle.engine.set_system_prompt(self.theseus_sm.get_system_prompt())
        self._bundle.engine._tool_registry = build_filtered_registry(
            self._bundle.tool_registry, self.project_tool_permissions, 
            self.user_level, exclude_tools=set()
        )
        self._sync_permission_mode()
        self._append_line("system> Switched to [bold yellow]PLAN[/bold yellow] mode.")
        self._refresh_sidebars(force=True)

    def action_switch_agent(self) -> None:
        self.theseus_sm.switch_mode(AgentMode.AGENT)
        self._bundle.engine.set_system_prompt(self.theseus_sm.get_system_prompt())
        self._bundle.engine._tool_registry = build_filtered_registry(
            self._bundle.tool_registry, self.project_tool_permissions, 
            self.user_level, exclude_tools={"create_tool"}
        )
        self._sync_permission_mode()
        self._append_line("system> Switched to [bold green]AGENT[/bold green] mode.")
        self._refresh_sidebars(force=True)

    def action_switch_ask(self) -> None:
        self.theseus_sm.switch_mode(AgentMode.ASK)
        self._bundle.engine.set_system_prompt(self.theseus_sm.get_system_prompt())
        all_tool_names = {t.name for t in self._bundle.tool_registry.list_tools()}
        self._bundle.engine._tool_registry = build_filtered_registry(
            self._bundle.tool_registry, self.project_tool_permissions, 
            self.user_level, exclude_tools=all_tool_names
        )
        self._sync_permission_mode()
        self._append_line("system> Switched to [bold blue]ASK[/bold blue] mode.")
        self._refresh_sidebars(force=True)
        
    def _sync_permission_mode(self) -> None:
        if not self._bundle: return
        mode_mapping = {
            AgentMode.AGENT: PermissionMode.FULL_AUTO, # TheseusPermissionChecker handles our safety overrides
            AgentMode.PLAN: PermissionMode.PLAN,
            AgentMode.ASK: PermissionMode.DEFAULT,
        }
        target_mode = mode_mapping.get(self.theseus_sm.mode, PermissionMode.FULL_AUTO)
        self._bundle.engine._permission_checker._settings.mode = target_mode
        self._bundle.app_state.set(permission_mode=target_mode.value)

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
                parts = line.strip().split()
                cmd_name = parts[0][1:].lower()
                args = " ".join(parts[1:])

                theseus_cmd_handlers = {
                    "plan": self._cmd_plan,
                    "agent": self._cmd_agent,
                    "ask": self._cmd_ask,
                    "session": self._cmd_session,
                    "clear": self._cmd_clear,
                }

                if cmd_name in theseus_cmd_handlers:
                    result = await theseus_cmd_handlers[cmd_name](args, None)
                    if result and result.message:
                        await self._print_system(result.message)
                    self._refresh_sidebars()
                    return

                should_continue = await handle_line(
                    self._bundle, line, print_system=self._print_system,
                    render_event=self._render_event, clear_output=self._clear_transcript,
                )
                self._refresh_sidebars()
                if not should_continue:
                    self.exit()
                return

            self._bundle.engine.set_system_prompt(self.theseus_sm.get_system_prompt())

            model_name = getattr(self._bundle.engine, '_model', 'unknown')
            tags = get_tracing_tags(
                self.user_level, model_name,
                self.current_session,
            )
            metadata = get_tracing_metadata(
                self.user_level, model_name,
                self.current_session,
            )

            try:
                with tracing_context(
                    tags=tags, metadata=metadata,
                ):
                    async for event in self._bundle.engine.submit_message(line):
                        await self._render_event(event)
            except MaxTurnsExceeded as exc:
                await self._print_system(f"Stopped after {exc.max_turns} turns (max_turns).")

            save_session_history(self.current_session, self._bundle.engine.messages)
            self._refresh_sidebars()

        finally:
            self._busy = False
            composer.disabled = False
            composer.focus()

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
            autocomplete.highlighted = ((autocomplete.highlighted + 1) % autocomplete.option_count 
                if autocomplete.highlighted is not None else 0)
        elif event.key == "up" and autocomplete.display:
            event.prevent_default()
            autocomplete.highlighted = ((autocomplete.highlighted - 1) % autocomplete.option_count 
                if autocomplete.highlighted is not None else autocomplete.option_count - 1)

    @on(Input.Changed, "#composer")
    def handle_input_changed(self, event: Input.Changed) -> None:
        value = event.value
        autocomplete = self.query_one("#autocomplete", OptionList)

        if value.startswith("/"):
            opts, mode = self.auto_helper.get_command_suggestions(value[1:])
        elif "@" in value:
            opts, mode = self.auto_helper.get_file_suggestions(value.split("@")[-1])
        else:
            opts, mode = [], None

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
        if index < 0 or index >= autocomplete.option_count: return

        composer = self.query_one("#composer", Input)
        option_text = str(autocomplete.get_option_at_index(index).prompt)
        
        composer.value = self.auto_helper.process_selection(option_text, composer.value)
        composer.cursor_position = len(composer.value)
        composer.focus()
        autocomplete.display = False

    def action_quit_session(self) -> None:
        if self._bundle and hasattr(self._bundle.engine, "_messages"):
            save_session_history(self.current_session, self._bundle.engine._messages)
        self.exit()

    def _refresh_sidebars(self, *, force: bool = False) -> None:
        if self._bundle is None: return
        super()._refresh_sidebars(force=force)
        state = self._bundle.app_state.get()
        usage = self._bundle.engine.total_usage
        
        tokens_str = str(usage.total_tokens) if usage.total_tokens > 0 else "N/A"
        
        status_lines = [
            "[b]Status[/b]",
            f"model: {state.model}",
            f"permissions: RBAC (Lv.{self.user_level})",
            f"tokens: {tokens_str}",
            f"messages: {len(self._bundle.engine.messages)}",
            "",
            "[b]Theseus Context[/b]",
            f"mode: [bold]{self.theseus_sm.mode.value}[/bold]",
            f"user_level: {self.user_level}",
            f"session: {getattr(self, 'current_session', 'default')}"
        ]
        self.query_one("#status-bar", Static).update("\n".join(status_lines))

if __name__ == "__main__":
    try:
        from dotenv import load_dotenv
        load_dotenv()
    except ImportError:
        pass

    model_name = os.getenv("OPENHARNESS_MODEL", "gpt-4o")
    
    app = TheseusTUI(model=model_name)
    app.run()
