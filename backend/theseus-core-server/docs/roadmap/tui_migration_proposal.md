# Theseus TUI(Textual) 기반 사용자 인터페이스 전환 및 고도화 제안

**작성일**: 2026-04-27
**작성자**: Theseus AI Agent (UX/UI Engineering)
**대상**: Theseus 프로젝트 인터페이스 고도화 로드맵

---

## 1. 개요: CLI를 넘어 상용 수준의 TUI로 (Why Textual?)

현재 `theseus_engine/app.py`는 세션 관리와 슬래시 명령어 등 견고한 로직을 갖추고 있으나, 단순 터미널 `input()` 기반의 인터페이스는 스트리밍 중 화면 멈춤, 멀티라인 렌더링의 한계, 그리고 권한 승인 시 흐름 단절 등의 문제를 안고 있습니다.

이를 해결하기 위해 파이썬 기반의 강력한 TUI 프레임워크인 **Textual**로 마이그레이션하여, 에이전트와의 상호작용을 풍부하게(Rich) 만들고 시스템의 상태를 실시간으로 시각화하는 것을 제안합니다.

---

## 2. 🔍 OpenHarness 내장 UI 자산 분석 결과 (재활용 가능 자원)

OpenHarness 코드베이스를 분석한 결과, **이미 상용 수준의 Textual TUI 앱과 관련 인프라가 완벽하게 구현**되어 있음을 확인했습니다. 밑바닥부터 개발할 필요 없이, 이 자산들을 Theseus 맥락에 맞게 래핑하여 활용하는 것이 가장 효율적인 전략입니다.

### 2.1. 핵심 재활용 모듈 목록

| 모듈 경로 | 핵심 클래스/함수 | 역할 | Theseus 활용 방안 |
|:---|:---|:---|:---|
| `ui/textual_app.py` | `OpenHarnessTerminalApp` | **완성된 Textual TUI 앱**: 3-Column 레이아웃 (채팅, 사이드바), 실시간 상태, 키바인딩 | Theseus의 TUI 앱의 **부모 클래스 또는 참조 모델(Reference)** |
| `ui/textual_app.py` | `PermissionScreen` | **모달 기반 권한 승인 팝업**: Allow/Deny 버튼, 키보드 단축키(`y`/`n`/`esc`) 지원 | `custom_permission_prompt` **즉시 교체 가능** |
| `ui/textual_app.py` | `QuestionScreen` | **모달 기반 사용자 질문 팝업**: 텍스트 입력 필드 + Submit/Cancel 버튼 | 에이전트가 추가 정보 필요 시 사용하는 `ask_user_question` 도구의 UI |
| `ui/runtime.py` | `RuntimeBundle`, `build_runtime()`, `handle_line()` | **엔진 초기화/라인 처리/세션 저장의 공식 런타임 관리자** | 현재 `app.py`의 수동 엔진 초기화를 `build_runtime()` 한 줄로 대체 |
| `ui/output.py` | `OutputRenderer` | **Rich 기반 포매터**: Markdown 렌더링, Syntax Highlighting, Spinner, Panel 출력 | 에이전트 응답의 **시각적 품질을 즉시 끌어올리는** 핵심 컴포넌트 |
| `themes/builtin.py` | `BUILTIN_THEMES` | 5종 빌트인 테마 (default, dark, minimal, cyberpunk, solarized) | Theseus TUI에 **테마 시스템 즉시 이식** |
| `themes/schema.py` | `ThemeConfig` | 색상, 보더, 아이콘, 레이아웃을 Pydantic으로 관리하는 테마 스키마 | 커스텀 Theseus 테마 작성 시 그대로 사용 |
| `keybindings/` | `load_keybindings()`, `default_bindings.py` | `Ctrl+L` (대화 초기화), `Ctrl+D` (종료) 등 커스텀 키바인딩 시스템 | Theseus 전용 단축키(예: `Ctrl+P` → Plan 모드 전환) 추가 가능 |
| `output_styles/` | `OutputStyleLoader` | 출력 스타일(detailed/compact/json) 동적 전환 | 사용자 선호에 따른 출력 밀도 조절 |
| `frontend/terminal/` | React/Ink 기반 TUI | Node.js 기반의 최신 프론트엔드 앱 (Vite 번들러) | 장기적으로 React TUI로 전환 시 참조 |
| `autopilot-dashboard/` | React 대시보드 앱 | 웹 기반 관리/모니터링 대시보드 (Vite + React) | B2B 웹 관리 콘솔로 확장 시 참조 |

### 2.2. 가장 중요한 발견: `PermissionScreen` & `QuestionScreen`

TUI 제안서에서 가장 큰 난관으로 지목했던 **`custom_permission_prompt`의 모달 전환 문제**가 OpenHarness에 이미 완벽하게 해결되어 있습니다.

