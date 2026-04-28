import os
import sys
import asyncio
from pathlib import Path
from typing import Optional

# Add project root and OpenHarness/src to sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))
sys.path.insert(0, str(PROJECT_ROOT / "OpenHarness" / "src"))



from textual.binding import Binding
from textual.widgets import Static, RichLog, OptionList, Input, Header, Footer
from textual.containers import Horizontal, Vertical, Container
from textual import on, work, events
from textual.app import ComposeResult

# OpenHarness imports
from openharness.ui.textual_app import OpenHarnessTerminalApp, PermissionScreen, QuestionScreen
from openharness.ui.runtime import build_runtime, start_runtime, handle_line
from openharness.engine.stream_events import (
    AssistantTextDelta,
    ToolExecutionStarted,
    ToolExecutionCompleted,
    ErrorEvent
)

# Theseus imports
from theseus_engine.monkey_patches import apply_patches
from theseus_engine.state import TheseusStateMachine, AgentMode
from theseus_engine.tool_factory import (
    ToolCreatorTool, build_filtered_registry, load_custom_tools
)
from theseus_engine.tools import DummyTool, SystemRebootTool
from theseus_engine.rbac import TheseusPermissionChecker
from theseus_engine.sessions import (
    load_session_history, save_session_history, list_sessions, get_session_path
)
from openharness.config.settings import PermissionSettings
from openharness.commands.registry import SlashCommand, CommandResult, CommandContext
from openharness.engine.query import MaxTurnsExceeded

