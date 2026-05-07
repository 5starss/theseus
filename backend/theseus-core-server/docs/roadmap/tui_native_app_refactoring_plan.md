# 독자적 Theseus TUI (Native Textual App) 아키텍처 재설계 및 구현 로드맵

본 문서는 기존 OpenHarness의 `OpenHarnessTerminalApp` 상속(Wrapping) 구조를 폐기하고, 순수 Textual 기반의 **독자적인 Theseus TUI**를 구축하기 위한 아키텍처 전환 가이드라인입니다. 

이를 통해 CLI(`theseus_cli.py`)에 적용된 최신 자율성/안정성 로직을 UI 블로킹 없이 완벽하게 이식하고, 향후 다중 에이전트 확장(Phase 6)에 대비한 유연한 프론트엔드 기반을 마련합니다.

---

## 1. 개요 및 필요성

현재 `tui_main.py`는 OpenHarness의 UI 계층에 강하게 결합되어 있어, 이벤트 버블링 차단을 위한 우회 코드(`TheseusInput` 등)나 런타임 몽키패칭(`_customize_runtime`)이 필수적이었습니다.

이 로드맵은 CLI에서 검증된 자율 복구(Auto-Resume) 루프, 예외 메모리 주입, 그리고 세련된 보안 승인(HITL) 모달 등을 TUI에 안정적으로 통합하기 위해 **OpenHarness UI와의 결합을 끊고 독자적인 Textual App으로 독립**하는 것을 목표로 합니다.

---

## 2. 주요 아키텍처 변경 계획

### 2.1 코어 애플리케이션 구조 분리

기존의 억지스러운 이벤트 가로채기와 동적 런타임 수정을 제거하고, 순수 Textual 애플리케이션으로 재시작합니다.

*   **상속 구조 변경**: `class TheseusTUI(OpenHarnessTerminalApp)` → `class TheseusTUI(App)`로 변경.
*   **엔진 초기화 직결**: `on_mount`에서 OpenHarness의 `build_runtime` 대신, CLI와 동일하게 `engine_builder.py`의 `setup_engine`을 직접 호출하여 `QueryEngine` 인스턴스를 소유합니다.
*   **레이아웃 명시적 정의**: `compose()` 메서드를 통해 `Header`, `Horizontal(RichLog, Sidebar)`, `Input`, `Footer` 등의 UI 배치를 명시적으로 제어합니다.

### 2.2 비동기 워커 기반 에이전트 루프 (Auto-Resume 이식)

UI 프리징 현상을 방지하고 CLI의 **자율 복구(Self-correction) 루프**를 이식하기 위해 비동기 백그라운드 태스크 패턴을 도입합니다.

*   **Input 핸들러 (`@on(Input.Submitted)`)**: 
    *   입력값을 받아 `RichLog`에 `user>`로 출력한 후 Input을 비활성화(disabled).
    *   `asyncio.create_task(self._agent_worker(user_text))` 호출로 백그라운드에서 에이전트 실행을 위임합니다.
*   **`_agent_worker(self, line: str)` 신규 코루틴**:
    *   CLI의 `while True:` 루프 로직을 그대로 구현합니다.
    *   **자율 복구**: `tool_error_occurred` 감지 시 내부적으로 재시도 라인(`"방금 에러가 발생했습니다..."`)을 주입하고 `continue`를 호출하여 UI 블로킹 없이 에이전트가 자체 해결을 시도하도록 합니다.
    *   **상태 보존**: `MaxTurnsExceeded` 발생 시 `save_plan_state` 호출 후 상태를 유지하며 재개합니다.
    *   **예외 주입**: 엔진 예외 발생 시 `ConversationMessage`를 강제 주입하고 로그창에 `[System Error]`를 출력한 후 다음 턴을 트리거합니다.

### 2.3 네이티브 UI 컴포넌트 확장 (모달 및 대시보드)

CLI의 터미널 텍스트 환경에서는 불가능했던 풍부한 GUI 경험을 제공합니다.

*   **`SecurityApprovalModal` (보안 승인 모달)**: 
    *   파괴적 도구(`BashTool`, `WriteFileTool` 등) 실행 시 화면 중앙에 나타나는 팝업(ModalScreen) 창을 신규 구현(`modals.py`).
    *   실행 사유와 명령어가 텍스트로 보이고, 하단에 `[y] 승인`, `[a] 항상 승인`, `[n] 거부` 버튼을 배치합니다.
    *   `permission_prompt` 훅(Hook)에서 `await app.push_screen_wait(SecurityApprovalModal(...))` 형태로 비동기 대기하여 사용자의 응답을 처리합니다.
*   **Slash 커맨드 네이티브 렌더링 지원**:
    *   `/cost`, `/stats` 입력 시 콘솔 문자열이 아닌 `RichLog` 내부의 마크다운 테이블이나 전용 패널을 렌더링합니다.
    *   `/kb`, `/tools`, `/validate` 등 최신 CLI 명령어 핸들러를 TUI 구조에 맞게 이식합니다.
*   **사이드바(Sidebar) 동적 업데이트**:
    *   **PLAN 모드**: 사이드바를 `Task 진행 현황` 위젯(체크리스트)으로 동적 교체합니다.
    *   **AGENT 모드**: 기존의 `Status & CostTracker` 위젯으로 복귀합니다.

---

## 3. 마일스톤 및 예상 검증 항목

이 로드맵은 Phase 5 이후의 주요 작업 항목으로 관리되며, 구현 완료 시 다음 항목들을 검증해야 합니다.

1.  **엔진 결합도 분리 검증**: TUI 구동 시 기존 OpenHarness `Runtime` 없이도 7종의 커스텀 툴 및 코어 툴이 모두 정상 작동하는가?
2.  **비동기 루프 안정성 검증 (Auto-Resume)**: 런타임 또는 툴 에러 발생 시 UI 창이 멈추지 않고, 에이전트가 실시간으로 에러 로그를 분석하며 자가 수정을 진행(RichLog 업데이트)하는가?
3.  **컴포넌트 렌더링 검증**: 파괴적 액션 시도 시 화면 중앙에 `SecurityApprovalModal`이 안정적으로 렌더링되고 응답(`y`, `n`, `a`)이 올바르게 라우팅되는가?