```python
# OpenHarness/src/openharness/ui/textual_app.py (Lines 45-84)

class PermissionScreen(ModalScreen[bool]):
    """Simple approval modal for mutating tools."""
    BINDINGS = [
        Binding("escape", "deny", "Deny"),
        Binding("y", "allow", "Allow"),
        Binding("n", "deny", "Deny"),
    ]

    def __init__(self, tool_name: str, reason: str) -> None:
        super().__init__()
        self._tool_name = tool_name
        self._reason = reason

    def compose(self) -> ComposeResult:
        yield Container(
            Static(Panel.fit(
                f"Allow tool [bold]{self._tool_name}[/bold]?\n\n{self._reason}",
                title="Permission Required",
            )),
            Horizontal(
                Button("Allow", id="allow", variant="success"),
                Button("Deny", id="deny", variant="error"),
                classes="permission-actions",
            ),
            id="permission-dialog",
        )

    @on(Button.Pressed)
    def handle_button_press(self, event: Button.Pressed) -> None:
        self.dismiss(event.button.id == "allow")
```

**이 코드를 그대로 임포트하거나 상속하면, `asyncio.to_thread(input)` 기반의 위험한 코드를 즉시 삭제할 수 있습니다.**

### 2.3. `RuntimeBundle`을 활용한 엔진 초기화 단순화

현재 `app.py`에서 수십 줄에 걸쳐 수행하는 엔진 초기화를 `build_runtime()` 한 줄로 대체할 수 있습니다.

```python
# 현재 app.py (약 50줄의 초기화 로직)
api_client = OpenAICompatibleClient(...)
full_registry = create_default_tool_registry()
engine = QueryEngine(api_client=..., tool_registry=..., ...)

# OpenHarness runtime.py 활용 시 (3줄로 단축)
from openharness.ui.runtime import build_runtime, start_runtime, handle_line

bundle = await build_runtime(
    model=model_name, api_key=api_key,
    permission_prompt=self._ask_permission,  # PermissionScreen 연결
    ask_user_prompt=self._ask_question,      # QuestionScreen 연결
)
await start_runtime(bundle)
```

**단, Theseus의 RBAC 필터링(`build_filtered_registry`)과 커스텀 도구(`ToolCreatorTool`) 주입은 `build_runtime()` 이후 별도로 수행해야 합니다.**

---

## 3. 🏗️ 구체화된 리팩토링 전략 (3단계)

### Phase 1: 최소 전환 (Minimal Viable TUI)

OpenHarness의 `OpenHarnessTerminalApp`을 상속하여 Theseus 전용 TUI를 구축합니다.

```python
from openharness.ui.textual_app import (
    OpenHarnessTerminalApp, PermissionScreen, QuestionScreen
)
from openharness.ui.runtime import build_runtime, start_runtime
from theseus_engine.state import TheseusStateMachine, AgentMode

class TheseusTUI(OpenHarnessTerminalApp):
    """Theseus B2B Agent TUI — OpenHarness TUI를 상속하여 확장."""

    BINDINGS = [
        *OpenHarnessTerminalApp.BINDINGS,
        Binding("ctrl+p", "switch_plan", "Plan Mode"),
        Binding("ctrl+a", "switch_agent", "Agent Mode"),
    ]

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._sm = TheseusStateMachine(initial_mode=AgentMode.AGENT)

    async def on_mount(self) -> None:
        await super().on_mount()
        # Phase 1: 기본 TUI 기동 후 Theseus 확장 주입
        self._inject_theseus_tools()
        self._update_status_bar()

    def _inject_theseus_tools(self):
        """RBAC 필터링 및 커스텀 도구를 런타임에 주입."""
        if self._bundle is None:
            return
        # Theseus ToolCreatorTool 등록
        from theseus_engine.tool_factory import ToolCreatorTool
        self._bundle.tool_registry.register(ToolCreatorTool())
        # RBAC 필터링 적용...

    def action_switch_plan(self) -> None:
        self._sm.switch_mode(AgentMode.PLAN)
        self._append_line("system> Switched to PLAN mode.")

    def action_switch_agent(self) -> None:
        self._sm.switch_mode(AgentMode.AGENT)
        self._append_line("system> Switched to AGENT mode.")
```

### Phase 2: 사이드바 확장 (Theseus 전용 패널)

OpenHarness의 3-Column 레이아웃(`#side-column`)을 오버라이드하여 Theseus 전용 패널을 추가합니다.