class TheseusTUI(OpenHarnessTerminalApp):
    """
    Theseus B2B AI Agent TUI.
    Inherits from OpenHarnessTerminalApp to leverage the production-grade TUI infrastructure
    while injecting Theseus-specific RBAC, Mode switching, and Meta-tooling.
    """

    CSS = OpenHarnessTerminalApp.CSS + """
    /* 화면 전체 정렬 속성 제거 (헤더 짤림 방지) */
    Screen {
        padding: 0;
    }
    
    #app-container {
        width: 100%;
        height: 100%;
    }

    #main-row {
        height: 100%;
    }
    
    #transcript-column {
        width: 1fr;
        height: 100%;
    }

    #side-column {
        width: 35;
        height: 100%;
        border-left: vkey $accent;
        padding: 0 1;
    }

    /* 자동완성 드롭다운 전체 창 */
    #autocomplete {
        display: none;
        max-height: 8;
        border: solid $accent;
        background: $panel;
        margin: 0 1;
    }
    
    /* ✅ 수정됨: item -> option 으로 변경하고 reverse 속성 추가 */
    #autocomplete > .option-list--option-highlighted {
        background: $accent !important;
        color: $surface !important; /* 글자색을 대비되게 변경 */
        text-style: bold reverse !important; /* 터미널 색상을 강제 반전시켜 무조건 보이게 만듦 */
    }
    
    /* ✅ 마우스 오버 시 효과도 option으로 수정 */
    #autocomplete > .option-list--option-hover {
        background: $accent 50%;
    }
    """

    BINDINGS = [
        *OpenHarnessTerminalApp.BINDINGS,
        Binding("ctrl+p", "switch_plan", "Plan Mode"),
        Binding("ctrl+a", "switch_agent", "Agent Mode"),
        Binding("ctrl+s", "switch_ask", "Ask Mode"),
        Binding("ctrl+c", "quit_session", "Quit"),
    ]

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        # Initialize Theseus State Machine
        self.theseus_sm = TheseusStateMachine(initial_mode=AgentMode.AGENT)
        self.current_session = "default"
        
        # Project specific configurations
        self.project_tool_permissions = {
            "bash": 3, "read_file": 1, "write_file": 2, "edit_file": 2, 
            "glob": 1, "grep": 1, "web_search": 1, "web_fetch": 1,
            "dummy_echo": 1, "create_tool": 2, "system_reboot": 5,
        }
        self.user_level = 5
        self._suggestion_mode = None # None, "command", "file"

    def compose(self) -> ComposeResult:
        """UI 레이아웃 구성 오버라이드"""
        yield Header(show_clock=True)
        with Container(id="app-container"):
            with Horizontal(id="main-row"):
                with Vertical(id="transcript-column"):
                    yield RichLog(id="transcript", wrap=True, highlight=True, markup=True)
                    yield Static("Ready.", id="current-response")
                    yield OptionList(id="autocomplete")
                    yield Input(placeholder="Ask Theseus or enter a /command", id="composer")
                with Vertical(id="side-column"):
                    yield Static("Starting...", id="status-bar")
                    yield Static("No tasks yet.", id="tasks-panel")
                    yield Static("No MCP servers configured.", id="mcp-panel")
        yield Footer()

    async def on_mount(self) -> None:
        """
        Overriding on_mount to inject Theseus-specific logic after runtime is built.
        """
        # 1. Apply OpenHarness/Theseus monkey patches
        apply_patches()
        
        # 2. Build the standard OpenHarness runtime
        self._bundle = await build_runtime(
            prompt=self._config.prompt,
            cwd=str(self.app.cwd) if hasattr(self.app, 'cwd') else str(Path.cwd()),
            model=self._config.model,
            max_turns=30,  # app.py와 동일하게 설정
            base_url=self._config.base_url,
            system_prompt=self.theseus_sm.get_system_prompt(),
            api_key=self._config.api_key,
            api_client=self._config.api_client,
            permission_prompt=self._ask_permission,
            ask_user_prompt=self._ask_question,
        )
        
        # 4. Load Session History
        history = load_session_history(self.current_session)
        if history:
            self._bundle.engine.load_messages(history)
            self._append_line(f"system> Loaded {len(history)} messages from session [bold]'{self.current_session}'[/bold].")
        
        # 5. UI Setup & Command Injection
        self._customize_runtime()
        
        # 6. Start the runtime hooks
        await start_runtime(self._bundle)
        
        # 6. UI Setup
        self.query_one("#composer").focus()
        self._refresh_sidebars(force=True)
        self._append_line(f"system> [bold green]Theseus Engine Initialized.[/bold green] Mode: [bold]{self.theseus_sm.mode.value}[/bold]")

        if self._config.prompt:
            self.call_later(lambda: asyncio.create_task(self._process_line(self._config.prompt or "")))

    def _customize_runtime(self):
        """
        Injects Theseus specific tools, RBAC, and system prompts into the bundle.
        """
        if not self._bundle:
            return
            
        # Register Theseus specific tools
        self._bundle.tool_registry.register(DummyTool())
        self._bundle.tool_registry.register(SystemRebootTool())
        self._bundle.tool_registry.register(ToolCreatorTool())
        
        # Setup Theseus Permission Checker
        settings = PermissionSettings()
        self.theseus_permission_checker = TheseusPermissionChecker(
            settings, self.user_level, self.project_tool_permissions
        )
        
        # Override the engine's permission checker with Theseus RBAC
        self._bundle.engine.permission_checker = self.theseus_permission_checker
        
        # Filter the registry based on user level (Default AGENT mode)
        self._bundle.engine._tool_registry = build_filtered_registry(
            self._bundle.tool_registry, 
            self.project_tool_permissions, 
            self.user_level, 
            exclude_tools={"create_tool"}
        )
        
        # Set the initial system prompt from Theseus state machine
        self._bundle.engine.set_system_prompt(self.theseus_sm.get_system_prompt())
        
        # 1. Theseus 명령어 정의
        from openharness.commands.registry import SlashCommand
        theseus_cmds = [
            SlashCommand(name="plan", description="Switch to Theseus PLAN mode", handler=self._cmd_plan),
            SlashCommand(name="agent", description="Switch to Theseus AGENT mode", handler=self._cmd_agent),
            SlashCommand(name="ask", description="Switch to Theseus ASK mode", handler=self._cmd_ask),
            SlashCommand(name="session", description="Manage sessions (/session [list|new|switch] [name])", handler=self._cmd_session),
            SlashCommand(name="clear", description="Clear session history", handler=self._cmd_clear),
        ]
        
        # 2. 원본 레지스트리 내부 딕셔너리에 조용히 덮어쓰기 (자동완성 UI 노출용)
        for cmd in theseus_cmds:
            self._bundle.commands._commands[cmd.name] = cmd
            if cmd.name in self._bundle.commands._canonical_names:
                self._bundle.commands._canonical_names.remove(cmd.name)
            self._bundle.commands._canonical_names.insert(0, cmd.name)
            
        self._append_line(f"system> [bold cyan]Registered {len(theseus_cmds)} Theseus slash commands.[/bold cyan]")

        # Inject metadata for ToolCreatorTool etc.
        self._bundle.engine.tool_metadata.update({
            "tool_registry": self._bundle.tool_registry,
            "tool_permissions": self.project_tool_permissions,
        })

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
            # Save current
            save_session_history(self.current_session, self._bundle.engine.messages)
            
            # Switch
            self.current_session = new_name
            self._bundle.engine.load_messages(load_session_history(new_name))
            self._append_line(f"system> Switched to session [bold]'{new_name}'[/bold].")
            self._refresh_sidebars(force=True)
            return CommandResult(message=f"Switched to {new_name}")
        return CommandResult(message="Unknown session command.")

    def action_switch_plan(self) -> None:
        """Switch to PLAN mode."""
        self.theseus_sm.switch_mode(AgentMode.PLAN)
        self._bundle.engine.set_system_prompt(self.theseus_sm.get_system_prompt())
        
        # Plan 모드: 모든 툴 허용 (메타 툴링 포함)
        self._bundle.engine._tool_registry = build_filtered_registry(
            self._bundle.tool_registry, self.project_tool_permissions, 
            self.user_level, exclude_tools=set()
        )
        
        self._append_line("system> Switched to [bold yellow]PLAN[/bold yellow] mode.")
        self._refresh_sidebars(force=True)

    def action_switch_agent(self) -> None:
        """Switch to AGENT mode."""
        self.theseus_sm.switch_mode(AgentMode.AGENT)
        self._bundle.engine.set_system_prompt(self.theseus_sm.get_system_prompt())
        
        # Agent 모드: create_tool 차단
        self._bundle.engine._tool_registry = build_filtered_registry(
            self._bundle.tool_registry, self.project_tool_permissions, 
            self.user_level, exclude_tools={"create_tool"}
        )
        
        self._append_line("system> Switched to [bold green]AGENT[/bold green] mode.")
        self._refresh_sidebars(force=True)

    def action_switch_ask(self) -> None:
        """Switch to ASK mode."""
        self.theseus_sm.switch_mode(AgentMode.ASK)
        self._bundle.engine.set_system_prompt(self.theseus_sm.get_system_prompt())
        
        # Ask 모드: 모든 툴 차단 (Read-only)
        all_tool_names = {t.name for t in self._bundle.tool_registry.list_tools()}
        self._bundle.engine._tool_registry = build_filtered_registry(
            self._bundle.tool_registry, self.project_tool_permissions, 
            self.user_level, exclude_tools=all_tool_names
        )
        
        self._append_line("system> Switched to [bold blue]ASK[/bold blue] mode.")
        self._refresh_sidebars(force=True)

    # -----------------------------------------------------------------------
    # 핵심 오버라이드: 부모 클래스의 _process_line을 완전히 대체합니다.
    # 이것이 OpenHarness가 시스템 프롬프트를 덮어쓰는 것을 막는 유일한 방법입니다.
    # -----------------------------------------------------------------------
    async def _process_line(self, line: str) -> None:
        """부모 클래스의 _process_line을 오버라이드하여 Theseus 파이프라인을 적용합니다.

        OpenHarness의 handle_line()은 매 턴마다 build_runtime_system_prompt()를
        호출하여 시스템 프롬프트를 'You are OpenHarness...'로 리셋합니다.
        이 오버라이드는 그 경로를 완전히 우회합니다.
        """
        if not line.strip() or self._bundle is None or self._busy:
            return

        self._busy = True
        composer = self.query_one("#composer", Input)
        composer.disabled = True
        self._append_line(f"user> {line}")
        self._set_current_response("[dim]Working...[/dim]")

        try:
            # --- 1단계: Theseus 슬래시 명령어 직접 디스패치 ---
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
                    # Theseus 명령어: 레지스트리를 거치지 않고 직접 실행
                    result = await theseus_cmd_handlers[cmd_name](args, None)
                    if result and result.message:
                        await self._print_system(result.message)
                    self._refresh_sidebars()
                    return

                # OpenHarness 내장 명령어: handle_line에 위임 (시스템 프롬프트에 영향 없음)
                should_continue = await handle_line(
                    self._bundle,
                    line,
                    print_system=self._print_system,
                    render_event=self._render_event,
                    clear_output=self._clear_transcript,
                )
                self._refresh_sidebars()
                if not should_continue:
                    self.exit()
                return

            # --- 2단계: 일반 메시지 → Theseus 시스템 프롬프트 적용 후 직접 전송 ---
            # [핵심] handle_line()을 우회하여 OpenHarness가 프롬프트를 덮어쓰지 못하게 합니다.
            self._bundle.engine.set_system_prompt(
                self.theseus_sm.get_system_prompt()
            )

            try:
                async for event in self._bundle.engine.submit_message(line):
                    await self._render_event(event)
            except MaxTurnsExceeded as exc:
                await self._print_system(
                    f"Stopped after {exc.max_turns} turns (max_turns)."
                )

            # 세션 히스토리 자동 저장
            save_session_history(
                self.current_session,
                self._bundle.engine.messages,
            )
            self._refresh_sidebars()

        finally:
            self._busy = False
            composer.disabled = False
            composer.focus()

    def on_key(self, event: events.Key) -> None:
        """앱 전역 키 이벤트 처리"""
        # 입력창(composer)에 포커스가 있을 때만 처리
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
                (autocomplete.highlighted + 1) % autocomplete.option_count 
                if autocomplete.highlighted is not None else 0
            )
        elif event.key == "up" and autocomplete.display:
            event.prevent_default()
            autocomplete.highlighted = (
                (autocomplete.highlighted - 1) % autocomplete.option_count 
                if autocomplete.highlighted is not None else autocomplete.option_count - 1
            )


    @on(Input.Changed, "#composer")
    def handle_input_changed(self, event: Input.Changed) -> None:
        """사용자 입력 변화에 따른 자동완성 처리"""
        value = event.value
        autocomplete = self.query_one("#autocomplete", OptionList)

        if value.startswith("/"):
            self._show_command_suggestions(value[1:])
        elif "@" in value:
            # @ 이후의 텍스트 추출 (가장 마지막 @ 기준)
            parts = value.split("@")
            self._show_file_suggestions(parts[-1])
        else:
            autocomplete.display = False
            self._suggestion_mode = None

    def _show_command_suggestions(self, filter_text: str):
        """슬래시 명령어 제안 표시 (Theseus 명령어 우선 정렬)"""
        if not self._bundle: return
        
        autocomplete = self.query_one("#autocomplete", OptionList)
        commands = self._bundle.commands.list_commands()
        
        # 1. 입력된 텍스트로 필터링
        filtered = [cmd for cmd in commands if cmd.name.startswith(filter_text)]
        
        # 2. Theseus 핵심 명령어 우선순위 지정
        theseus_priority = {"plan", "agent", "ask", "session", "clear"}
        
        # 3. 정렬 로직: 테세우스 명령어면 앞으로(0), 아니면 뒤로(1) 보낸 후 알파벳 정렬
        filtered.sort(key=lambda cmd: (0 if cmd.name in theseus_priority else 1, cmd.name))
        
        if filtered:
            autocomplete.clear_options()
            for cmd in filtered:
                prefix = "✨ " if cmd.name in theseus_priority else "  "
                # 테세우스 명령어인 경우 강제로 우리 설명(Description)이 나오도록 한 번 더 검증
                desc = cmd.description
                if cmd.name == "plan" and "Switch to Theseus" not in desc:
                    desc = "Switch to Theseus PLAN mode"
                elif cmd.name == "agent" and "Switch to Theseus" not in desc:
                    desc = "Switch to Theseus AGENT mode"
                
                autocomplete.add_option(f"{prefix}/{cmd.name} - {desc}")
            autocomplete.styles.display = "block"
            self._suggestion_mode = "command"
        else:
            autocomplete.styles.display = "none"

    def _show_file_suggestions(self, filter_text: str):
        """파일 및 폴더 제안 표시 (@)"""
        autocomplete = self.query_one("#autocomplete", OptionList)
        cwd = Path.cwd()
        
        # 입력된 경로 파싱 (예: "theseus_engine/t" -> dirname="theseus_engine", basename="t")
        if "/" in filter_text:
            dirname, basename = filter_text.rsplit("/", 1)
            search_dir = cwd / dirname
        else:
            dirname, basename = "", filter_text
            search_dir = cwd

        # 유효하지 않은 경로나 접근 제한된 폴더 제외
        if not search_dir.exists() or not search_dir.is_dir():
            autocomplete.display = False
            return

        try:
            # 해당 디렉토리 내 파일 및 폴더 목록 추출
            entries = []
            for p in search_dir.iterdir():
                if p.name.startswith(basename):
                    # .git, __pycache__ 등 제외
                    if p.name.startswith(".") or p.name == "__pycache__":
                        continue
                    
                    rel_path = str(p.relative_to(cwd)).replace("\\", "/")
                    if p.is_dir():
                        entries.append(f"@{rel_path}/") # 폴더는 / 추가
                    else:
                        entries.append(f"@{rel_path}")
            
            # 정렬 (폴더 우선)
            entries.sort(key=lambda x: (not x.endswith("/"), x))
        except Exception:
            entries = []
            
        if entries:
            autocomplete.clear_options()
            for entry in entries[:30]:
                autocomplete.add_option(entry)
            autocomplete.display = True
            self._suggestion_mode = "file"
        else:
            autocomplete.display = False

    @on(OptionList.OptionSelected, "#autocomplete")
    def handle_suggestion_selected(self, event: OptionList.OptionSelected) -> None:
        """마우스 클릭이나 엔터로 제안 선택 시"""
        self._apply_suggestion(event.option_index)

    def _apply_suggestion(self, index: int) -> None:
        """실제 선택된 제안을 입력창에 적용"""
        autocomplete = self.query_one("#autocomplete", OptionList)
        if index < 0 or index >= autocomplete.option_count:
            return

        composer = self.query_one("#composer", Input)
        option = autocomplete.get_option_at_index(index)
        option_text = str(option.prompt)
        
        if self._suggestion_mode == "command":
            # "✨ /plan - ..." 형식에서 명령어만 추출
            clean_text = option_text.replace("✨", "").strip()
            cmd_name = clean_text.split(" ")[0]
            composer.value = cmd_name + " "
        elif self._suggestion_mode == "file":
            parts = composer.value.split("@")
            # 선택된 경로가 폴더로 끝나면 공백 없이 /만 유지하여 계속 입력 유도
            replacement = option_text[1:]
            suffix = "" if replacement.endswith("/") else " "
            parts[-1] = replacement
            composer.value = "@".join(parts) + suffix
        
        # 커서를 문장 마지막으로 이동
        composer.cursor_position = len(composer.value)
        composer.focus()
        autocomplete.display = False
        self._suggestion_mode = None

    def action_quit_session(self) -> None:
        """앱 종료 및 세션 저장"""
        if self._bundle and hasattr(self._bundle.engine, "_messages"):
            save_session_history(self.current_session, self._bundle.engine._messages)
        self.exit()

    def _refresh_sidebars(self, *, force: bool = False) -> None:
        """
        Override sidebar refresh to include Theseus-specific state.
        """
        if self._bundle is None:
            return
            
        # Call parent refresh to update tasks/mcp panels
        super()._refresh_sidebars(force=force)
        
        # Manually update status bar to include Theseus-specific fields
        state = self._bundle.app_state.get()
        usage = self._bundle.engine.total_usage
        
        status_lines = [
            "[b]Status[/b]",
            f"model: {state.model}",
            f"permissions: {state.permission_mode}",
            f"tokens: {usage.total_tokens}",
            f"messages: {len(self._bundle.engine.messages)}",
            "",
            "[b]Theseus Context[/b]",
            f"mode: [bold]{self.theseus_sm.mode.value}[/bold]",
            f"user_level: {self.user_level}",
            f"session: {getattr(self, 'current_session', 'default')}"
        ]
        
        self.query_one("#status-bar", Static).update("\n".join(status_lines))

if __name__ == "__main__":
    # Ensure environment variables are loaded
    try:
        from dotenv import load_dotenv
        load_dotenv()
    except ImportError:
        pass

    api_key = os.getenv("OPENAI_API_KEY") or os.getenv("GEMINI_API_KEY")
    model_name = os.getenv("OPENHARNESS_MODEL", "gpt-4o")
    
    app = TheseusTUI(
        model=model_name,
        api_key=api_key
    )
    app.run()