| 패널 | 표시 정보 | 원본 위젯 |
|:---|:---|:---|
| `#status-bar` (확장) | 모델, 토큰, **현재 AgentMode**, **PlanPhase**, RBAC 레벨 | `Static` |
| `#tasks-panel` (재활용) | 백그라운드 태스크 진행률 | `Static` |
| `#theseus-tools` (신규) | 현재 세션에 로드된 도구 목록 및 권한 레벨 | `Static` |
| `#plan-view` (신규) | Plan 모드의 `PlanBlock` 트리 (체크박스 승인) | `Tree` |

### Phase 3: 테마 및 출력 고도화

`OutputRenderer`와 `BUILTIN_THEMES`를 통합하여 Theseus 전용 테마를 추가합니다.

```python
from openharness.themes.schema import ThemeConfig, ColorsConfig, BorderConfig, IconConfig, LayoutConfig

THESEUS_THEME = ThemeConfig(
    name="theseus",
    colors=ColorsConfig(
        primary="#4fc3f7",    # Theseus 브랜드 블루
        secondary="#81c784",  # 성공/승인 그린
        accent="#ffb74d",     # 경고 오렌지
        error="#ef5350",      # 에러 레드
        muted="#546e7a",
        background="#1a2332", # 딥 네이비
        foreground="#eceff1",
    ),
    borders=BorderConfig(style="rounded"),
    icons=IconConfig(spinner="⠋", tool="🛠", error="🚨", success="✅", agent="🧠"),
    layout=LayoutConfig(compact=False, show_tokens=True, show_time=True),
)
```

---

## 4. 🎯 확장 기능 로드맵 (UX Enhancements)

단순 채팅창을 넘어 B2B 플랫폼으로서 갖추어야 할 기능입니다.

1. **사이드바 세션 매니저**: `/session list` → 사이드바에서 클릭 전환. OpenHarness의 `SessionBackend`과 연동.
2. **@ 파일 선택기**: 에이전트가 참고할 파일을 `@` 입력 시 자동 완성. OpenHarness의 `glob` 도구와 연계.
3. **대시보드 모드**: 토큰 소모량, 실행 중인 도구의 리소스 사용량, RBAC 권한 레벨을 상시 표시. (`OutputRenderer.print_status_line()` 활용)
4. **Plan 시각화**: `PlanBlock`들을 `Tree` 위젯으로 표시하고 각 항목별 체크박스로 승인 여부 결정.
5. **React TUI 장기 전환**: OpenHarness의 `frontend/terminal/` (React/Ink 기반)으로의 점진적 전환도 로드맵에 포함.
6. **웹 관리 콘솔**: `autopilot-dashboard/` (React + Vite)를 참조하여 B2B 관리자용 웹 대시보드 구축.

---

## 5. ⚠️ 주의사항 및 의존성

### 5.1. OpenHarness 직접 상속 시 리스크
- `OpenHarnessTerminalApp`은 `build_runtime()`에서 MCP 매니저, Hook 시스템 등 Theseus가 아직 사용하지 않는 모듈들을 자동 초기화합니다.
- **권장**: Phase 1에서는 직접 상속보다 **`PermissionScreen`, `QuestionScreen`, `OutputRenderer`만 선택적으로 임포트**하여 사용하고, 엔진 초기화는 현재 `app.py`의 커스텀 로직을 유지합니다.

### 5.2. 추가 의존성
```
textual>=0.50.0
rich>=13.0.0
prompt-toolkit>=3.0.0  # permission_dialog.py 의존
```

### 5.3. 현재 app.py에서 즉시 적용 가능한 Quick Win
`OutputRenderer`는 Textual 없이도 단독으로 사용 가능합니다. 현재 CLI 환경에서도 즉시 적용하여 출력 품질을 올릴 수 있습니다.

```python
from openharness.ui.output import OutputRenderer

renderer = OutputRenderer(style_name="default")
# 기존: print(event.text, end="", flush=True)
# 변경: renderer.render_event(event)
```

---

## 6. 결론 및 행동 강령

OpenHarness에 이미 상용 수준의 TUI 인프라가 구축되어 있으므로, **밑바닥부터 만드는 것은 오버엔지니어링**입니다.

| 우선순위 | 작업 | 소요 시간 (예상) |
|:---:|:---|:---:|
| **1** | `OutputRenderer` 즉시 적용 (Quick Win, CLI 품질 향상) | 1시간 |
| **2** | `PermissionScreen` + `QuestionScreen` 임포트하여 `custom_permission_prompt` 교체 | 2시간 |
| **3** | `OpenHarnessTerminalApp` 상속 기반의 `TheseusTUI` 스켈레톤 구축 | 반나절 |
| **4** | Theseus 전용 사이드바 패널 및 테마 추가 | 1일 |
| **5** | Plan 시각화 (`Tree` 위젯) 및 세션 사이드바 | 2일 |
