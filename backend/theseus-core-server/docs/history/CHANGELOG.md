# Changelog

모든 변경 사항은 최신순(역순)으로 기록됩니다.

## [Unreleased]

### 🏗️ Session 40 — 프로젝트별 역할 기반 툴 가시성 (RuntimeMode + PermissionProvider) (2026-05-08)

#### 목표
`dual_mode_runtime_spec.md` P0 항목 구현.
프로젝트별·역할별로 사용자에게 보이는 툴이 달라지도록 에이전트 코어를 준비한다.
기존 standalone 호출은 하위 호환 유지.

---

#### 신규 파일 1 — `theseus_engine/models/runtime_mode.py`

- `RuntimeMode` enum: `STANDALONE` / `SERVER`
- `detect_runtime_mode(project_id, actor_user_id)`:
  - 우선순위: 환경변수 `THESEUS_RUNTIME_MODE` > 컨텍스트 파라미터 > 폴백 `STANDALONE`

---

#### 신규 파일 2 — `theseus_engine/models/permission_provider.py`

- `ToolPermissionProvider` ABC:
  - `get_permissions() -> dict[str, int]` — 툴 권한 맵
  - `get_disabled_tools() -> set[str]` — 프로젝트 단위 비활성 툴
  - `sync_tool(tool_name, permission_level, meta)` — 생성/갱신 후 소스 동기화
- `StandalonePermissionProvider` — `.meta.json` 파일 스캔 기반
  - `get_permissions()`: `custom_tools/*.meta.json` 의 `permissionLevel` 읽기
  - `get_disabled_tools()`: `isActive=False` 인 툴 수집
  - `sync_tool()`: `.meta.json` 의 `permissionLevel` 갱신
- `ServerPermissionProvider` — 콜백 함수 주입 방식
  - `theseus_engine`은 `src/auth`를 직접 import하지 않음
  - 호출 측(`src/builder/engine.py`)이 `fetch_permissions_func`, `fetch_disabled_func`, `sync_func` 콜백을 주입
  - Spring Backend API 연결 시 추가 코드 변경 불필요

---

#### 수정 — `theseus_engine/tools/core/tool_factory.py`

- `load_custom_tools_for_project(registry, project_id, tool_permissions)` 함수 추가:
  - 경로: `custom_tools/projects/<project_id>/*.py`
  - `meta.json`의 `isActive=True` && `status="active"` 인 것만 로드
  - `ToolValidator.validate_and_load_module()` 검증 후 등록
  - `tool_permissions` 딕셔너리에 로드된 툴의 `permission_level` 자동 추가
- `normalize_tool_meta()` — `runtimeMode` 필드 추가 (기본값 `"standalone"`)

---

#### 수정 — `theseus_engine/tools/core/__init__.py`

- `load_custom_tools_for_project` export 추가

---

#### 수정 — `theseus_engine/core/engine_builder.py`

- `setup_engine()` 신규 파라미터:
  - `project_id: str | None = None` — 프로젝트 격리 경로
  - `actor_role: str = "MEMBER"` — `"ADMIN"` / `"MEMBER"`
  - `project_disabled_tools: set | None = None` — 프로젝트 단위 비활성 툴
- 커스텀 툴 로딩 분기: `project_id` 유무에 따라 `load_custom_tools` / `load_custom_tools_for_project` 선택
- `create_tool` 제외 로직 강화:
  - 기존: PLAN EXECUTING이면 허용
  - 변경: **ADMIN** 역할 + PLAN EXECUTING 일 때만 `create_tool` 허용
- `project_disabled_tools` → `exclude_tools`에 합산하여 `build_filtered_registry` 호출
- `tool_metadata`에 `project_id`, `actor_role` 추가

---

#### 하위 호환

- 모든 신규 파라미터에 기본값 설정 (`None`, `"MEMBER"`, `None`)
- `theseus_cli.py`, `tui_main.py` 기존 호출 변경 없이 동작 유지
- standalone 경로 (`project_id=None`): 기존 `load_custom_tools()` 사용, `create_tool`은 PLAN EXECUTING에서 역할 제한 없이 허용 (로컬 사용자는 ADMIN 역할 불요)
- 서버 경로 (`project_id` 존재): `actor_role="ADMIN"` 일 때만 `create_tool` 허용

---

#### 기능 추가 — CLI / TUI 사용자 역할 표시

**파일**: `theseus_cli.py`, `theseus_cli/context.py`, `theseus_cli/ui.py`, `theseus_engine/tui/tui_main.py`

현재 사용자의 역할(`ADMIN` / `MEMBER`)을 CLI 헤더와 TUI 사이드바에 표시.

- **`theseus_cli.py`**: `actor_role = "ADMIN"` 변수 추가, `CLIContext`·`print_help`에 전달
- **`theseus_cli/context.py`**: `actor_role: str = "ADMIN"` 필드 추가
- **`theseus_cli/ui.py`**: `print_status()`·`print_help()`에 `actor_role` 파라미터 추가, 헤더에 `역할 : ADMIN` 줄 출력
- **`theseus_engine/tui/tui_main.py`**:
  - `self.actor_role = "ADMIN"` 필드 추가
  - 사이드바 Status에 `role : ADMIN` 표시 (ADMIN → `bold cyan`, MEMBER → `dim`)
  - 초기화 완료 메시지에 `Role: ADMIN | RBAC: Lv.5` 표시

**CLI 출력 예시**:
```
  현재 모드  : 🤖 AGENT       (자율 실행)
  역할       : ADMIN
  권한 레벨  : Lv.5  (1=최소 / 5=최대)
```

**TUI 사이드바 예시**:
```
● Status
  model     : gpt-4o
  mode      : AGENT
  role      : ADMIN
  RBAC      : Lv.5
  tokens    : N/A
  messages  : 0
  session   : default
```

---

### 🖥️ Session 39 — TUI Native App 고도화: 바인딩 정리 · /quit 커맨드 · 자동완성 수정 (2026-05-08)

#### 목표
`tui_native_app_refactoring_plan.md` 로드맵의 구현 완료 후 발견된 잠재 버그를 수정하고,
TUI 종료 커맨드(`/quit`, `/exit`, `/bye`)를 추가하여 사용성을 완성.

---

#### 버그 수정 1 — Textual 키바인딩 중복 등록

**증상**: `TheseusTUI.BINDINGS`에 `ctrl+p/a/s`를 직접 선언하면서 `*THESEUS_BINDINGS` spread도 포함 —
동일 키가 두 번 등록되어 Textual 내부 경고(BindingConflict) 발생 가능.

**수정**: `theseus_engine/tui/tui_main.py`
- `BINDINGS` 리스트에서 `*THESEUS_BINDINGS` spread 제거
- `from theseus_engine.tui.ui_components import THESEUS_BINDINGS, ...` → `THESEUS_TUI_CSS`만 import

**수정**: `theseus_engine/tui/ui_components.py`
- `THESEUS_BINDINGS` 목록에서 `ctrl+p/a/s/c` 4개 제거 (tui_main.py에서 직접 관리)
- `ctrl+c → quit_session` 바인딩 제거 — 터미널 인터럽트(SIGINT)와 충돌 방지
- `THESEUS_BINDINGS`는 향후 확장 포인트로 빈 목록만 유지

---

#### 버그 수정 2 — `CommandRegistry.list_commands()` 누락

**증상**: `AutocompleteHelper.get_command_suggestions()`에서 `bundle.commands.list_commands()` 호출 →
`AttributeError: 'CommandRegistry' object has no attribute 'list_commands'`

**수정**: `theseus_engine/tui/commands.py`
- `list_commands() -> list[SlashCommand]` 메서드 추가
  - `_canonical_names` 순서대로 등록된 모든 `SlashCommand` 객체를 반환

---

#### 기능 추가 — `/quit` `/exit` `/bye` 종료 커맨드

**파일**: `theseus_engine/tui/tui_main.py`

TUI 내에서 슬래시 커맨드로 앱을 안전하게 종료할 수 있는 커맨드 3종 추가.

| 커맨드 | 동작 |
|--------|------|
| `/quit` | 현재 세션 히스토리를 저장하고 TUI 종료 |
| `/exit` | `/quit`와 동일 |
| `/bye`  | `/quit`와 동일 |

**구현 상세**:
- `TheseusInput._THESEUS_CMDS`에 `"quit"`, `"exit"`, `"bye"` 추가 → Input 위젯 레벨에서 선제 인터셉트
- `_register_commands()`에 세 커맨드 모두 동일한 `_cmd_quit` 핸들러로 등록
- `_cmd_quit()` 핸들러:
  - `save_session_history()` 호출로 메시지 히스토리 보존
  - RichLog에 `"👋 Goodbye! Session saved."` 출력
  - `self.call_after_refresh(self.exit)` — 마지막 메시지가 화면에 렌더된 한 프레임 후 종료
    (즉시 `self.exit()` 호출 시 RichLog write가 화면에 나타나기 전에 앱이 닫히는 현상 방지)

---

### 🔧 Session 38 — requirements.txt OH 의존 제거 & README 현행화 (2026-05-08)

#### 목표
`-e ./OpenHarness` 항목을 `requirements.txt`에서 완전히 제거하고,
OH가 간접 제공하던 패키지를 Theseus가 직접 명시하도록 재구성.
README.md의 OH 관련 문구를 현행 아키텍처에 맞게 갱신.

---

#### `requirements.txt` 재편

| 구분 | 변경 내용 |
|------|----------|
| 제거 | `-e ./OpenHarness` — OH 로컬 패키지 완전 삭제 |
| 추가 | `anthropic>=0.40.0` — Theseus-native LLM client (OH가 간접 제공하던 것) |
| 추가 | `openai>=1.0.0` — OpenAI 호환 클라이언트 직접 명시 |
| 추가 | `textual>=0.80.0` — TUI 프레임워크 직접 명시 (OH가 간접 제공) |
| 추가 | `rich>=13.0.0` — 터미널 렌더링 (OH 간접 의존) |
| 추가 | `prompt-toolkit>=3.0.0` — CLI 입력 처리 (OH 간접 의존) |
| 추가 | `sse-starlette>=1.6.0` — FastAPI SSE 스트리밍 |
| 추가 | `websockets>=12.0` — MCP/WebSocket 통신 |
| 추가 | `pyyaml>=6.0` — YAML 파싱 유틸 |
| 추가 | `psutil` — 시스템 리소스 모니터링 (커스텀 툴 실사용) |
| 추가 | `speedtest-cli` — 인터넷 속도 측정 툴 의존 |
| 정리 | 섹션별 주석(`Web Framework`, `LLM Clients`, `TUI` 등) 추가로 가독성 개선 |

**제거 근거**: OH `pyproject.toml` 의존성(`anthropic`, `openai`, `textual`, `rich`, `prompt-toolkit`, `websockets`, `pyyaml` 등)이 `-e ./OpenHarness`를 통해 간접 설치되고 있었음. OH 제거 후 이 패키지들이 누락되지 않도록 직접 명시.

---

#### `README.md` 현행화

- **개발 환경**: `"Python 3.11 권장 (OpenHarness 권장 사양)"` → `"Python 3.11 권장"`
- **Tech Stack**: `theseus_engine (OpenHarness 의존성을 배제한...)` → `(자체 구현 코어 엔진 — OpenHarness 의존성 없음)`, LLM Clients 항목 신규 추가
- **Quick Start**: `"의존성 설치 (openharness 라이브러리 포함)"` → `"의존성 설치"`
- **업무 분장 B**: QueryEngine 설명에 `theseus_engine/engine/query_engine.py` 경로 명시, `create_tool` 자동 등록 알림·`/tools custom` 언급 추가

---

### 🐛 Session 37 — maybe_compress 시그니처 버그 수정 / /tools custom 커맨드 추가 / create_tool 자동 등록 알림 / LLM 생성 코드 정제 (2026-05-08)

---

#### 버그 수정 1 — `maybe_compress()` 미지원 파라미터 에러

**증상**: `[ERROR] maybe_compress() got an unexpected keyword argument 'system_prompt'`

**원인**: `theseus_engine/engine/query_engine.py`의 `run_query()` 안에서 `maybe_compress()`를 호출할 때
`system_prompt=`, `force=True` 두 개의 없는 파라미터를 전달하고 있었음.
`maybe_compress(messages, max_messages, keep_recent, api_client, model)` 시그니처에는 두 파라미터가 없음.
추가로 반환값이 `(list, bool)` 튜플인데 `messages = await ...` 로 튜플 전체를 받고 있었음.

**수정**: `theseus_engine/engine/query_engine.py`
- auto-compact 경로: `system_prompt` 제거, 반환값 `messages, _ = await maybe_compress(...)` 언패킹
- reactive compact 경로: `system_prompt`·`force=True` 제거, `keep_recent=4` 명시(공격적 압축), 반환값 언패킹

---

#### 기능 추가 1 — `/tools custom` 커맨드

**파일**: `theseus_cli/commands.py`, `theseus_cli/context.py`, `theseus_cli.py`, `theseus_cli/ui.py`

`/tools` 커맨드를 서브커맨드 방식으로 확장.

| 커맨드 | 동작 |
|--------|------|
| `/tools` 또는 `/tools all` | 전체 활성 툴 목록. 커스텀 툴은 `[custom]` 태그 표시 |
| `/tools custom` | 커스텀 툴만 필터링. `meta.json`에서 권한·상태·검증 결과 읽어 상세 출력 |
| `/tools help` | 서브커맨드 도움말 |

- **`theseus_cli/commands.py`**:
    - `/tools` 핸들러를 서브커맨드 라우터로 재작성
    - `_print_all_tools(ctx)`: 전체 툴 테이블, 커스텀 툴 `[custom]` 태그
    - `_print_custom_tools(ctx)`: `meta.json`(`toolName`, `permissionLevel`, `status`, `isActive`, `validationResult`) + registry 인스턴스 `description` 조합 출력
    - `_get_custom_tool_names()`: `custom_tools/` 디렉토리 `.py` 파일 스캔
    - `_load_meta(dir, module_name)`: `module_name.meta.json` 파싱 헬퍼

- **`theseus_cli/context.py`**: `full_registry: Any = None` 필드 추가

- **`theseus_cli.py`**:
    - `engine, _ = await setup_engine(...)` → `engine, full_registry = await setup_engine(...)`
    - `CLIContext(full_registry=full_registry)` 주입
    - 매 턴 `setup_engine` 재구성 후 `ctx.full_registry = new_full_registry` 갱신

- **`theseus_cli/ui.py`**: `/help` 출력에 `/tools custom`, `/tools help` 라인 추가

---

#### 기능 추가 2 — `create_tool` 성공 후 자동 등록 알림

**파일**: `theseus_cli.py`

`create_tool` 툴이 성공적으로 실행된 직후, 다음 `AssistantTurnComplete` 이벤트 수신 시 새로 등록된 툴 정보를 자동으로 출력.

**동작 흐름**:
```
ToolExecutionCompleted(tool_name="create_tool", is_error=False)
  └─ output에서 "Tool '<name>' created" 정규식 파싱 → newly_created_tools 누적
AssistantTurnComplete
  └─ _auto_print_created_tools() 자동 호출
  └─ ctx.full_registry를 engine._tool_metadata["tool_registry"]로 갱신
```

**출력 예시**:
```
────────────────────────────────────────────────────────────
  ✨ 새 커스텀 툴 등록 완료 (1개)
────────────────────────────────────────────────────────────
  🔧 internet_speed_tool
     권한 레벨   : Lv.1
     상태        : active
     파일        : custom_tools/internet_speed_tool.py
     설명        : 인터넷 속도를 측정하여 다운로드/업로드 속도…
     검증        : ✅ 통과

  💡 '/tools custom' 으로 전체 커스텀 툴 목록을 확인할 수 있습니다.
────────────────────────────────────────────────────────────
```

- **추가 함수** `_auto_print_created_tools(tool_names, ctx)`:
    - 각 툴 이름으로 `module_name.meta.json` 읽기
    - `full_registry` 또는 `engine._tool_metadata["tool_registry"]`에서 인스턴스 조회 → `description` 출력
    - validation 이상 시 경고 라인 추가
- **이벤트 루프 수정**: `newly_created_tools: list[str] = []` 턴 단위 버퍼, `ToolExecutionCompleted` 핸들러에서 파싱·누적, `AssistantTurnComplete` 후 출력 및 `clear()`

---

#### 버그 수정 2 — LLM 생성 코드 파싱 오염 (`SyntaxError: unexpected character after line continuation character`)

**증상**: `[ToolAudit] Legacy tool creation failed at validation: Syntax Error: unexpected character after line continuation character (<unknown>, line 7)`

**원인 분류**:

| 패턴 | 원인 |
|------|------|
| `\ ` (백슬래시 + 후행 공백) | LLM이 줄 끝 공백을 보존한 채 멀티라인 코드 생성 — 파이썬은 `\` 뒤 공백에서 SyntaxError 발생 |
| ` ```python\n...\n``` ` | `python_code` 인자에 마크다운 펜스 블록째로 전달 |
| `\r\n` 혼입 | Windows 라인엔딩이 섞인 코드 생성 |
| NULL 바이트 | 바이너리 혼입 시 파서 충돌 |

**수정**: `_sanitize_generated_code(code: str) -> str` 함수를 두 실행 경로 모두에 추가.

- **`theseus_engine/tools/core/tool_factory.py`**:
    - `_sanitize_generated_code()` 모듈 레벨 함수 추가
    - `_execute_standalone()` 내 `inject_permission_level()` 직후 `code = _sanitize_generated_code(code)` 호출
    - 검증 실패 시 코드 앞 20줄을 로그에 덤프 (디버깅 가시성 확보)

- **`src/tooling/service.py`**:
    - 동일한 `_sanitize_generated_code()` 함수 추가 (서버 경로 동일 처리)
    - `inject_permission_level()` 직후 `code = _sanitize_generated_code(code)` 호출

**`_sanitize_generated_code` 처리 순서**:
1. 마크다운 코드펜스 벗기기 (` ```python ... ``` `)
2. CRLF → LF 정규화
3. NULL 바이트 제거
4. `\ ` (백슬래시 + 1개 이상 공백 + `\n`) → `\\\n` 교정

---

### 🔧 Session 36 — QueryEngine & TUI OH 의존 완전 제거 (2026-05-08)

#### 목표
`openharness.engine.query_engine.QueryEngine`, `openharness.ui.*`, `openharness.commands.*` 의존을
Theseus-native 구현으로 교체하여 `theseus_engine` 패키지 내 **런타임 OH import 0개** 달성.

#### 달성 결과 요약

| 영역 | 이전 | 이후 |
|------|------|------|
| QueryEngine | `openharness.engine.query_engine.QueryEngine` | `theseus_engine.engine.query_engine.QueryEngine` |
| Stream Events | OH re-export `try/except` 브릿지 | Theseus-native frozen dataclass |
| TUI 베이스 | `OpenHarnessTerminalApp` 상속 | `textual.app.App` 직접 상속 |
| TUI 런타임 | `build_runtime`, `start_runtime`, `handle_line` (OH) | `build_theseus_runtime`, `start_theseus_runtime` (Theseus-native) |
| 커맨드 레지스트리 | `SlashCommand`, `CommandResult` (OH) | `theseus_engine.tui.commands` (Theseus-native) |
| sys.path 주입 | `OpenHarness/src` 경로 2곳 | 완전 제거 |

---

#### Task 2 — QueryEngine Theseus-native 구현 및 배선

- **`theseus_engine/engine/query_engine.py` (신규)**:
    - `MaxTurnsExceeded(max_turns)` — OH 호환 예외 클래스
    - `QueryContext` dataclass — 단일 쿼리 실행 상태 캡슐화
    - `_execute_tool_call()`:
        - pre-hook (`TheseusHookExecutor.before_tool`) → permission check (`TheseusPermissionChecker`) → tool 유효성 검사 → tool 실행
        - 대형 출력 파일 오프로드 (`THESEUS_TOOL_OUTPUT_INLINE_CHARS`, 기본 8000자)
        - carryover 추적 (읽기/쓰기 파일 메타 기록) → post-hook (`after_tool`)
    - `run_query()` 비동기 제너레이터:
        - auto-compact: `context_compressor.maybe_compress()` 위임
        - token limit 에러 감지 → reactive compact 후 재시도
        - 복수 tool call 병렬 실행: `asyncio.gather(return_exceptions=True)`
        - `AssistantTextDelta`, `AssistantTurnComplete`, `ToolExecutionStarted`, `ToolExecutionCompleted`, `ErrorEvent`, `StatusEvent`, `CompactProgressEvent` yield
    - `QueryEngine` 클래스 — OH-compatible public interface:
        - `submit_message(text)` → `AsyncIterator[StreamEvent]`
        - `set_system_prompt(prompt)`, `set_api_client(client)`, `clear()`
        - `load_messages(msgs)`, `messages` property, `total_usage` property
    - Tool metadata 추적 헬퍼:
        - `remember_user_goal`, `_remember_active_artifact`, `_remember_verified_work`
        - `_remember_read_file`, `_record_tool_carryover`, `_offload_tool_output_if_needed`

- **`theseus_engine/core/engine_builder.py`**:
    - `from openharness.engine.query_engine import QueryEngine` → `from theseus_engine.engine.query_engine import QueryEngine`

- **`theseus_engine/core/command_handler.py`**:
    - `from openharness.engine.query_engine import QueryEngine` → `from theseus_engine.engine.query_engine import QueryEngine`

---

#### Task 6 — stream_events.py 브릿지 → native 전환

- **`theseus_engine/engine/stream_events.py` (재작성)**:
    - OH re-export `try/except ImportError` 브릿지 블록 완전 제거
    - `AssistantTextDelta`, `AssistantTurnComplete`, `ToolExecutionStarted`, `ToolExecutionCompleted`, `ErrorEvent`, `StatusEvent`, `CompactProgressEvent`, `StreamEvent` — 모두 `@dataclass(frozen=True)` Theseus-native 정의로 확정
    - docstring: OH 브릿지 설명 → "Theseus-native stream event types" 로 교체
    - **배경**: Session 34에서 OH `QueryEngine`이 yield하는 타입과 `isinstance()` 호환을 위해 OH re-export 방식을 임시 채택했었음. 본 세션에서 `QueryEngine`을 Theseus-native로 교체하면서 브릿지 불필요 → 순수 Theseus 정의로 전환

---

#### Task 5 — TUI OH 프레임워크 완전 분리

- **`theseus_engine/tui/commands.py` (신규)**:
    - `CommandResult(message, exit_app)` — 커맨드 핸들러 반환값
    - `SlashCommand(name, description, handler)` — 커맨드 정의
    - `CommandRegistry` — 등록(`register`), 조회(`get`), 디스패치(`dispatch`) 기능 포함
    - OH `openharness.commands.registry` 완전 대체

- **`theseus_engine/tui/runtime.py` (신규)**:
    - `AppState(model, permission_mode, session)` — TUI 앱 상태, `.get()`/`.set()` 인터페이스 (OH bundle.app_state 호환)
    - `TheseusBundle(engine, tool_registry, api_client, commands, app_state, external_api_client)` — OH bundle 인터페이스 호환 dataclass
    - `build_theseus_runtime(...)` — `setup_engine` 결과로 `QueryEngine` 생성 및 `TheseusBundle` 반환
    - `start_theseus_runtime(bundle)` — 백그라운드 태스크 시작 (확장 포인트)
    - `handle_theseus_line(bundle, line, ...)` — 슬래시 커맨드 디스패치 (`/exit`, `/quit`, `/clear` 포함)
    - OH `openharness.ui.runtime` 완전 대체

- **`theseus_engine/tui/tui_main.py` (전면 재작성)**:
    - **제거**: `from openharness.ui.textual_app import OpenHarnessTerminalApp`
    - **제거**: `from openharness.ui.runtime import build_runtime, start_runtime, handle_line`
    - **제거**: `from openharness.engine.query import MaxTurnsExceeded`
    - **제거**: `from openharness.commands.registry import SlashCommand, CommandResult`
    - **제거**: `sys.path.insert(0, str(PROJECT_ROOT / "OpenHarness" / "src"))`
    - `TheseusTUI(App)` — `textual.app.App` 직접 상속, Theseus-native CSS/BINDINGS 자체 정의
    - `TheseusInput(Input)` — 슬래시 커맨드 위젯 레벨 인터셉트 유지 (OH 의존 없음)
    - `on_mount()`: OH `build_runtime` 제거 → `setup_engine()` 직접 호출, `TheseusBundle` 생성
    - `_register_commands()`: OH `bundle.commands._commands` 직접 조작 대신 `CommandRegistry.register()` 사용
    - `_render_event()`: `isinstance()` 분기 — `AssistantTextDelta`, `AssistantTurnComplete`, `ToolExecutionStarted`, `ToolExecutionCompleted`, `ErrorEvent`, `StatusEvent`, `CompactProgressEvent` 모두 처리
    - `_process_line()`: `MaxTurnsExceeded` → `theseus_engine.engine.query_engine`에서 import
    - `_cmd_*` 핸들러: `CommandResult` → `theseus_engine.tui.commands`에서 import
    - `action_quit_session()`: 종료 시 세션 히스토리 자동 저장
    - `_refresh_sidebars()`: OH `bundle.app_state.get()` → `TheseusBundle.app_state.get()` 호환 유지

---

#### Task 7 — sys.path OpenHarness 경로 제거

- **`theseus_cli.py`** (line 18):
    - `sys.path.insert(0, str(PROJECT_ROOT / "OpenHarness" / "src"))` 삭제
    - `sys.path.insert(0, str(PROJECT_ROOT))` 1줄만 유지

- **`theseus_engine/core/cli_main.py`** (line 8):
    - 동일 라인 삭제

---

#### 최종 OH 의존 현황 (theseus_engine + theseus_cli)

| 구분 | OH import 수 | 비고 |
|------|-------------|------|
| `theseus_engine/**/*.py` (런타임) | **0** | `state.py` docstring 텍스트만 존재 (코드 아님) |
| `theseus_cli/**/*.py` | **0** | 완전 클린 |
| `src/builder/engine.py` | 6 | 서버 빌더 — 별도 계획 |
| `docs/legacy/*.py` | 13 | 비활성 레거시 — 삭제 예정 |

---

### 🔧 Session 35 — Message 타입 & LLM Client OH 의존 제거 (2026-05-08)

#### 목표
`openharness.engine.messages`, `openharness.api.client`, `openharness.api.openai_client`,
`openharness.api.usage` 4개 모듈 의존을 Theseus-native 구현으로 완전 교체.

#### Task 3 — Message 타입 자체 정의

- **`theseus_engine/models/messages.py` (신규)**:
    - `TextBlock`, `ImageBlock`, `ToolUseBlock`, `ToolResultBlock`, `ContentBlock`, `ConversationMessage` — Pydantic BaseModel 기반, OH 의존 없음
    - `serialize_content_block()`, `assistant_message_from_api()`, `sanitize_conversation_messages()` 헬퍼 포함
    - `ConversationMessage.to_api_param()`, `.text`, `.tool_uses`, `from_user_text()` 등 OH와 동일 인터페이스 유지

- **`theseus_engine/models/sessions.py`**: `from openharness.engine.messages import ConversationMessage` → `theseus_engine.models.messages`
- **`theseus_engine/core/context_compressor.py`**: lazy OH import → Theseus 직접 import (try/except 제거)
- **`theseus_cli/intent.py`**: `openharness.engine.messages` → `theseus_engine.models.messages`
- **`src/history/mapper.py`**: lazy OH import → Theseus import (fallback 메시지 문구 업데이트)
- **`tests/test_markdown_to_pdf.py`**: `openharness.tools.base.ToolExecutionContext` → `theseus_engine.tools.core.base_tools`

#### Task 1 — LLM Client OH 의존 제거

- **`theseus_engine/wrappers/llm_clients/api_types.py` (신규)**:
    - `UsageSnapshot`, `ApiMessageRequest`, `ApiTextDeltaEvent`, `ApiMessageCompleteEvent`, `ApiRetryEvent`, `ApiStreamEvent`, `SupportsStreamingMessages` Protocol
    - `TheseusApiError`, `AuthenticationFailure`, `RateLimitFailure`, `RequestFailure` 에러 타입

- **`theseus_engine/wrappers/llm_clients/anthropic_client.py` (신규)**:
    - `TheseusAnthropicClient` — `AnthropicApiClient` OH 의존 없이 재구현
    - 표준 API 키 인증, retry/backoff, `_stream_once()` 완전 구현
    - Claude OAuth 전용 코드 제거 (OH 전용 기능)

- **`theseus_engine/wrappers/llm_clients/openai_compat_client.py` (신규)**:
    - `TheseusOpenAICompatClient` — `OpenAICompatibleClient` OH 의존 없이 재구현
    - 변환 함수 4개 이식: `_convert_messages_to_openai`, `_convert_tools_to_openai`, `_token_limit_param_for_model`, `_strip_think_blocks`
    - DashScope, DeepSeek, Ollama, vLLM, OpenAI 등 모든 OpenAI 호환 제공자 지원

- **`theseus_engine/wrappers/llm_clients/theseus_client.py`**:
    - `from openharness.api.*`, `from openharness.engine.messages` → `theseus_engine.wrappers.llm_clients.api_types`, `theseus_engine.models.messages`
    - `AnthropicApiClient` → `TheseusAnthropicClient`, `OpenAICompatibleClient` → `TheseusOpenAICompatClient`

#### 잔여 OH import (theseus_engine/ 기준)

| 파일 | 항목 | Phase |
|------|------|-------|
| `core/engine_builder.py`, `core/command_handler.py` | `QueryEngine` | Task 2 (P1) |
| `engine/stream_events.py` | OH re-export 브릿지 | Task 6 (QueryEngine 이후) |
| `tui/tui_main.py` | TUI 프레임워크 4개 | Task 5 (P2) |

---

### 🔧 Session 34 — Tool Primitives & Stream Events 자체 정의 (2026-05-07)

#### 목표
OpenHarness 완전 분리를 위해 남은 핵심 import 2개(`openharness.tools.base`, `openharness.engine.stream_events`)를 Theseus-native 구현으로 교체.

#### Task 1 — `base_tools.py` 자체 정의

- **`theseus_engine/tools/core/base_tools.py`**:
    - `from openharness.tools.base import (BaseTool, ToolExecutionContext, ToolResult, ToolRegistry)` 제거.
    - `ToolExecutionContext` (dataclass), `ToolResult` (frozen dataclass), `BaseTool` (ABC), `ToolRegistry` (dict-backed)를 Theseus-native로 완전 재정의.
    - `to_api_schema()` 메서드 포함 — LLM API 스키마 변환 자체 처리.
    - `DummyTool`, `SystemRebootTool` 테스트 도구 유지.
    - 모든 `theseus_engine/` 코드가 이 단일 모듈에서 import — 향후 OH 완전 제거 시 변경점 1곳.

#### Task 2 — `stream_events.py` OH 브릿지 + Theseus 폴백

- **`theseus_engine/engine/stream_events.py` (신규)**:
    - OH `QueryEngine`이 yield하는 이벤트와 `isinstance()` 호환을 위해 OH re-export 방식 채택.
    - `try: from openharness.engine.stream_events import ...` → `except ImportError:` Theseus-native frozen dataclass 폴백.
    - 향후 QueryEngine 자체 분리 시 이 파일만 Theseus-native 정의로 교체하면 완료.
    - `AssistantTextDelta`, `AssistantTurnComplete`, `ToolExecutionStarted`, `ToolExecutionCompleted`, `ErrorEvent`, `StatusEvent`, `CompactProgressEvent`, `StreamEvent` 8개 심볼 제공.

- **`theseus_engine/core/cli_main.py`**: import를 `theseus_engine.engine.stream_events`로 변경.
- **`theseus_cli.py`**: import를 `theseus_engine.engine.stream_events`로 변경.

#### Hotfix — `isinstance()` 불일치 수정

- **원인**: `QueryEngine`(OH)은 `openharness.engine.stream_events.AssistantTextDelta`를 yield하지만, 변경 후 `theseus_cli.py`가 `theseus_engine.engine.stream_events.AssistantTextDelta`로 isinstance 체크 → 서로 다른 클래스이므로 항상 `False` → 모든 이벤트가 `else` 분기의 `[EVENT]` 디버그 출력으로 빠짐.
- **수정**: `stream_events.py`를 OH re-export 방식으로 변경하여 동일 클래스 참조 보장. OH 미설치 환경에서는 Theseus-native 폴백 자동 적용.

---

### 🏗️ Session 33 — OpenHarness 의존성 체계적 제거 (2026-05-07)

#### 목표
OpenHarness 컴포넌트가 유기적으로 참조되어 Theseus 엔진이 bypass되는 문제를 근본 해결. 3단계(단기/중기/장기)로 의존성을 제거하여 Theseus가 모든 Hook/RBAC/Tool 파이프라인을 독자적으로 제어하도록 개선.

---

#### 🔴 Phase 1 (단기) — Hook/RBAC 상속 제거, 핵심 bypass 차단

- **`theseus_hook_executor.py` — `HookExecutor` 상속 완전 제거**:
    - `class TheseusHookExecutor(HookExecutor)` → `class TheseusHookExecutor`로 변경.
    - `super().__init__(registry, context)`, `super().execute(event, payload)` 호출 삭제 — OH Hook 파이프라인이 Theseus보다 선행하는 문제 원천 제거.
    - `HookEvent`, `HookResult`, `AggregatedHookResult`를 Theseus-native로 재정의 (동일 필드/프로퍼티 유지, QueryEngine duck-typing 호환).
    - `__init__` 시그니처에서 `registry: HookRegistry`, `context: HookExecutionContext` 제거 → keyword-only 파라미터로 단순화.
    - OH `AgentHook` Markdown backtick 복구 로직 삭제 (OH 파이프라인 자체가 없으므로 불필요).
    - OpenHarness import 6개 → 0개로 감소.

- **`engine_builder.py` — `create_default_tool_registry()` 제거**:
    - `from openharness.tools import create_default_tool_registry` 삭제.
    - `full_registry = create_default_tool_registry()` → `full_registry = ToolRegistry()` 로 교체.
    - OH 기본 도구(BashTool, FileReadTool 등 38개)가 Theseus `ALL_CORE_TOOLS`와 이중 등록되던 문제 해결.
    - `HookRegistry`, `HookExecutionContext` import 및 사용 삭제 — `TheseusHookExecutor` 생성자가 더 이상 필요하지 않음.

- **`rbac.py` — `PermissionChecker`/`PermissionSettings` 상속 제거**:
    - `class TheseusPermissionChecker(PermissionChecker)` → 독립 클래스.
    - `PermissionDecision`, `TheseusPermissionSettings`, `PermissionMode` Theseus-native 정의.
    - OH `SENSITIVE_PATH_PATTERNS` 이관 (민감 자격증명 경로 보호 유지).
    - `super().evaluate()` 호출 삭제 — Theseus가 RBAC + 경로/명령어 정책을 직접 평가.

---

#### 🟠 Phase 2 (중기) — 래핑 레이어 교체

- **`tui_main.py` — `PermissionMode` import 교체**:
    - `from openharness.permissions.modes import PermissionMode` → `from theseus_engine.models.rbac import PermissionMode`.
    - TUI 베이스(`OpenHarnessTerminalApp`)는 장기 교체 대상으로 주석 표시.

- **PLAN DRAFTING 프롬프트 — `create_tool` 경로 명시**:
    - `state.py` DRAFTING RULES에 "새 도구 생성 시 `target_files`는 `theseus_engine/custom_tools/` 경로만 사용, `OpenHarness/src/` 금지" 지시 추가.
    - `tool_factory.py` `execute()` — `src.tooling` import를 `try/except ImportError`로 감싸 CLI 전용 배포에서 standalone 폴백.

---

#### 🟡 Phase 3 (장기) — `BaseTool`/`ToolResult` re-export 단일 게이트웨이

- **`base_tools.py` — OpenHarness tool primitives 단일 진입점 확립**:
    - `BaseTool`, `ToolExecutionContext`, `ToolResult`, `ToolRegistry`를 `base_tools.py`에서 re-export.
    - `theseus_engine/tools/core/` 26개 파일, `theseus_engine/custom_tools/` 7개 파일, `core/tool_retriever.py`, `core/engine_builder.py` — 전부 `from openharness.tools.base import ...` → `from theseus_engine.tools.core.base_tools import ...`로 일괄 교체.
    - **향후 OpenHarness 완전 분리 시 `base_tools.py` 1개 파일만 교체하면 됨**.

---

#### 현재 잔존 OpenHarness 의존 (장기 유지/순차 교체 대상)

| 모듈 | 의존 | 비고 |
|------|------|------|
| `base_tools.py` | `openharness.tools.base` | 단일 게이트웨이 (설계상 유지) |
| `engine_builder.py`, `command_handler.py` | `QueryEngine` | 코어 LLM 엔진 — 교체 비용 최대 |
| `theseus_client.py` | `openharness.api.*` | API client/message types — 대규모 이관 필요 |
| `tui_main.py` | `OpenHarnessTerminalApp`, `build_runtime` 등 | TUI 프레임워크 — Theseus 자체 TUI 완성 후 교체 |
| `cli_main.py` | `stream_events` | 이벤트 데이터 클래스 — 장기 유지 허용 |
| `sessions.py`, `context_compressor.py` | `ConversationMessage` | 메시지 타입 — `QueryEngine` 교체와 동시 진행 |

---

### 🔒 Session 32 — THESEUS_ENABLE_AGENT_HOOK OpenHarness 의존성 제거 (2026-05-07)

#### 목표
`THESEUS_ENABLE_AGENT_HOOK=true` 활성화 시 `src/tooling` 서버 레이어(Spring/FastAPI)와 OpenHarness `AgentHookDefinition`에 대한 의존 없이 독립적으로 감사 LLM을 실행하도록 개선.

#### 변경 사항

- **`theseus_engine/tools/core/tool_validator.py` — 신규 생성**:
    - `src/tooling/service.py`에만 있던 `ToolCreationError`, `normalize_tool_name`, `inject_permission_level`를 `theseus_engine/` 내부에 독립 모듈로 추출.
    - `theseus_engine/` 내에서 `src/` 레이어 없이 도구 생성 파이프라인 전체를 자급자족.

- **`theseus_engine/tools/core/tool_factory.py` — `_execute_standalone()` 독립화**:
    - `_execute_legacy()`가 `src.tooling.service`를 import하던 의존성 제거.
    - `_execute_standalone()`이 `theseus_engine.tools.core.tool_validator`만 사용하도록 리팩토링.
    - `_execute_legacy()`는 `_execute_standalone()`으로 위임(delegate)하는 thin wrapper로 유지.

- **`theseus_engine/wrappers/hooks/theseus_hook_executor.py` — 감사 LLM 독립화**:
    - `_AUDIT_PROMPT` 클래스 상수 추가 (OpenHarness `AgentHookDefinition.prompt`에서 이관).
    - `__init__`에 `llm_client: TheseusLLMClient` 및 `audit_tools: set[str]` 파라미터 추가.
    - `_run_audit_llm(tool_name, tool_input)` 메서드 구현: `TheseusLLMClient.generate()`를 직접 호출하여 파일 수정 안전성 감사. OpenHarness `AgentHookDefinition` 불필요.
    - PRE_TOOL_USE 블록에서 `self._audit_tools`에 속한 도구(기본: `write_file`, `edit_file`)에 대해 `_run_audit_llm()` 자동 실행.
    - 감사 실패(`ok: false`) 시 HITL 건너뛰고 즉시 차단. 감사 LLM 오류(예외) 시 통과 처리(fail-open).

- **`theseus_engine/core/engine_builder.py` — HookExecutor 생성자 갱신**:
    - `HookEvent`, `AgentHookDefinition` import 제거.
    - `TheseusHookExecutor` 생성 시 `llm_client=api_client`, `audit_tools={"write_file", "edit_file"}` 전달.

---

### 🐛 Session 31 — CHANGELOG 감사 및 불일치 전면 수정 (2026-05-07)

#### 신규 버그 수정

- **`bash_tool.py` — Windows 따옴표 손상 버그 수정 (🚨 Critical)**:
    - Windows에서 `asyncio.create_subprocess_exec("cmd.exe", "/c", command)`를 사용할 때 Python의 `list2cmdline`이 command 문자열을 추가 인용하면서 cmd.exe가 따옴표를 잘못 처리, Python `-c` 인자 앞에 `"`가 붙어 `SyntaxError: unterminated string literal`이 발생하던 버그 수정.
    - Windows/Linux 구분 없이 `asyncio.create_subprocess_shell`로 통일. `IS_WINDOWS` 상수 및 `platform` import 제거.
    - 이 버그로 인해 `python -c "..."` 형태의 모든 bash 명령이 Windows에서 실패하고, 에이전트가 동일 명령을 무한 반복하는 루프의 근본 원인이었음.

- **`engine_builder.py` — EXECUTING 단계에서 `create_tool` RAG 제외 문제 수정 (🔴 High)**:
    - RAG Top-K가 `create_tool`을 쿼리와 무관하다고 판단해 `current_registry`에서 제외하면, `build_filtered_registry`에서 `exclude_tools=set()`(EXECUTING이므로 제외 없음)을 전달해도 이미 없는 도구는 포함되지 않는 구조적 누락 수정.
    - `is_plan_executing=True`일 때 `current_registry`에 `create_tool`이 없으면 `full_registry`에서 꺼내 강제 삽입하는 로직 추가.

- **`theseus_cli.py` — PLAN DRAFTING REINFORCEMENT 과잉 강제 수정 (🟠 Medium)**:
    - Session 28에서 도입된 `"Output ONLY the JSON block... No conversational prose allowed."` 주입이 질문·대화 입력에도 적용되어, 에이전트가 단순 질문을 JSON 플랜으로 만들어버리는 문제 수정.
    - `"REMINDER: If this is a question, answer it directly. If this is an implementation request, output a JSON plan."` 으로 완화하여 입력 의도에 따라 응답 방식을 선택하도록 개선.

#### CHANGELOG 감사 결과 반영 — 기존 미수정 불일치 항목

- **`theseus_cli.py` — `error_sig` 실제 에러 내용 기반으로 수정 (🟠 Medium)**:
    - 기존: `error_sig = resume_prompt[:80]` — tool error 시 항상 고정 문자열(`"A tool execution error occurred..."`)을 시그니처로 사용하여 에러가 달라져도 동일하게 처리됨.
    - 수정: `tool_error_occurred=True`일 때 `error_sig = accumulated_text[-200:][:80]` — LLM이 출력한 실제 에러 텍스트로 시그니처 생성. 에러 내용이 다르면 다른 시그니처로 판별하여 반복 에러 감지 정확도 향상.

- **`context.py`, `theseus_cli.py` — 세션 전체 자동 재개 절대 상한 추가 (🔴 High)**:
    - 문제: `auto_resume_count`가 5 초과 시 `WAIT_FOR_REVIEW`로 강등되지만, 사용자 재승인(`approve`) 후 `auto_resume_count`가 리셋되어 다시 5턴 반복 가능. 세션 전체에서 bash 무한루프가 30턴을 꽉 채우는 원인.
    - `CLIContext`에 `session_resume_total: int = 0`, `MAX_SESSION_RESUMES: int = 20` 추가.
    - `auto_resume_count`는 재개 승인 시 리셋하되 `session_resume_total`은 세션 전체에서 유지. 20회 초과 시 재승인 없이 최종 차단.
    - 자동 재개 3개 블록(정상 resume, 턴 리밋 예외, 일반 예외) 모두 `session_resume_total` 카운팅 적용.
    - WAIT_FOR_REVIEW → EXECUTING 재진입 시 `auto_resume_count`, `repeated_error_count`, `last_error_sig` 리셋 명시.

- **`commands.py` — `/coordinator` 모드 전환 시 `pending_mode_notification` 누락 수정 (🟡 Low)**:
    - `/agent`, `/ask`, `/plan` 전환에는 모드 전환 알림이 주입되었으나 `/coordinator`에는 누락되어 히스토리 컨텍스트 오염 방지 기능이 미적용된 문제 수정.
    - `"[System: Mode switched to COORDINATOR. Decompose the task into parallel sub-agents. All prior mode restrictions are lifted.]"` 알림 추가.

---

### 🚀 Session 30 (2026-05-07)
- **`state.py` 프롬프트 감사 및 불일치 전면 수정**:
    - **검증(Verifying) 완료 키워드 명시**: `_PLAN_VERIFYING_PROMPT`에 "Verification complete." 출력 지시를 추가하여, 검증 완료 후 에이전트가 "사용자 결정 대기" 상태로 무한 정지하던 버그의 근본 원인을 해결했습니다.
    - **웹 리서치 도구 허용 범위 확대**: `_PLAN_DRAFTING_PROMPT`의 읽기 전용 허용 도구에 `web_search`, `web_fetch`, `deep_research`를 추가하여 초기 계획 수립 시 리서치 역량을 강화했습니다.
    - **`deep_research` 활용 가이드라인**: Base 프롬프트에 단일 턴 매크로 검색 도구인 `deep_research`의 우선 사용을 유도하는 지시를 추가했습니다.
    - **불필요한 따옴표 노이즈 제거**: `_BASE_SYSTEM_PROMPT` 마지막 줄에 남아있던 이스케이프 따옴표(`\"`)를 제거하여 프롬프트 품질을 향상시켰습니다.
    - **`is_plan_executing` 프로퍼티 추가**: `TheseusStateMachine`에 누락되었던 실행 단계 확인용 편의 프로퍼티를 추가했습니다.
- **런타임 크래시 및 의존성 버그 수정**:
    - `theseus_cli.py` 모듈화 과정에서 발생한 **Git 머지 충돌 마커 잔존 버그**를 찾아내 제거하고, 검증 단계 전환 영어 키워드 로직으로 통일하여 런타임 오류를 차단했습니다.
    - `requirements.txt`가 알 수 없는 이유로 손실된 것을 정상 복구하고, Session 26의 `DeepResearchTool` 의존성(`markdownify`, `beautifulsoup4`)이 누락되지 않도록 반영했습니다.
### 🗂️ `theseus_cli.py` 모듈 분리 리팩토링 — `theseus_cli/` 패키지 신설 (2026-05-07)

893줄짜리 단일 파일을 역할별 5개 모듈로 분리하여 God Object 문제를 해결하고 테스트·확장성을 확보했습니다.

#### 신규 파일 구조

```
theseus_cli.py          (893줄 → 230줄, 엔트리포인트만 유지)
theseus_cli/
├── __init__.py
├── context.py          CLIContext 데이터클래스 — 가변 상태(sm, engine, client, 카운터 등) 단일 객체로 묶음
├── ui.py               화면 출력 전담 — print_help, print_status, display_plan, safe_hr, status_mark
├── parsers.py          파싱/프롬프트 조립 — extract_plan_json, parse_plan_feedback, build_feedback_prompt, handle_plan_draft
├── intent.py           LLM 승인 의도 분류기 — llm_is_approval (다국어 지원)
└── commands.py         슬래시 명령어 라우터 — handle_slash_command (CLIContext 수신, bool/str 반환)
```

#### 핵심 설계 결정

- **`CLIContext` 도입** (`context.py`): 슬래시 명령어 처리에 필요한 10개 이상의 가변 상태를 단일 데이터클래스로 묶어 `commands.py`에 전달. 인자 폭발(Parameter Explosion) 없음.
- **`commands.py` 반환 규약**: `(should_continue: bool, new_line: str | None)` 튜플로 `continue`/LLM 전달/미인식 명령어 3가지 경로를 명확히 분리.
- **`theseus_engine/` 레이어 무결성 유지**: `theseus_cli/` 패키지는 프로젝트 루트에 위치, 엔진 레이어가 CLI를 참조하지 않는 단방향 의존성 유지.
- **`ui.py`, `parsers.py`, `intent.py`**: 외부 상태 없는 순수 함수 구조 → 단위 테스트 가능.
- **`print_status()` 신규 추가** (`ui.py`): 현재 모드(이모지 포함)와 권한 레벨을 한 줄로 출력.
    - 표시 시점: 시작 시(`print_help` 내부), `/help`, `/agent`·`/ask`·`/plan`·`/coordinator` 전환 직후, `/rbac` 변경 후.
    - PLAN 모드에서는 현재 Phase(DRAFTING / WAIT_FOR_REVIEW / EXECUTING / VERIFYING)도 함께 표시.
    - `print_help(mode, user_level, plan_phase)` 시그니처 확장 — 호출 시 컨텍스트 인자 전달.

---

### 🌐 LLM 기반 다국어 승인 의도 분류기 도입 — `theseus_cli.py` (2026-05-07)

- **`_llm_is_approval()` async 함수 신규 추가** (기존 `_is_approval_intent()` 하드코딩 키워드 방식 완전 제거):
    - 언어 중립 빠른 필터: 입력 100자 초과 시 즉시 `False` 반환 (LLM 호출 없음).
    - 100자 이하 모호한 입력은 기존 `TheseusLLMClient.stream_message()`로 분류 요청 (`max_tokens=5`).
    - 시스템 프롬프트: "YES 또는 NO 단답만 반환, 조건부 승인(`Yes, but...`)은 NO 처리" 명시.
    - 장애 시 보수적 `False` 폴백 — 의도치 않은 실행 트리거 방지.
- **다국어(i18n) 확장성 확보**: 스페인어("Sí"), 일본어("はい"), 프랑스어("Oui") 등 코드 수정 없이 자동 지원.
- WAIT_FOR_REVIEW 처리부 `if _is_approval_intent(line)` → `if await _llm_is_approval(line, client)` 교체.

---

### 🔧 Plan 모드 안정성 개선 — 루프 트랩 방지 · 자연어 승인 · 모드 컨텍스트 주입 (2026-05-07)

#### 1. 자동 재개 루프 트랩 완전 차단 (`theseus_cli.py`)

- **문제**: `_auto_resume_count` 초과 후 `EXECUTING` 상태 유지 → 사용자 입력 직후 루프 재점화.
    - 재현 경로: 5회 초과 → 카운터 리셋 → 사용자 "기다려봐" 입력 → LLM 텍스트만 응답 → `not tool_called_this_turn == True` → `should_auto_resume = True` 재발화.
- **수정**: `_waiting_for_user: bool` 플래그 추가.
    - 초과 시 `True` 설정, 사용자 입력(`input()`) 수신 시 `False` 해제.
    - `PLAN EXECUTING` 상태에서 `_waiting_for_user == True`이면 자동 재개 차단.
- **WAIT_FOR_REVIEW 강제 강등**: 초과 시 `EXECUTING` → `WAIT_FOR_REVIEW` 상태 전이 + 시스템 프롬프트 즉시 교체.
    - 적용 범위: 정상 auto-resume 블록, 턴 리밋 예외 핸들러, 일반 예외 핸들러 3곳 모두.
    - 재개 방법: 대화로 원인 파악 후 `approve` 입력 → 다시 `EXECUTING` 진입.
- **`/pause`, `/stop` 명령어 추가**: 언제든 수동으로 `WAIT_FOR_REVIEW` 강등 가능.

#### 2. 모드 전환 컨텍스트 오염 방지 (`theseus_cli.py`)

- **문제**: `/agent` 전환 시 시스템 프롬프트는 교체되나 히스토리에 "나는 도구를 쓸 수 없다" 등 과거 페르소나 발언이 잔류 → LLM이 과거 답변에 이끌려 이전 모드처럼 행동.
- **수정**: `_pending_mode_notification: str` 변수 추가.
    - 모드 전환 슬래시 명령어(`/agent`, `/ask`, `/plan`) 처리 시 알림 메시지 장전.
    - 다음 사용자 입력 전송 직전 `actual_line` 앞에 주입 후 클리어.
    - 예: `[System: Mode switched to AGENT. All tools are now available. Ignore any prior restrictions.]`
- **적용 모드**: AGENT, ASK, PLAN 전환 3곳.

#### 3. Plan description 엔지니어링 명세 강제 (`state.py`)

- **`_PLAN_DRAFTING_PROMPT` JSON 스키마 수정**:
    - 메인 태스크 `description` 예시값: `"Engineering spec: target class/function names, key library calls with options, data flow, error handling strategy"`.
    - 서브 태스크 `description` 예시값: `"Engineering spec: exact method/function to modify, inputs/outputs, edge cases to handle"`.
- **RULES 가드레일 추가**: `"The 'description' field MUST NOT be a vague summary. Specify concrete class/function names, library methods with key arguments, and error handling — detailed enough to code from directly."`

#### 4. AGENT 모드 `create_tool` 노출 차단 (`engine_builder.py`)

- **`is_create_allowed` 로직 수정**: 기존 `is_plan_executing or sm.mode == AgentMode.AGENT` → `is_plan_executing` 단독 조건으로 변경.
- `create_tool`이 PLAN EXECUTING 단계에서만 `active_registry`에 포함되어, AGENT 모드에서 호출 시 "tool not found" 처리됨.
- Session 4 설계 원칙("Plan Executing 모드 전용") 코드 레벨 완전 적용.

---

### 🖥️ CLI LLM 프롬프트 영어화 — `theseus_cli.py` (2026-05-07)

- **`theseus_cli.py` — LLM에 전송되는 모든 프롬프트 문자열 영어 전환**:
    - `_build_feedback_prompt()` — Plan 피드백 프롬프트 전문 영어화 (4개 분기 모두).
    - `auto_resume_line` — 시스템 알림, 턴 리밋 재개, 반복 에러 프롬프트 등 7개 항목 영어화.
    - `resume_prompt` — 자동 재개, 도구 에러 복구, 반복 에러 전환 프롬프트 5개 항목 영어화.
    - 승인 메시지(`"승인된 계획을..."`) — Plan approve 시 LLM에 전달되는 2곳 영어화.
    - 완료 감지 키워드 — `"계획 실행 완료"`, `"검증 완료"` 한국어 키워드 제거 → 영어 키워드로 대체.
    - `is_asking_user` — 질문 감지 키워드 `"어떻게"`, `"진행할까요"` 등 → 영어 패턴으로 대체.
- **유지 항목**: `_print_help()`, `_display_plan()`, `print()` 메시지 등 사용자 대면 UI 텍스트는 한국어 유지.

---

### 🔧 도구(Tools) 한국어 → 영어 일괄 전환 — 에이전트 입력 파이프라인 통일 (2026-05-07)

- **대상**: `theseus_engine/tools/core/` 내 16개 파일, ~65건 수정
- **🔴 Critical (description / Field description)**:
    - `memory_tools.py` — 3개 Input 클래스의 `Field(description=...)` 및 3개 Tool의 `description` 전문 영어화.
    - `tool_search_tool.py` — `ToolSearchInput.query`/`top_k` Field, `ToolSearchTool.description` 전문 영어화.
    - `agent_tool.py` — `AgentInput.max_rbac_level`/`inherit_context`/`timeout_seconds` Field 영어화.
- **🟠 High (ToolResult output)**:
    - `bash_tool.py`, `brief_tool.py`, `deep_research_tool.py`, `lsp_tool.py` — 에러/결과 메시지 영어화.
    - `mcp_tools.py`, `skill_tools.py`, `worktree_tools.py` — 성공/실패 메시지 영어화.
    - `web_search_tool.py`, `web_fetch_tool.py` — HTTP 에러 메시지 영어화.
    - `todo_write_tool.py` — 업데이트 결과 메시지 영어화.
    - `task_create_tool.py`, `task_get_tool.py`, `task_list_tool.py`, `task_stop_tool.py` — 태스크 상태 메시지 영어화.
- **🟡 유지 항목**: `tool_search_tool.py`의 `example_queries` 한국어 엔트리 — RAG 임베딩 정확도를 위해 유지.
- **🟢 미수정 항목**: 코드 주석/docstring (LLM 미노출, 개발자 전용).

---

### 🌐 프롬프트 언어 통일 — ALL 영어 시스템 프롬프트 + 동적 출력 언어 감지 (2026-05-07)

- **`state.py` — 시스템 프롬프트 전문 영어화 리팩토링**:
    - 한국어/영어 혼재로 인한 LLM 어텐션 분산 및 코드 스위칭 환각 문제 해결.
    - `_BASE_SYSTEM_PROMPT`에 `# Communication Language` 섹션 신규 추가:
        - 사용자의 마지막 메시지 언어를 자동 감지하여 동일 언어로 응답하도록 지시.
        - 코드 블록, 변수명, 터미널 명령어, JSON 키는 항상 영어 유지.
        - JSON 구조화 출력의 키는 영어, 값은 사용자 언어로 작성.
    - `_AGENT_PROMPT` — 모드 전환 안내 문구 한국어 하드코딩 제거 → 영어 지시로 변환 (에이전트가 사용자 언어로 자동 번역).
    - `_PLAN_DRAFTING_PROMPT` — JSON 스키마 설명 전문 영어 전환:
        - `"한 문장으로 최종 목표 요약"` → `"One-sentence summary of the final goal"` 등 모든 placeholder 영어화.
        - 스키마 상단에 `CRITICAL: JSON keys MUST remain in English, but JSON values MUST be written in the user's language` 규칙 추가.
    - `_PLAN_REVIEW_PROMPT` — 사용자 액션 예시 한국어 제거 → 영어 예시로 통일, 승인 키워드를 사용자 언어 동적 감지로 전환.

- **기대 효과**:
    - LLM 추론 정확도 향상 (영어 학습 데이터 비율 활용 극대화).
    - 토큰 소모 ~30-40% 절감 (한국어 대비 영어의 높은 토큰 효율).
    - 명령(Instruction)과 출력(Content) 언어의 명확한 분리로 에이전트 페르소나 안정화.

---

### 🐛 외부 피드백 반영 — 코드 품질 버그 4종 수정 (2026-05-07)

- **`tool_retriever.py` — 캐시 무효화 로직 수정 (버그 #1)**:
    - `_ensure_indexed()`의 변경 감지 조건을 `len()` 수량 비교에서 `set(이름)` 집합 비교로 교체.
    - 기존: 도구 A 삭제 + 도구 B 추가 시 개수가 같으면 재인덱싱을 건너뛰어 Stale Vector 상태 유지.
    - 수정: `set(t.name for t in current_tools) == set(self._tool_names)` 비교로 이름이 달라지면 즉시 재인덱싱 트리거. 빠른 경로(lock 전)와 double-checked locking(lock 후) 양쪽 모두 수정.

- **`theseus_client.py` — JSON 파싱 실패 시 Silent Failure 제거 (버그 #3)**:
    - LLM이 후행 쉼표 등 잘못된 JSON을 생성했을 때 `args = {}`로 조용히 대체하던 패턴 제거.
    - 수정: `args = {"_parse_error": str(parse_err), "_raw": tc["arguments"][:200]}`으로 에러 정보를 input에 포함. 에이전트가 다음 턴에서 Pydantic validation 에러 메시지를 통해 자신이 JSON을 잘못 생성했음을 인지하고 self-healing 가능.

- **`tool_usage_logger.py` — 동기 파일 I/O 비동기화 (버그 #4)**:
    - `record_tool_call()` 내 `open().write()` 가 이벤트 루프를 블로킹하던 문제 개선.
    - `_write_record_sync()` 헬퍼 분리 후 `record_tool_call_async()`를 신규 추가 — `asyncio.to_thread()`로 파일 I/O를 스레드 풀에 위임. 기존 동기 `record_tool_call()`은 비async 호출처를 위해 유지.
    - `theseus_cli.py`: import를 `record_tool_call_async as record_tool_call`로 교체하고 호출부에 `await` 추가.

- **`theseus_cli.py` — 동일 에러 반복 시 접근 방식 전환 가드레일 추가 (버그 #5)**:
    - 동일한 에러가 2회 연속 발생하면 `_MAX_AUTO_RESUME` 5회를 채우지 않고 즉시 접근 전환 프롬프트 주입.
    - `_last_error_sig`, `_repeated_error_count`, `_MAX_REPEATED_ERRORS = 2` 추가.
    - 반복 에러 감지 시: "현재 방식을 완전히 바꾸거나, 해결이 어렵다면 사용자에게 보고하라"는 강한 가드레일 프롬프트로 교체. 카운터는 감지 직후 리셋.
    - 적용 범위: 정상 auto-resume 블록과 Exception 핸들러 내 PLAN 모드 블록 양쪽 모두.

---

### 📋 Plan 모드 전면 재설계 — 제안서 스타일 + 4단계 파이프라인 + 구조화 피드백 (2026-05-07)

Antigravity(Google DeepMind) Planning Mode 프롬프트 분석을 기반으로 Theseus Plan 모드의 프롬프트, JSON 스키마, 표시 로직, 피드백 시스템을 전면 개선.

#### 핵심 변경 1 — Plan 4단계 파이프라인 (`state.py`)

- **`PlanPhase.VERIFYING` 신규 추가**:
    - Plan 모드 파이프라인을 3단계(Drafting→Review→Executing)에서 **4단계(Drafting→Review→Executing→Verifying)**로 확장.
    - `is_plan_verifying` 편의 프로퍼티 추가. `get_system_prompt()`에 VERIFYING 분기 추가.

- **`_PLAN_DRAFTING_PROMPT` 전면 재작성**:
    - **도구 전면 금지 → 읽기 도구 허용**: `read_file`, `glob`, `grep`, 읽기 전용 bash 사용 가능. 상태 변경 도구만 금지.
    - **Research→Analyze→Plan 3단계 워크플로우** 도입: 코드베이스를 먼저 조사한 뒤 분석, 그 후 계획 수립.
    - **T1/T2/T3 Tier 분류 체계**: 각 메인 태스크를 Impact/Effort 기준으로 Quick Win(T1), Strategic(T2), Architecture(T3)로 분류.
    - **JSON 스키마 대폭 확장**: 기존 `goal`+`tasks[]` 구조에서 다음 필드 추가:
        - `context{current_state, problem_analysis, affected_files, risks}` — 코드베이스 조사 결과
        - `tasks[]{tier, problem, solution, target_files, integration_points, expected_effect}` — 태스크별 문제/해결/효과
        - `verification{test_commands, manual_checks, success_criteria}` — 검증 계획
        - `action_plan{immediate, sequential_dependencies, estimated_turns}` — 실행 순서 계획

- **`_PLAN_REVIEW_PROMPT` 강화 — 반복 승인 루프**:
    - 단순 3옵션(approve/edit/cancel)에서 **반복 수정→재제시→재승인 루프**로 확장.
    - dot notation 피드백 문법 가이드 추가 (아래 "핵심 변경 3" 참조).
    - 리뷰 중 읽기 도구로 추가 조사 허용.

- **`_PLAN_EXECUTING_PROMPT_TEMPLATE` 보강**:
    - **Tier/action_plan 기반 실행 순서 결정** 규칙 추가. T1→T2→T3 순서 또는 `action_plan.immediate` 우선.
    - 진행 상황 보고 형식 구체화: `[Progress] task-N complete (N/total) — <summary>`.
    - 예상외 복잡도 발견 시 실행 중단 의무 명시.

- **`_PLAN_VERIFYING_PROMPT` 신규 추가**:
    - 4단계 검증 체크리스트: 테스트 실행, 변경 파일 리뷰, 회귀 확인, 계획 완료율 비교.
    - 구조화된 출력 포맷: Tests/Changes/Issues found/Plan completion + Next Steps.
    - 사소한 수정(`edit_file`)만 허용, 근본적 설계 결함 시 Drafting 회귀 권고.

#### 핵심 변경 2 — 제안서 스타일 Plan 표시 (`theseus_cli.py`)

- **`_display_plan()` 전면 리디자인**:
    - **Tier별 그룹핑 출력**: `[T1] Quick Win`, `[T2] Strategic`, `[T3] Architecture` 섹션으로 분리.
    - **태스크별 상세 정보 표시**: Problem, Solution, Files, Effect, Integration 각 필드를 라벨과 함께 출력.
    - **Verification Plan / Action Plan 섹션** 추가: 테스트 명령어, 수동 확인 항목, 성공 기준, 실행 순서, 예상 턴 수 표시.
    - **하위 호환**: `tier` 필드 없는 기존 JSON 스키마도 fallback으로 정상 렌더링.
    - `_safe_hr()` 헬퍼 추가: Windows 콘솔 유니코드 인코딩 문제 시 ASCII(`-`) fallback.

- **Executing→Verifying 자동 전환**:
    - "Plan complete" 키워드 감지 시 기존 즉시 완료 대신 **VERIFYING 단계로 자동 전환**.
    - "Verification complete" 감지 시 최종 완료 처리 및 plan state 클리어.
    - auto-resume 로직이 VERIFYING 단계에서도 작동하도록 `PlanPhase.EXECUTING` → `PlanPhase.EXECUTING, PlanPhase.VERIFYING` 튜플 확장.

#### 핵심 변경 3 — 구조화 피드백 시스템 (`theseus_cli.py`)

- **`_parse_plan_feedback()` 신규** — 3레벨 피드백 파싱:

    | 문법 | 예시 | 대상 |
    |---|---|---|
    | `<task-id>: <피드백>` | `task-1: API 대신 CLI로 변경` | 태스크 전체 |
    | `<task-id>.<field>: <피드백>` | `task-1.solution: httpx 사용` | 태스크의 특정 필드 |
    | `<section>.<field>: <피드백>` | `verification.success_criteria: 1초 이내` | 최상위 섹션 필드 |

    - **태스크 필드**: `problem`, `solution`, `target_files`, `expected_effect`, `description`, `tier`, `integration_points`, `title`, `status`
    - **섹션.필드**: `context.{current_state, problem_analysis, affected_files, risks}`, `verification.{test_commands, manual_checks, success_criteria}`, `action_plan.{immediate, sequential_dependencies, estimated_turns}`
    - 유효하지 않은 필드명 입력 시 `None` 반환 → 일반 텍스트 피드백으로 fallback.

- **`_build_feedback_prompt()` 신규** — 파싱 결과를 LLM 프롬프트로 변환:
    - 대상 위치(태스크/섹션 + 필드)를 한국어로 명확히 지정하여 LLM이 정확한 지점만 수정하도록 유도.
    - 기존 `_parse_task_feedback()` + `_build_task_feedback_prompt()` 2개 함수를 대체 및 삭제.

#### 문서 최신화 — `docs/prompt/prompt_architecture_map.md`

- Plan 모드 4단계(Drafting→Review→Executing→Verifying) 파이프라인 반영.
- **Plan JSON 스키마 레퍼런스** 섹션 신규 추가: 전체 필드 구조 및 타입 명세.
- Coordinator 모드 4단계 프롬프트(Decompose/Dispatch/Synthesize/Verify) 문서화.
- 도구 설명 섹션에 `agent_tool.py`, `bash_tool.py`, `tool_search_tool.py` 추가.
- 컨텍스트 관리(`context_compressor.py`) 섹션 추가.
- 상태 전환 흐름도 및 Mermaid 다이어그램 업데이트.

---

### ✨ 파일 수정 Diff 미리보기 — rich 기반으로 구현 (2026-05-07)

- **`theseus_hook_executor.py` — `_show_diff_preview()` 신규 구현**:
    - `write_file` / `edit_file` 도구 실행 전 HITL 승인 요청 직전에 변경 전후를 diff로 터미널에 출력하는 기능 추가.
    - `write_file`: 기존 파일 전체 vs 새 `content` 비교. 신규 파일이면 "신규 파일 생성" 표시. `difflib.unified_diff(n=3)` 사용.
    - `edit_file`: `old_str` vs `new_str` 인라인 비교. 변경 대상 블록만 표시해 노이즈 최소화.
    - **렌더링**: `rich.syntax.Syntax(lexer="diff", theme="monokai")` + `rich.panel.Panel`로 출력. `rich.Console`이 터미널 ANSI 지원 여부 및 Windows 인코딩을 자동 감지하므로 별도 fallback 불필요. Textual이 `rich`를 직접 의존하므로 추가 패키지 설치 없음.
    - **실행 흐름**: `_check_hitl()` → `_show_diff_preview()` (diff 출력) → `[y=허용 / a=항상허용 / 그 외=거부]` 승인 프롬프트.
    - 120줄 초과 diff는 나머지 줄 수만 안내. `rich` 미설치 환경에서는 diff 없이 HITL로 바로 진행(graceful degradation).
    - `import difflib`, `from pathlib import Path` 추가.

---

### 🚨 Hotfix — setup_engine async 전환 후속 버그 수정 (2026-05-07)

- **`agent_tool.py:122` — 서브 에이전트 스폰 즉시 크래시 수정 (🚨 Critical)**:
    - `setup_engine()`을 `async def`로 전환한 후 `AgentTool`이 동적으로 생성하는 서브 에이전트 스크립트 문자열에서 `await` 없이 호출하던 버그 수정.
    - `engine, _ = setup_engine(...)` → `engine, _ = await setup_engine(...)`.
    - 미수정 시: `/coordinator` 모드 또는 `agent` 도구 실행 시 `engine`에 코루틴 객체가 할당되어 `engine.query()` 호출 직후 `AttributeError`로 크래시.

- **`theseus_hook_executor.py` — 레지스트리 순회 중 변경 방지 (⚠️ High)**:
    - `_discover_and_inject_tools()`에서 `retrieve_top_k()` 결과를 순회하며 `active_registry.register()`를 호출하는 도중, OpenHarness 엔진 루프가 동일 레지스트리를 순회 중이면 `RuntimeError: dictionary changed size during iteration` 발생 가능.
    - 주입 대상 목록을 `list comprehension`으로 먼저 확정(`to_inject`)한 뒤 별도 루프에서 일괄 등록하도록 변경. 레지스트리 읽기(필터링)와 쓰기(등록)를 단계 분리.

- **`theseus_cli.py` — 세션 종료 시 비용 로그 미저장 수정 (📌 Medium)**:
    - `cost_tracker.save_async()`가 구현됐음에도 어디서도 호출되지 않아 세션 종료 후 `~/.theseus/cost_log.jsonl`에 비용 데이터가 기록되지 않던 문제 수정.
    - `run_cli()` 루프 탈출 직후 (`"Saving session and exiting..."` 블록) `await CostTracker.get_or_create().save_async()` 추가. 저장 실패 시 세션 종료를 막지 않도록 `try/except` 래핑.

---

### 🔧 temp_di 브랜치 — 코드 품질 개선 일괄 수정 (2026-05-07)

#### Phase 1 — 버그 수정

- **`theseus_client.py` — 디버그 덤프 경로 크로스플랫폼 전환**:
    - `DEBUG_DUMP_DIR`이 특정 Windows 절대 경로(`C:\Users\SSAFY\...`)로 하드코딩되어 다른 환경에서 즉시 크래시되던 문제 수정.
    - `Path.home() / ".theseus" / "debug_dumps"` 기본값으로 변경하고, `THESEUS_DEBUG_DUMP_DIR` 환경변수로 오버라이드 가능하도록 개선. 덤프 기능 자체는 유지.

- **`context_compressor.py` — `_build_summary()` async 중첩 버그 수정**:
    - `_build_summary()`가 `async` 함수임에도 내부에서 `asyncio.get_running_loop()`를 탐지하면 LLM 호출 없이 즉시 구조적 요약으로 fallback하는 버그 수정. CLI 실행 컨텍스트에서 루프가 항상 존재하므로 LLM 요약이 단 한 번도 실행되지 않았음.
    - 잘못된 `try/except asyncio.get_running_loop()` 분기를 제거하고 `await api_client.chat_completion(...)` 직접 호출로 교체.

- **`sessions.py` — 동기 파일 I/O → `asyncio.to_thread()` 래핑**:
    - `save_session_history()` 내 파일 읽기/쓰기가 동기로 구현되어 에이전트 응답 스트리밍 중 이벤트 루프를 블로킹하던 문제 개선.
    - `_serialize_messages()`, `_read_envelope()`, `_write_envelope()` 헬퍼 함수 분리.
    - `save_session_history_async()` 추가 — `asyncio.to_thread()`로 파일 I/O를 스레드 풀에 오프로드하여 블로킹 없이 저장. 기존 동기 함수는 비async 호출처(CLI 종료 핸들러 등)를 위해 유지.

#### Phase 2 — 레거시 코드 정리

- **레거시 파일 3종 삭제**:
    - `theseus_engine/core/structured_planner.py` — Session 3 유산. `state.py` PLAN 모드로 완전 대체됨.
    - `theseus_engine/wrappers/llm_clients/gemini_patch.py` — Session 9 CHANGELOG에 삭제 기록이 있었으나 실제 파일이 남아있어 정리.
    - `theseus_engine/models/schemas.py` — `structured_planner`에서만 사용되던 스키마 파일. 함께 삭제.

- **삭제된 파일 import 잔재 제거**:
    - `theseus_cli.py`: `from theseus_engine.wrappers.llm_clients.gemini_patch import apply_gemini_patch` 및 `apply_gemini_patch()` 호출 제거.
    - `tui_main.py`: 동일한 `gemini_patch` import 블록 제거.
    - `theseus_cli.py`: `save_session_history` → `save_session_history_async`로 교체, 5개 호출부 모두 `await` 추가.

#### Phase 3 — 성능 및 안정성 개선

- **`tool_retriever.py` — `asyncio.Lock` 도입 및 임베딩 LRU 캐싱 (`retrieve_top_k` async 전환)**:
    - `_ensure_indexed()`에 `asyncio.Lock` 기반 double-checked locking 적용. 병렬 도구 실행 시 임베딩 인덱스가 동시에 여러 번 재빌드되는 레이스 컨디션 방지.
    - `retrieve_top_k()`를 `async def`로 전환. 임베딩 인코딩 연산(`model.encode`)을 `asyncio.to_thread()`로 오프로드하여 이벤트 루프 블로킹 제거.
    - 128-entry 수동 LRU 캐시(`_query_cache`, `_query_cache_order`) 추가. 동일 쿼리 재입력 시 임베딩 재계산 없이 캐시에서 즉시 반환. 레지스트리 변경(재인덱싱) 시 캐시 자동 무효화.

- **`engine_builder.py` — `setup_engine()` async 전환 및 호출부 일괄 수정**:
    - `retrieve_top_k()`가 async로 전환됨에 따라 `setup_engine()`을 `async def`로 변경.
    - `theseus_cli.py` 3개 호출부, `cli_main.py` 1개 호출부 → `await setup_engine(...)`.
    - `tui_main.py` `_customize_runtime()` → `async def`로 변경 + `await setup_engine(...)` + 호출부 `await self._customize_runtime()`.

- **`theseus_hook_executor.py`, `tool_search_tool.py` — `retrieve_top_k` 호출부 async 대응**:
    - `_discover_and_inject_tools()` 내 `self._retriever.retrieve_top_k(...)` → `await`.
    - `ToolSearchTool.execute()` 내 `retriever.retrieve_top_k(...)` → `await`.

- **`bash_tool.py` — 좀비 프로세스 방지 (`CancelledError` 처리)**:
    - 코루틴이 취소(`asyncio.CancelledError`)될 때 `process.wait()` 대기 중 정리 로직이 실행되지 않아 하위 프로세스가 좀비로 남는 문제 수정.
    - `except asyncio.CancelledError` 블록 추가 → 취소 시 `_terminate(process, force=True)` 호출 후 예외 재발생(re-raise)하여 정상 취소 흐름 보장.

- **`cost_tracker.py` — `save_async()` 비동기 저장 추가**:
    - `import asyncio` 추가.
    - `save_async()` 메서드 추가 — `asyncio.to_thread(self.save)`로 세션 종료 시 비용 로그를 이벤트 루프 차단 없이 저장 가능하도록 개선.

---

### 🐛 Session 28 Hotfix (2026-05-06)
- **Sessions 26~28 코드 버그 일괄 수정**:
    - **`sessions.py` — 중복 함수 제거 및 `plan_state` 파라미터 연동 수정**:
        - `load_session_history()` 함수가 파일 내에 두 번 정의되어 첫 번째 구현이 완전히 무시되던 문제 해결. 첫 번째(구버전) 정의를 제거하여 하위 호환 로직이 포함된 두 번째 정의만 유지.
        - `save_session_history(plan_state=...)` 파라미터를 받아도 실제로 파일에 쓰지 않던 버그 수정. 기존 파일을 읽어 `plan_state` 키만 덮어씌우는 방식으로 변경하여 `history` 외의 키(예: 다른 메타데이터)도 보존.
    - **`theseus_hook_executor.py` — JSON 변환 실패 시 `str()` fallback 추가**:
        - `dict`/`list` 출력을 `json.dumps()`로 직렬화할 때 예외 발생 시 무시하던 `except: pass`를 `str()` 변환으로 교체하여 Pydantic 검증 에러가 발생하지 않도록 안전성 강화.
    - **`theseus_client.py` — `turn_tool_calls` 미집계 버그 수정**:
        - `turn_tool_calls = []`로 초기화만 되고 스트림 이벤트 루프에서 한 번도 채워지지 않던 버그 수정. `ApiMessageCompleteEvent`의 `content` 블록에서 `tool_use` 타입 블록을 추출하여 도구 이름을 실제로 수집하도록 수정. 이로써 `ModelRouter`가 직전 턴 도구 호출 패턴을 정상적으로 읽어 FAST/REASONING 모델 라우팅이 올바르게 동작함.
        - Pydantic frozen 모델에 `setattr()`로 패칭 시 silently 실패하는 문제에 대해 `object.__setattr__()` fallback을 추가하여 `[TOOL EXECUTION ERROR]` prefix 주입의 신뢰성 향상.
    - **`theseus_cli.py` — Auto-resume 무한루프 방지 + 에러 메시지 중복 주입 제거**:
        - Auto-resume 루프에 `_MAX_AUTO_RESUME = 5` 상한을 추가하여, LLM이 도구 호출 없이 텍스트만 반환하는 상황에서 발생하던 무한루프 차단. 5회 초과 시 사용자 입력 대기로 전환.
        - 예외 발생 시 에러 메시지를 `engine.messages`에 user 역할로 직접 주입하던 로직 제거. 에러 정보는 다음 턴의 `line` 프롬프트 문자열에만 포함하여 히스토리에 동일 에러가 두 번 기록되는 문제 해결.
        - 예외 핸들러(turn limit, 일반 에러)에도 동일한 재시도 카운터를 적용하여 에러 복구 루프도 무한 반복되지 않도록 통제.
    - **`engine_builder.py` — 매 턴 Stats/Cost 리셋 방지 + Hook 이중 등록 제거**:
        - `setup_engine()`이 매 턴 호출될 때마다 `SessionStats.reset()`과 `CostTracker.reset()`이 실행되어 이전 통계가 유실되던 문제 수정. `reset_stats: bool = False` 파라미터를 추가하고, 세션 시작 최초 1회만 `reset_stats=True`로 호출하도록 `theseus_cli.py` 수정.
        - `*_file` glob 매처로 등록한 `AgentHook`과 `write_file`/`edit_file` 개별 등록이 중복되어 해당 도구에 보안 감사가 2회 실행되던 버그 수정. glob 매처를 제거하고 개별 등록만 유지.
    - **`tool_factory.py` — active_registry 등록 시 RBAC 체크 누락 수정**:
        - `create_tool` 실행 후 `active_registry.register(instance)`를 호출할 때 사용자 권한 레벨 체크가 없어 권한이 낮은 사용자도 높은 레벨의 도구를 즉시 사용할 수 있던 보안 버그 수정. `user_rbac_level >= permission_level` 조건을 추가하여 레거시 경로와 서버 경로 모두 RBAC 체크 적용.
    - **`deep_research_tool.py` — `_visited_queries` 메모리 누수 방지**:
        - `_visited_queries` 클래스 변수에 리셋 메서드가 없어 장기 세션에서 이전에 검색한 정상 쿼리가 영구 차단되던 문제 개선. `reset_visited()` 클래스 메서드 추가 및 `_MAX_VISITED = 100` 상한 도달 시 자동 전체 초기화 로직 추가.
    - **`model_router.py` — 싱글톤 초기화 Thread-safety 보강**:
        - `get_model_router()`의 `if _router is None:` 단순 체크를 `threading.Lock()` 기반 double-checked locking으로 교체하여 멀티스레드/비동기 환경에서의 중복 초기화 가능성 제거.

### 🚀 Session 28 (2026-05-06)
- **에이전트 복원력 및 자율 복구 루프 구축 (`theseus_cli.py`, `theseus_hook_executor.py`)**:
    - **자율 복구 루프 (Auto-Resume)**: `AGENT` 및 `PLAN EXECUTING` 모드에서 도구 실행 에러 발생 시, 사용자의 재입력 없이 에이전트가 에러를 스스로 분석하고 다음 턴을 즉시 시작하는 자동 재개 로직 구현.
    - **엔진 예외 메모리 주입**: Pydantic 유효성 검사 에러 등 엔진 내부 예외 발생 시, 에러 메시지를 `user` 역할로 메모리에 자동 주입하여 에이전트가 "자가 수정(Self-correction)"을 시도하도록 개선.
    - **도구 출력 데이터 타입 자동 보정**: `theseus_hook_executor.py`의 `POST_TOOL_USE` 훅에서 도구가 반환하는 `dict` 또는 `list` 데이터를 자동으로 JSON 문자열로 변환하여, Pydantic의 `string_type` 검증 에러를 원천 차단.
- **PLAN 모드 안정성 및 형식 엄격화 (`state.py`, `theseus_cli.py`)**:
    - **Drafting 프롬프트 최적화**: 계획 작성 단계에서 LLM이 순수 JSON 블록만 출력하도록 지침을 단순화하고, 기존의 모순된 안내 문구 포함 요구사항을 제거.
    - **TUI/CLI 안내 로직 분리**: "승인/피드백" 안내 메시지를 모델이 아닌 CLI가 직접 출력하도록 변경하여 파싱 안정성 확보.
    - **출력 형식 강화 (Reinforcement)**: 세션 히스토리가 길어질 경우를 대비해, 작성 모드 진입 시 매 턴마다 출력 형식 제약을 리마인드하는 프롬프트 자동 부착 로직 추가.
- **보안 및 RBAC 권한 체계 고도화 (`engine_builder.py`, `tool_factory.py`)**:
    - **도구별 권한 레벨 존중**: `build_filtered_registry`가 외부 설정뿐만 아니라 도구 클래스 내부의 `permission_level` 속성을 참고하도록 수정하여 핵심 도구의 보안 등급(Lv.2+)을 엄격히 준수.
    - **`create_tool` 가시성 최적화**: 보안 훅 활성화(`HOOK=true`) 상태에서도 `create_tool`이 누락되지 않도록 필수 도구 목록에 등록하되, `AGENT` 모드에서도 Lv.2 이상의 권한을 가진 사용자에게만 노출되도록 조정.
    - **HITL 보안 훅 개선**: `ask_permission` 함수가 "항상 허용(a)" 상태를 정상적으로 처리하도록 수정하고, `create_tool`에 `is_destructive=True` 플래그를 명시하여 보안 감사 대상에 포함.

### 🚀 Session 27 (2026-05-06)
- **Plan Persistence & Auto-Resume 시스템 구현 (`sessions.py`, `theseus_cli.py`)**:
    - **세션 파일 구조 확장**: 기존 flat-list 형식의 세션 파일을 `{"history": [...], "plan_state": {...}}` envelope 구조로 업그레이드. 하위 호환을 유지하여 기존 세션 파일도 정상 로드 가능.
    - **Plan 상태 영속화**: `save_plan_state()` / `load_plan_state()` / `clear_plan_state()` 유틸리티 함수를 신규 구현하여 Plan 모드 진행 상황(계획 JSON, 현재 Phase, 완료된 Task, 마지막 에러)을 디스크에 저장.
    - **Turn Limit 자동 복구**: Plan EXECUTING 중 턴 리밋 에러 발생 시, Plan 상태를 저장한 뒤 `continue`로 `input()` 대기를 건너뛰고 즉시 재개하는 로직 구현. 에이전트에게 "중단된 지점부터 재개하라"는 시스템 프롬프트를 강제 주입.
    - **세션 시작 시 미완료 Plan 탐지**: CLI 시작 시 미완료 Plan이 있으면 사용자에게 재개 여부를 묻고, 승인 시 Plan EXECUTING 모드로 즉시 전환하여 `input()` 없이 자동 실행.
- **Self-Reflection Hook — Two-Tier 자동 코드 검증 (`theseus_hook_executor.py`)**:
    - **POST_TOOL_USE 단계**: `write_file` 또는 `edit_file`로 `.py` 파일이 수정된 직후, 자동으로 구문 검증을 수행하여 에이전트에게 즉시 피드백.
    - **Tier 1 (ast.parse)**: Python 내장 모듈로 치명적 구문 에러(SyntaxError, IndentationError)를 0.01초 만에 감지.
    - **Tier 2 (ruff check)**: `shutil.which("ruff")`로 시스템에 ruff가 설치되어 있는지 자동 감지. 있으면 `ruff check --select=E,F`를 실행하여 미사용 import, 미선언 변수 등 의미론적 에러까지 감지. 없으면 Tier 1만 수행.
    - **에이전트 인지 메커니즘**: 검증 경고를 `payload["tool_output"]`에 자동 추가하여, 에이전트가 다음 턴에서 즉시 에러를 인지하고 코드를 수정하도록 유도.
- **Smart Model Routing — `.env` 기반 지능형 모델 라우팅 (`model_router.py`, `theseus_client.py`)**:
    - **신규 `.env` 키**: `THESEUS_MODEL_FAST` (단순 작업용), `THESEUS_MODEL_REASONING` (추론 작업용), `THESEUS_MODEL_ROUTING` (true/false 토글)을 도입하여 기능별 모델을 분리 관리.
    - **ModelRouter 싱글톤**: 직전 턴의 도구 호출 패턴과 현재 에이전트 모드를 분석하여 FAST/REASONING 모델을 자동 선택. Plan/Coordinator 모드에서는 항상 REASONING 모델 사용.
    - **TheseusLLMClient 연동**: `stream_message()` 내에서 라우팅된 모델로 백엔드를 일시 교체하고, 턴 종료 후 원본 모델로 자동 복원.

### 🚀 Session 26 (2026-05-06)
- **DeepResearchTool 코어 툴 신규 구현 및 웹 서칭 최적화 (`deep_research_tool.py`)**:
    - **통합 매크로 서치 파이프라인**: 1턴에 웹 검색(DuckDuckGo), 병렬 스크래핑(asyncio), HTML 파싱(`BeautifulSoup`), 마크다운 변환(`markdownify`)을 모두 수행하는 `DeepResearchTool` 도입.
    - **무한 루프 방지**: 클래스 레벨 변수 `_visited_queries`를 활용하여 이전에 검색한 키워드로 중복 호출 시 강제 에러 블로킹을 통해 모델이 다른 키워드로 탐색하도록 제약 추가.
    - **토큰 오염 방어**: 불필요한 HTML 태그를 제거하고 Markdown 형식으로 변환하여 토큰 소모를 최소화하고 모델의 추론 정확도 향상.
    - **의존성 추가**: `markdownify>=1.2.2`, `beautifulsoup4>=4.12.0`을 `requirements.txt`에 등록.
- **오픈소스 LLM 툴 에러 인지력 강화 (`theseus_client.py`)**:
    - `is_error=True`인 툴 실행 결과에 대해 모델에 전달하기 전 `[TOOL EXECUTION ERROR]` 접두사를 강제 삽입하여, Gemma 등의 오픈소스 모델이 에러를 성공 텍스트로 오인하지 않도록 명시적 경고 주입.
- **턴 리밋 강제 종료 메모리 주입 버그 수정 (`theseus_cli.py`)**:
    - `ConversationMessage` 임포트 경로 오작동(`ModuleNotFoundError`) 수정 및 `TextBlock` 포맷팅 정상화로 루프 차단 알림이 대화 히스토리에 올바르게 주입되도록 수정.

### 🚀 Session 25 (2026-05-04)
- **파일 생성·수정 실패 근본 원인 수정 및 마크다운 링크 오염 방어**:
    - **이중 권한 프롬프트 제거 (`engine_builder.py`)**: CLI 모드에서 `write_file`·`edit_file`·`bash` 호출 시 `TheseusHookExecutor._check_hitl()`과 `TheseusPermissionChecker.evaluate()`가 각각 사용자 확인을 요청하는 이중 프롬프트 문제 해결. `require_human_confirm=False`로 고정하여 HITL 훅이 단독으로 사람 확인을 담당하고 권한 체커는 RBAC 레벨 체크만 수행하도록 역할 분리.
    - **코드 파일 마크다운 링크 자동 제거 (`file_write_tool.py`, `file_edit_tool.py`)**: LLM이 `from [openharness.tools](http://openharness.tools).base import ...` 같은 마크다운 링크 문법을 Python 코드에 삽입하는 문제 방어. `.py`·`.ts`·`.js`·`.tsx`·`.jsx`·`.sh` 확장자 파일에 한해 `_strip_markdown_links()`를 content·old_str·new_str에 자동 적용하여 잘못된 import 구문 없이 파일이 생성되도록 수정.
    - **시스템 프롬프트 마크다운 링크 금지 규칙 추가 (`state.py`)**: 베이스 프롬프트 및 PLAN EXECUTING 섹션 양쪽에 "파일명·경로·코드에 마크다운 링크 문법(`[label](url)`) 절대 사용 금지" CRITICAL 규칙 추가. 예시(`[sorter.py](http://sorter.py)` → `sorter.py`, `[x.is](http://x.is)_integer()` → `x.is_integer()`) 포함.

### 🚀 Session 24 (2026-05-04)
- **툴 호출 파이프라인 안정화 및 'bool' object is not callable 오류 해결**:
    - **OpenHarness QueryEngine 연동 최적화**: `engine_builder.py`에서 `QueryEngine` 초기화 시 `permission_prompt_func`가 호출 가능한(callable) 객체인지 사전에 검증하여, 불리언 값이 전달될 경우 발생하던 런타임 에러를 방지하였습니다.
    - **HITL 승인 로직 강화 (`theseus_hook_executor.py`)**: `TheseusHookExecutor._check_hitl` 메서드가 `permission_prompt` 콜백에 `tool_name`과 `prompt_msg` 두 개의 인자를 정상적으로 전달하도록 수정하여 `theseus_cli.py`의 `ask_permission` 인터페이스와의 정합성을 맞췄습니다.
    - **유연한 응답 처리**: 승인 콜백이 불리언(`bool`) 값을 반환할 경우(OpenHarness 표준)와 문자열(`str`)을 반환할 경우(TUI/CLI input)를 모두 지원하도록 개선하여 다양한 인터페이스 환경에서의 호환성을 확보하였습니다.
    - **방어적 프로그래밍 적용**: 모든 콜백 호출부에 `callable()` 체크 및 `try...except` 예외 처리를 추가하여 보안 훅 실행 중 에러가 발생하더라도 전체 시스템이 크래시되지 않고 안전하게 차단(Safe-fail)되도록 개선하였습니다.

### 🚀 Session 23 (2026-05-04)
- **'bool' object is not callable 오류 해결**:
*   **'bool' object is not callable 런타임 오류 해결**:
    *   `engine_builder.py`에서 `permission_prompt_func`가 `None`일 때 불리언 값이 할당되어 `QueryEngine`에서 호출 시 에러가 발생하던 문제를 수정하였습니다.
    *   `TheseusHookExecutor`가 `permission_prompt` 콜백을 주입받아 보안 훅 실행 시 올바르게 사용자 승인을 요청할 수 있도록 구조를 개선하였습니다.
*   **vLLM 도구 호출 호환성 확보**:
    *   `--enable-auto-tool-choice` 및 `--tool-call-parser gemma4` 설정을 통해 vLLM 환경에서의 안정적인 도구 사용을 지원합니다.
*   **관측성 및 보안 훅 안정화**:
    *   `THESEUS_ENABLE_AGENT_HOOK=true` 설정 시 파일 시스템 작업에 대한 보안 감사(Security Audit)가 정상적으로 작동함을 확인하였습니다.

### 🚀 Session 22 (2026-05-04)
- **CLI 슬래시 명령어 확장 — /cost · /stats · /coordinator · /help**:
### 변경 파일: `theseus_cli.py`

**배경**: Session 21에서 구현한 CostTracker, SessionStats, Coordinator 모드가 TUI에만 연동되어 있었고, CLI(`theseus_cli.py`)에서는 `/cost`, `/stats`, `/coordinator` 명령어가 슬래시 인터셉터에 등록되지 않아 LLM에게 쿼리로 전달되는 문제 발생.

**추가된 슬래시 명령어**:

| 명령어 | 동작 |
|--------|------|
| `/coordinator` | `AgentMode.COORDINATOR`로 전환. Decompose 단계 프롬프트 활성화 |
| `/cost` | `CostTracker.get_or_create().format_report()` 출력. 모델별 입력/출력 토큰 및 USD 비용 집계 테이블 |
| `/stats` | `SessionStats.get().format_report()` 출력. 툴별 p50/p95 실행 시간, 호출/에러 횟수, RAG 검색 시간 |
| `/help` | `_print_help()` 호출로 전체 명령어 목록 재출력 |

**`_print_help()` 함수 분리**:
- 기존에 `run_cli()` 내부에 `print()` 나열로 작성되어 있던 도움말을 독립 함수로 추출.
- 카테고리 4개로 구조화: `[모드 전환]`, `[도구 및 권한]`, `[지식 베이스]`, `[세션 관리]`, `[기타]`.
- 시작 시 자동 출력(`_print_help()` 단일 호출) 및 `/help` 명령어로 언제든 재확인 가능.

**인코딩 안전 처리**:
- `/cost`, `/stats` 출력 시 `UnicodeEncodeError` 발생 가능성을 고려해 try/except 래핑.
- Windows cp949 터미널 환경에서도 `errors="replace"` 방식으로 깨짐 없이 출력.
- `stats.py`의 `format_report()` 헤더에서 이모지(`📊`, `─`) 제거 → ASCII 문자(`[Stats]`, `-`)로 교체.

**import 추가**: `CoordinatorPhase`, `CostTracker`, `SessionStats` 3종 추가.

### 🚀 Session 21 (2026-05-04)
- **Claude Code 참조 고도화 — Stats · CostTracker · Memory 3-Scope · AgentTool · Coordinator**:
> **참조 출처**: Claude Code (codeaashu/claude-code) 소스 분석 결과를 Theseus 아키텍처에 맞게 재설계하여 구현. 5개 Feature를 구현 우선순위(Stats → CostTracker → Memory → AgentTool → Coordinator) 순으로 진행.


### Feature 5: 인메모리 Stats 히스토그램 [`theseus_engine/observability/stats.py`] [신규]

**목적**: LangSmith 없이도 세션 단위 성능 지표(툴 실행 시간, RAG 검색 시간, LLM 토큰 분포)를 실시간으로 측정.

**핵심 설계 — Reservoir Sampling (Algorithm R)**:
- 512개 샘플 상한으로 메모리 무제한 증가 없이 p50/p95/p99 퍼센타일 계산.
- N번째 관측값이 들어올 때 확률 512/N로 기존 샘플을 교체 → 균등 분포 보장.
- `sorted(reservoir)[int(len*p/100)]` 방식의 경량 퍼센타일 연산.

**신규 클래스**:
- `Histogram`: 단일 메트릭 Reservoir 샘플링 히스토그램. `observe(value)`, `percentile(p)`, `avg/count/min_val/max_val` 프로퍼티.
- `HistogramReport` (dataclass): count, avg, min, max, p50, p95, p99 스냅샷.
- `StatsReport` (dataclass): 툴별 duration/call/error 집계 + RAG/LLM/HITL 지표 포함.
- `SessionStats` (싱글톤): `get()` / `reset()` 클래스 메서드로 접근. `observe(metric, ms)`, `increment(metric, delta)`, `set_gauge(metric, value)` 기본 API.

**툴 타이머 API**:
- `tool_start(tool_name)`: `_tool_timers[name] = time.monotonic()` 저장.
- `tool_end(tool_name, is_error)`: `(monotonic() - start) * 1000` 으로 ms 계산 → `tool.<name>.duration_ms` 히스토그램에 기록. `tool.<name>.call_count` / `error_count` 카운터도 자동 증가.

**연동**:
- `TheseusHookExecutor.execute()`: PRE_TOOL_USE에서 `stats.tool_start()`, POST_TOOL_USE에서 `stats.tool_end(is_error=payload["is_error"])` 호출.
- `TheseusHookExecutor._check_hitl()`: `hitl.prompt_count`, `hitl.always_allow_count`, `hitl.blocked_count` 카운터 연동.
- `ToolRetriever.retrieve_top_k()`: `time.monotonic()` 기준 RAG 검색 전후 계측 → `rag.retrieval_ms` 기록.
- `engine_builder.setup_engine()`: 세션 시작 시 `SessionStats.reset()` 자동 호출.

**보고서**: `format_report()` → CLI `/stats` 명령 출력용 56자 구분선 테이블. 툴별 p50/p95, 호출/에러 횟수, RAG/LLM/HITL 섹션 포함.


### Feature 1: 비용/토큰 추적기 [`theseus_engine/engine/cost_tracker.py`] [신규]

**목적**: 멀티모델 환경(OpenAI·Anthropic·Google)에서 세션 단위 토큰 소비량과 USD 비용을 LangSmith 없이 즉시 집계.

**기본 단가표 (`_DEFAULT_PRICING`)** — USD / 1M tokens:

| 모델 | input | output | cache_read | cache_write |
|------|-------|--------|------------|-------------|
| gpt-4o | 2.50 | 10.00 | 1.25 | - |
| gpt-4o-mini | 0.15 | 0.60 | 0.075 | - |
| gpt-4-turbo | 10.00 | 30.00 | - | - |
| o1 | 15.00 | 60.00 | 7.50 | - |
| claude-opus-4 / 4-5 | 15.00 | 75.00 | 1.50 | 3.75 |
| claude-sonnet-4 / 4-6 | 3.00 | 15.00 | 0.30 | 3.75 |
| claude-haiku-4 | 0.80 | 4.00 | 0.08 | 1.00 |
| gemini-2.5-pro | 1.25 | 10.00 | - | - |
| gemini-2.5-flash | 0.075 | 0.30 | - | - |
| gemini-2.0-flash | 0.10 | 0.40 | - | - |

- `THESEUS_PRICING_TABLE` 환경변수에 JSON으로 단가 오버라이드 가능. 파싱 실패 시 경고 로그만 출력, 기본 단가 유지.

**신규 클래스**:
- `ModelUsage` (dataclass): 모델 한 종류의 input/output/cache_read/cache_creation 토큰 + cost_usd + call_count 누적.
- `SessionCost` (dataclass): 세션 전체 집계 (session_id, started_at, total_cost_usd, total_input/output/cache 토큰, total_tool_calls, model_usage 딕셔너리).
- `CostTracker` (싱글톤): `get_or_create(session_id)` / `reset()` 클래스 메서드.

**핵심 메서드**:
- `record(event)`: dict 또는 OpenHarness `UsageEvent` 객체 모두 처리. 내부에서 `record_usage()` 호출.
- `record_usage(model, input_tokens, output_tokens, cache_read, cache_creation)`: `_canonical_model()`로 모델명 정규화 → `_calculate_cost()` → 모델별/세션 전체 집계 누적. 발생 비용(USD) 반환.
- `_canonical_model(model)`: 모델명 소문자화 후 단가표 키 순회하여 부분 매칭으로 정규화 (예: `"claude-sonnet-4-6-20251015"` → `"claude-sonnet-4-6"`).
- `_calculate_cost()`: `(tokens * rate / 1_000_000)` 4항목 합산, `round(..., 8)` 처리.
- `increment_tool_calls(count)`: `total_tool_calls` 증가.
- `format_report()`: CLI `/cost` 명령용 60자 구분선 테이블. 모델별 입력/출력/캐시/비용, 합계 행, 툴 호출 횟수 출력.
- `save()`: `~/.theseus/cost_log.jsonl`에 JSONL 한 줄 추가. OSError 발생 시 경고 로그만 출력.

**엔진 연동**:
- `TheseusLLMClient.stream_message()`: 스트림 이벤트 중 `ApiMessageCompleteEvent` 감지 → `CostTracker.get_or_create().record_usage(model, input_tokens, output_tokens)` 자동 호출. try/except로 래핑하여 추적 실패가 스트림을 중단하지 않음.
- `engine_builder.setup_engine()`: `tracker = CostTracker.reset()` 초기화 → `tool_metadata["cost_tracker"]` 에 노출.
- **설계 결정**: OpenHarness `QueryEngine`이 자체 내부 `CostTracker`를 보유하나 외부 콜백을 제공하지 않아, LLM Client 스트림 인터셉트 방식을 채택. cache 토큰은 Anthropic Claude 응답에서만 제공되므로 현재는 0으로 집계됨.


### Feature 4: Agent Memory 3단계 스코핑 [`theseus_engine/memory/`] [신규]

**목적**: Claude Code의 `~/.claude/memory/`, `.claude/memory/`, `.claude/memory-local/` 3계층 메모리 구조를 Theseus에 이식. 에이전트가 프로젝트·사용자·로컬 컨텍스트를 지속적으로 기억하도록 지원.

**스코프 설계**:

| 스코프 | 경로 | 공유 범위 | git 추적 |
|--------|------|-----------|----------|
| `user` | `~/.theseus/memory/` | 모든 프로젝트 공통 | 아니오 |
| `project` | `.theseus/memory/` | 프로젝트 팀 전체 | 예 |
| `local` | `.theseus/memory-local/` | 로컬 개인 전용 | 아니오 (gitignore) |

**신규 파일: `theseus_engine/memory/scoped_memory.py`**:
- `MemoryScope` (str Enum): `USER`, `PROJECT`, `LOCAL`.
- `ScopedMemory`: `cwd` 파라미터로 프로젝트 루트 지정 (기본값 `Path.cwd()`). 사용자 홈 디렉터리는 `THESEUS_DATA_DIR` 환경변수 오버라이드 가능.
- `write(scope, filename, content)`: 해당 스코프 디렉터리에 `.md` 파일 저장. `.md` 확장자 자동 추가.
- `read(scope, filename)`: 파일 존재 시 UTF-8 텍스트 반환, 없으면 `None`.
- `delete(scope, filename)`: 파일 삭제, 성공 여부 bool 반환.
- `list_files(scope)`: 스코프 디렉터리의 `*.md` 파일명 목록 반환 (정렬).
- `read_context()`: user → project → local 순으로 모든 스코프를 순회하여 `# Agent Memory` 섹션으로 합산. 시스템 프롬프트 직접 주입용. 파일 없으면 빈 문자열 반환.
- `ensure_gitignore()`: 프로젝트 `.gitignore`에 `.theseus/memory-local/` 미존재 시 자동 추가.

**신규 파일: `theseus_engine/tools/core/memory_tools.py`**:
- `MemoryWriteTool` (`memory_write`): scope/filename/content 입력 → 지정 스코프에 파일 저장. `is_read_only=False`, `is_destructive=False`, `permission_level=1`.
- `MemoryReadTool` (`memory_read`): scope/filename 입력 → 파일 내용 반환.
- `MemoryListTool` (`memory_list`): scope 입력 (`all` 포함) → 스코프별 파일 목록 반환.
- 3종 모두 `ALL_CORE_TOOLS` 및 `theseus_engine/tools/core/__init__.py`에 등록.

**엔진 연동 (`engine_builder.py`)**:
- `ScopedMemory` import 추가.
- `setup_engine()` 초기화 시:
  1. `scoped_memory = ScopedMemory(cwd=Path.cwd())` 생성.
  2. `scoped_memory.ensure_gitignore()` 호출 (최초 1회 `.gitignore` 자동 설정).
  3. `memory_context = scoped_memory.read_context()` 로드.
  4. `sm.get_system_prompt() + "\n\n" + memory_context` 로 시스템 프롬프트에 주입.
  5. `tool_metadata["scoped_memory"]` 로 도구에서 접근 가능하도록 노출.


### Feature 2: AgentTool 컨텍스트 전달 개선 [`theseus_engine/tools/core/agent_tool.py`] [수정]

**목적**: 서브 에이전트 스폰 시 부모 RBAC 레벨·모드·환경 컨텍스트가 무단 권한 상승 없이 안전하게 전달되도록 보장.

**`AgentInput` 신규 필드**:
- `max_rbac_level: Optional[int]`: 서브 에이전트에 허용할 최대 RBAC 레벨 (1~5). 미지정 시 부모 레벨 상속.
- `inherit_context: bool` (기본 `False`): True이면 부모의 `agent_mode` 환경변수를 서브 에이전트에 전달.
- `timeout_seconds: Optional[int]` (기본 `300`): 서브 에이전트 실행 타임아웃 (향후 TaskManager 타임아웃 연동용).

**RBAC 상속 로직**:
```
parent_rbac = context.metadata.get("user_rbac_level", 3)
sub_rbac = min(arguments.max_rbac_level ?? parent_rbac, parent_rbac)
```
- 서브 에이전트 RBAC는 부모 레벨을 초과할 수 없음. 권한 상승(privilege escalation) 차단.

**환경 변수 전파**:
- `THESEUS_SUBAGENT=1`: 서브 에이전트 실행 컨텍스트임을 표시. 향후 로깅/비용 집계 분리에 활용.
- `OPENHARNESS_MODEL`: 지정 모델을 서브 에이전트에 주입.
- `inherit_context=True` 시 `THESEUS_AGENT_MODE` 추가 전파.

**출력 개선**: `ToolResult.metadata`에 `sub_rbac_level`, `parent_rbac_level` 포함. 로그에 RBAC 레벨 차이 기록.

**`engine_builder.py` 연동**:
- `tool_metadata["user_rbac_level"] = user_level`: AgentTool이 부모 RBAC를 읽는 데 사용.
- `tool_metadata["agent_mode"] = sm.mode.value`: 현재 모드 정보 전달.


### Feature 3: Coordinator 모드 [`theseus_engine/models/state.py`, `tui_main.py`] [수정]

**목적**: 복잡한 작업을 병렬 서브 에이전트로 분해·배포·합성·검증하는 4단계 오케스트레이션 파이프라인 모드 도입. Claude Code의 멀티 에이전트 패턴 참조.

**`theseus_engine/models/state.py` 변경**:

1. `AgentMode.COORDINATOR = "Coordinator"` 추가 (기존 ASK/AGENT/PLAN 외 4번째 모드).
2. `CoordinatorPhase` Enum 신규 추가:
   - `DECOMPOSE`: 작업 분해. 병렬 서브태스크 목록 생성.
   - `DISPATCH`: 워커 배포 및 모니터링.
   - `SYNTHESIZE`: 워커 결과 통합 및 병합.
   - `VERIFY`: 최종 결과 검증 및 원본 요구사항 대조.
3. `MODE_DESCRIPTIONS`에 Coordinator 설명 추가.
4. **4개 단계별 전용 시스템 프롬프트** 추가:
   - `_COORDINATOR_DECOMPOSE_PROMPT`: 2~6개 원자적·병렬 서브태스크 분해 → JSON list 출력 → `agent` 툴로 배포 지시.
   - `_COORDINATOR_DISPATCH_PROMPT`: `task_output`으로 진행 모니터링, 실패 워커 재시도/적응 지시.
   - `_COORDINATOR_SYNTHESIZE_PROMPT`: 결과 통합·충돌 해결·요청 범위 내 병합 지시.
   - `_COORDINATOR_VERIFY_PROMPT`: 테스트/검증 실행, 원본 요구사항 대조, 미해결 이슈 솔직하게 보고 지시.
5. `TheseusStateMachine` 개선:
   - `coordinator_phase: Optional[CoordinatorPhase]` 필드 추가.
   - `switch_mode(COORDINATOR)` 시 `coordinator_phase = CoordinatorPhase.DECOMPOSE` 자동 초기화.
   - `set_coordinator_phase(phase)` 메서드 추가 (단계 전환 + 콘솔 출력).
   - `display_mode` 프로퍼티: `"Coordinator/Decompose"` 형태 반환.
   - `get_system_prompt()`: COORDINATOR 모드일 때 단계별 프롬프트 분기 추가.
   - UnicodeEncodeError 방지: `switch_mode()` print 문에 try/except 래핑 (Windows cp949 환경 대응).

**`theseus_engine/tui/tui_main.py` 변경**:
- `CoordinatorPhase` import 추가.
- `action_switch_coordinator()` 메서드 추가: 모드 전환 + 시스템 프롬프트 갱신 + `create_tool` 제외 레지스트리 설정.
- `_sync_permission_mode()`: `AgentMode.COORDINATOR → PermissionMode.FULL_AUTO` 매핑 추가.
- `_cmd_coordinator()` 비동기 핸들러 추가.
- `SlashCommand` 목록에 `coordinator` 등록.
- `theseus_cmd_handlers` 딕셔너리 및 `TheseusInput` 인터셉터 집합 모두에 `"coordinator"` 추가.

**사용 흐름**:
```
/coordinator          → Decompose 단계 시작, 작업 분해 프롬프트 활성화
sm.set_coordinator_phase(CoordinatorPhase.DISPATCH)    → 워커 배포 단계
sm.set_coordinator_phase(CoordinatorPhase.SYNTHESIZE)  → 결과 통합 단계
sm.set_coordinator_phase(CoordinatorPhase.VERIFY)      → 최종 검증 단계
```


### 변경 파일 요약

| 파일 | 변경 유형 | 주요 내용 |
|------|-----------|-----------|
| `theseus_engine/observability/stats.py` | 신규 | Reservoir Sampling Stats 시스템 |
| `theseus_engine/engine/cost_tracker.py` | 신규 | 멀티모델 USD 비용 추적기 |
| `theseus_engine/memory/__init__.py` | 신규 | 메모리 패키지 초기화 |
| `theseus_engine/memory/scoped_memory.py` | 신규 | 3단계 스코프 메모리 관리자 |
| `theseus_engine/tools/core/memory_tools.py` | 신규 | MemoryWrite/Read/List 도구 3종 |
| `theseus_engine/tools/core/agent_tool.py` | 수정 | RBAC 상속, 컨텍스트 전파 강화 |
| `theseus_engine/models/state.py` | 수정 | CoordinatorPhase + COORDINATOR 모드 프롬프트 |
| `theseus_engine/wrappers/hooks/theseus_hook_executor.py` | 수정 | stats.tool_start/end 연동 |
| `theseus_engine/wrappers/llm_clients/theseus_client.py` | 수정 | CostTracker 스트림 인터셉트 |
| `theseus_engine/core/tool_retriever.py` | 수정 | RAG 검색 시간 계측 |
| `theseus_engine/core/engine_builder.py` | 수정 | CostTracker/ScopedMemory 초기화 및 tool_metadata 확장 |
| `theseus_engine/tui/tui_main.py` | 수정 | /coordinator 슬래시 명령어 추가 |
| `theseus_engine/tools/core/__init__.py` | 수정 | 메모리 도구 3종 등록 |

### 🚀 Session 20 (2026-05-04)
- **Tool Calling 고도화 — 보안 강화 · RAG 폴백 · HITL**:

*   **[Task 1] BashTool 보안 패턴 강화 (`execution_validator.py`)**:
    *   기존 Regex 2개(HTTP 변이, 파일시스템 파괴)에 Bash 전용 위험 패턴 4종 추가.
    *   `_BASH_DESTRUCTIVE_PATTERN`: `rm -rf`, `dd if=`, `mkfs.*`, `shred` 등 파일시스템 파괴 명령 탐지.
    *   `_BASH_RCE_PATTERN`: `curl ... | bash`, `eval $(...)`, `base64 -d | sh` 등 원격 코드 실행 패턴 탐지.
    *   `_BASH_PRIVILEGE_PATTERN`: `sudo rm`, `chmod -R 777`, `chown -R root` 등 권한 상승 명령 탐지.
    *   `_BASH_PATH_TRAVERSAL_PATTERN`: `> /etc/`, `> /bin/`, `../../../` 등 시스템 경로 탈출 탐지.
    *   모든 패턴은 `tool_name == "bash"` 일 때만 적용되어 타 툴에 영향 없음. 기존 PRE_TOOL_USE Hook 파이프라인에 자동 연결됨.

*   **[Task 2] ToolSearchTool 구현 및 RAG 폴백 전략 (`tool_search_tool.py`, `engine_builder.py`)**:
    *   신규 파일 `theseus_engine/tools/core/tool_search_tool.py` 생성.
    *   `ToolSearchTool`: 자연어 쿼리로 `full_registry`에서 시맨틱 검색 → 매칭 툴을 `active_registry`에 즉시 주입 → 툴 이름·설명·입력 스키마 반환.
    *   `engine_builder.py`에 RAG 실패 감지 로직 추가: `ESSENTIAL_TOOL_NAMES` 외 유사도 선택이 0개이거나 예외 발생 시 `rag_failed = True` 플래그 설정.
    *   `rag_failed` 시 `ToolSearchTool`을 `active_registry`에 자동 활성화. RAG 성공 시에는 노출하지 않아 불필요한 컨텍스트 낭비 방지.
    *   `tool_metadata`에 `active_registry` 키 추가. `ToolSearchTool`이 런타임에 직접 레지스트리에 접근하여 즉시 주입 가능.
    *   `ALL_CORE_TOOLS` 및 `__init__.py`에 `ToolSearchTool` 등록.

*   **[Task 3] POST_TOOL_USE 동적 주입 쿼리 품질 개선 (`theseus_hook_executor.py`)**:
    *   기존 `tool_output[:500]` 원문 그대로 사용하던 방식을 `_build_injection_query()` 정적 메서드로 대체.
    *   툴 이름 + 입력 키(값 제외, 민감 정보 노출 방지) + 출력 신호(파일 확장자, 에러/파일 미발견/권한/타임아웃 패턴) 조합으로 쿼리 생성.
    *   노이즈 많은 원문 대신 의미 있는 키워드 중심 쿼리 사용으로 시맨틱 검색 정확도 향상.

*   **[Task 4] `is_destructive` / `is_read_only` 플래그 및 HITL 레이어 구현**:
    *   파괴적 툴 3종에 `is_destructive = True` 추가: `BashTool`, `WriteFileTool`, `EditFileTool`.
    *   읽기 전용 툴 3종에 `is_read_only = True` / `is_destructive = False` 추가: `ReadFileTool`, `GlobTool`, `GrepTool`.
    *   `ToolSearchTool`에도 `is_read_only = True`, `is_destructive = False` 명시.
    *   **Security Pipeline Fixes**:
    *   **AgentHook Refinement**: Removed `read_file` from the security auditor's scope (AgentHook) to prevent false-positive blocks that replaced file content with `{"ok": true}`.
    *   **Markdown Robustness**: Added a heuristic unblocker in `TheseusHookExecutor` to handle LLM auditors returning Markdown-wrapped JSON, preventing unexpected security blocks.
    *   **Tool Result Serialization**: Fixed `number_sorter.py` to use `json.dumps()`, resolving Pydantic validation errors in the `ToolResult` model.
    *   **Interactive HITL**: Integrated a "warn-then-override" mechanism for sensitive tools.
    *   `TheseusHookExecutor`에 `_check_hitl()` 비동기 메서드 추가: `is_destructive=True` 툴 실행 전 `permission_prompt` 콜백을 호출하여 사용자 승인 요청.
    *   응답 `y`/`yes`/`1` → 1회 허용, `a`/`always` → 세션 내 `_always_allow` 캐시에 등록(재확인 면제), 그 외 → `HookResult(blocked=True)`로 차단.
    *   `permission_prompt` 콜백 미제공(비대화형 환경) 시 자동 허용하여 기존 자동화 파이프라인과 하위 호환 유지.

### 🚀 Session 19 (2026-05-04)
- **동적 도구 기능 제어 토글 구현**:
*   **동적 도구 검색 및 주입 토글(Toggle) 시스템 구현**:
    *   `THESEUS_DYNAMIC_TOOL_RETRIEVAL` 환경 변수를 통해 엔진의 동적 도구 검색 및 런타임 주입 기능을 전역적으로 온오프할 수 있도록 구현하였습니다.
    *   `setup_engine` 메서드에 `enable_dynamic_tools` 파라미터를 추가하여 프로그래밍 방식으로도 제어가 가능하게 개선하였습니다.
*   **Hook 파이프라인 연동 최적화**:
    *   `TheseusHookExecutor`가 생성 시점에 동적 도구 활성화 여부를 주입받아, `POST_TOOL_USE` 단계에서의 자동 도구 발견(`_discover_and_inject_tools`)을 조건부로 실행하도록 수정하였습니다.
    *   동적 도구 기능 비활성화 시 불필요한 `ToolRetriever` 초기화 및 임베딩 모델 로드를 방지하여 리소스 사용 효율을 높였습니다.

### 🚀 Session 18 (2026-04-29)
- **동적 도구 검색 최적화 및 런타임 주입 시스템 구현**:
*   **런타임 도구 수혈(Runtime Tool Injection) 시스템 구현**:
    *   `POST_TOOL_USE` 훅을 활용하여 도구 실행 결과(`tool_output`)를 실시간 분석하는 로직 추가.
    *   새로운 맥락이 발견되면 `ToolRetriever`를 통해 연관 도구를 찾아 현재 에이전트 레지스트리에 즉시 주입(Inject)함으로써 다단계 작업 중 도구 가용성 문제 해결.
*   **도구 검색 파이프라인(Tool Retriever) 고도화**:
    *   **동적 재인덱싱**: 레지스트리의 도구 변경을 감지하여 재시작 없이도 자동으로 임베딩 인덱스를 갱신하도록 개선.
    *   **키워드 기반 리랭킹**: 쿼리에 포함된 핵심 단어(예: "만들어", "수정", "search")에 가중치를 부여하여 시맨틱 검색의 한계를 보완하는 간이 리랭킹 알고리즘 적용.
*   **시스템 안정성 및 Pydantic 호환성 수정**:
    *   `worktree_tools.py` 등에서 발생하던 `class not fully defined` 에러 해결을 위해 `Optional` 임포트 누락 수정 및 `model_rebuild()` 일괄 적용.
    *   `ToolRetriever` 싱글톤 패턴에서의 레지스트리 참조 동기화 문제 해결.

### 🚀 Session 17 (2026-04-29)
- **Theseus CLI 안정화 및 기능 고도화 (`theseus_cli.py`)**:
    - **비동기 호출 오류 수정**: `maybe_compress` 코루틴 호출 시 `await`를 누락하여 발생하던 런타임 에러를 해결하였습니다.
    - **Gemini 400 에러 해결**: `apply_gemini_patch()` 적용 및 `TheseusLLMClient` 강제 주입을 통해 도구 호출 시 `Name cannot be empty` INVALID_ARGUMENT 에러를 원천 차단하였습니다.
    - **슬래시 명령어 통합 인터셉터 구현**: 명령어를 루프 최상단에서 가로채 처리하는 구조로 개편하여 TUI와의 기능 패리티(Parity)를 맞추고 확장성을 확보하였습니다.
- **로드맵 핵심 명령어 5종 CLI 이식**:
    - **`/validate <tool_name>`**: `ToolValidator`를 연동하여 `custom_tools/` 내 도구의 보안 및 규격을 수동으로 정적 분석할 수 있는 기능을 추가하였습니다.
    - **`/kb <query>`**: 에이전트를 거치지 않고 `RAGService`를 직접 호출하여 지식 베이스의 내용을 즉시 검색하고 원문을 확인할 수 있는 기능을 구현하였습니다.
    - **`/rbac <level>`**: 사용자 권한 레벨을 실시간으로 변경하여 도구 노출 및 실행 권한 테스트가 가능하도록 개선하였습니다.
    - **`/tools`**: 현재 모드와 RBAC 레벨에서 실제 사용 가능한 도구 목록을 시각적으로 확인할 수 있는 기능을 추가하였습니다.
    - **`/ask` / `/plan` / `/agent`**: 에이전트 동작 모드 전환 로직을 CLI 루프에 완벽히 통합하였습니다.
    - **`/approve` / `/reject`**: 향후 비동기 승인 서버 연동을 위한 워크플로우 커맨드 스텁(Stub)을 마련하였습니다.

## [Released]


## [Released]
### 🚀 Session 16 (2026-04-29)
- **Adaptive K — 쿼리 복잡도 기반 동적 슬롯 조정 (`tool_retriever.py`)**:
    - `compute_adaptive_k(query, base_k)` 함수 신규 구현. 정규식으로 다단계 신호(`먼저`, `그런 다음`, `마지막으로` 등)와 복잡도 키워드(`분석`, `리팩터링`, `전체` 등)를 감지하여 k를 동적 조정.
    - 단순 질문 → `base_k // 2` (최소 3), 다단계/복합 요청 → `base_k × 1.5` (최대 16), 일반 → `base_k`.
    - `retrieve_top_k(adaptive=True)` 파라미터 추가. 기본 활성화 상태로 매 쿼리마다 자동 적용.
- **Tool 사용 피드백 루프 (`tool_usage_logger.py`)**:
    - `record_tool_call(query, tool_name)`: 실제 도구 호출 이벤트를 `~/.theseus/tool_usage.jsonl`에 JSONL 형식으로 누적.
    - `merge_feedback_into_examples()`: 누적 로그에서 도구별 쿼리를 집계하여 `TOOL_EXAMPLE_QUERIES`에 자동 병합. `ToolRetriever` 초기화 시 자동 적용되어 사용 패턴이 쌓일수록 검색 정확도가 향상.
    - `get_log_stats()`: 도구별 총 호출 횟수 통계 제공.
    - `theseus_cli.py`: `ToolExecutionStarted` 이벤트에서 `record_tool_call()` 자동 호출.
- **컨텍스트 자동 압축 (`context_compressor.py`)**:
    - `maybe_compress(messages, max_messages=30, keep_recent=10)`: 메시지 수가 임계값 초과 시 오래된 메시지를 요약 1개로 교체, 최근 N개는 원본 유지. 35개 → 11개(요약 1 + 최근 10) 검증 완료.
    - LLM 클라이언트 주입 시 AI 요약, 미주입 시 구조적 압축으로 자동 fallback.
    - `ConversationMessage` 객체 및 `dict` 형식 모두 지원.
    - `theseus_cli.py`: 매 메시지 전송 전 자동 압축 체크 및 적용.
- **코드 정리**:
    - `theseus_engine/tools/tools.py`, `theseus_engine/tools/tool_factory.py` 중복 파일 삭제 (이미 `tools/core/`로 이전 완료).
    - `command_handler.py` import 경로 구 경로 → 신 경로로 수정.
    - `knowledge_tools.py`: `psycopg2` 미설치 환경에서도 import 오류 없이 로드되도록 try/except 처리.

### 🚀 Session 15 (2026-04-29)
- **동적 도구 선택 시스템 (Top-K Tool Retrieval) 구현**:
    - **`ToolRetriever` (`theseus_engine/core/tool_retriever.py`)**: 사용자 쿼리를 기반으로 시맨틱 유사도가 높은 상위 K개 도구를 선별하여 에이전트에 제공하는 인메모리 검색 엔진 구현.
    - **인프라 독립**: 기존 RAGService(PostgreSQL + pgvector) 의존을 제거하고, `sentence-transformers` + `numpy` 코사인 유사도 기반 경량 인메모리 검색으로 전환. 외부 DB 없이 즉시 동작.
    - **비대칭 검색 최적화**: `intfloat/multilingual-e5-small` 모델로 전환. `query:`/`passage:` 프리픽스를 활용하여 짧은 사용자 쿼리 ↔ 긴 도구 설명 간의 비대칭 매칭 정확도를 극대화.
    - **Few-shot 쿼리 보강**: 각 도구에 예상 사용자 발화를 추가하여 임베딩 공간에서의 매칭 품질 향상. (Score: 0.26 → 0.83, 약 3배 이상 개선)
    - **필수 도구 보장(Essential Tools)**: `read_file`, `write_file`, `edit_file`, `bash`, `glob`, `grep`, `ask_user`는 검색 결과와 무관하게 항상 포함.
    - **K 슬롯 분리 (Essential ≠ K 소비)**: 필수 도구가 `k` 슬롯을 소비하지 않도록 `similarity_added` 카운터를 별도로 관리. 이전에는 `len(selected) >= k`로 비교하여 필수 도구가 K 슬롯을 차지하는 버그가 있었으며, `k=8`에 필수 7개가 포함되면 유사도 기반 도구가 1개밖에 추가되지 않는 문제 해결.
    - **Ghost Tool Call 방지**: `_extract_history_tool_names()` 메서드로 이전 대화 히스토리에서 사용된 도구 이름을 추출하여 현재 레지스트리에 강제 포함. LLM이 현재 스키마에 없는 도구를 호출하는 Ghost Tool Call 오류 원천 차단. `ConversationMessage` 객체 및 `dict` 형식 모두 지원.
    - **안전 장치**: `engine_builder.py`에 try/except 래핑 및 fallback 로직 추가. 임베딩 모델 로드 실패 시 전체 레지스트리로 자동 복구.
- **P2 도구 이식 완료**:
    - **Git 워크트리 관리 (`worktree_tools.py`)**: `enter_worktree` / `exit_worktree` 도구 구현. `.theseus/worktrees/` 경로에 격리된 실험 환경 제공.
    - **지능형 브리핑 (`brief_tool.py`)**: 긴 텍스트/대화를 구조적으로 압축하는 `brief` 도구 구현. 향후 LLM 연동 확장 구조 내장.

### 🚀 Session 14 (2026-04-29)
- **OpenHarness 코어 Gemini 3.1 Pro 네이티브 지원 통합**:
    - **문제점**: 이전의 몽키패칭이나 래퍼 방식은 OpenHarness의 내부 리프레시 로직에 의해 무력화되거나 의존성 주입이 복잡해지는 한계가 있었음.
    - **해결**: `OpenHarness/src/openharness/api/openai_client.py`를 직접 수정하여 Gemini의 `thought_signature` / `extra_content`를 코어 레벨에서 자동으로 캡처하고 패치하도록 구현. 이제 어떤 실행 환경(CLI, TUI, API)에서도 Gemini 3.1 Pro가 "순정" 상태로 도구 사용 기능을 지원함.
- **TUI 이벤트 버블링 차단 아키텍처 개선 (`TheseusInput` 도입)**:
    - **문제점**: App 레벨에서 이벤트를 가로채려 시도했으나, 부모 클래스(OpenHarness)와의 Race Condition으로 인해 Theseus 전용 슬래시 커맨드가 바이패스되는 현상 발생.
    - **해결**: 위젯 계층의 최하단인 `Input` 위젯을 상속받은 `TheseusInput` 커스텀 위젯을 구현. 이벤트가 상위(App)로 전달되기 전 위젯 레벨에서 `event.stop()`을 호출하여 OpenHarness로의 이벤트 유출을 물리적으로 완벽 차단.
- **심플 CLI 에이전트 (`theseus_cli.py`) 구축**:
    - TUI의 시각적 복잡함과 의존성 없이 로직에만 집중할 수 있는 가벼운 CLI 인터페이스 개발. 실시간 스트리밍, 세션 관리, 도구 사용 승인(HITL) 기능을 포함하며 코어에 통합된 Gemini 로직을 직접 활용.
- **주요 버그 수정**:
    - `theseus_client.py`: 디버그 덤프 로직 중 `sys` 모듈 임포트 누락으로 인한 `NameError` 및 묵음 에러 해결.
    - `theseus_cli.py`: `.env` 로드 로직 추가 및 OpenHarness 스트림 이벤트 클래스 명칭 불일치(`ToolUseStart` → `ToolExecutionStarted` 등) 수정.
    - 세션 초기화: `thought_signature`가 누락된 과거 오염된 세션 데이터가 400 에러를 유발하지 않도록 `default.json` 초기화.

### 🚀 Session 13 (2026-04-29)
- **Gemini 400 에러 최종 근본 원인 수정 (`patch_assistant_tool_calls` 버그)**:
  - **원인 분석**: `gemini_compat.py`의 `patch_assistant_tool_calls` 함수에서 `_raw_tool_calls`가 있을 때 (`tc_id in raw_tool_calls`) 해당 dict를 그대로 교체하는데, `extra_content`가 `None`으로 수집된 경우 `rebuild_tool_call_dict`가 `extra_content` 키를 아예 포함하지 않아 Fallback이 우회되는 버그가 있었음. 결과적으로 `_raw_tool_calls`가 존재하지만 `extra_content`가 없는 상태로 API에 전달되어 `INVALID_ARGUMENT` 에러 지속 발생.
  - **수정 (`gemini_compat.py`)**: `raw_tool_calls[tc_id]`에 `extra_content` 키가 없는 경우 Fallback `_FALLBACK_EXTRA_CONTENT`를 주입한 복사본으로 교체하도록 로직 개선. 이제 `_raw_tool_calls`의 유무와 관계없이 모든 tool call에 `extra_content`가 보장됨.
- **커스텀 툴 로딩 경로 버그 수정 (`CUSTOM_TOOLS_DIR`)**:
  - `tool_factory.py`의 `CUSTOM_TOOLS_DIR`이 `theseus_engine/tools/custom_tools/`를 가리키고 있었으나 실제 커스텀 툴은 `theseus_engine/custom_tools/`에 저장되어 있어 툴이 전혀 로드되지 않는 버그 수정. `os.path.join(__file__, "..", "custom_tools")`로 경로 수정.
- **`time_weather_tool_v2.py` 입력 모델 명명 규칙 수정**:
  - `ToolValidator`의 입력 모델 명명 규칙(`<ToolClassName>Input`)에 따라 `TimeWeatherInputV2` → `TimeWeatherToolV2Input`으로 클래스명 수정. 이전 이름으로는 검증 실패로 툴 로드가 스킵되고 있었음.
- **`OPENWEATHERMAP_API_KEY` 미설정 안내**: `time_weather_tool_v2.py`가 사용하는 OpenWeatherMap API 키가 `.env`에 없음. 툴 사용 전 `.env`에 `OPENWEATHERMAP_API_KEY=<키>` 추가 필요.

### 🚀 Session 11 (2026-04-28)
- **RAG 지식 베이스(Knowledge Base) 시스템 구현 (PostgreSQL + pgvector)**:
  - `theseus_engine/rag/config.py` [신규]: `.env` 기반의 PostgreSQL, 임베딩, RAG 설정 로더. `dataclass(frozen=True)` 패턴으로 불변 설정 관리.
  - `theseus_engine/rag/database.py` [신규]: pgvector 확장 자동 설치, `knowledge_documents` 테이블/IVFFlat 인덱스 생성, 벡터 CRUD 및 코사인 유사도 검색(`<=>` 연산자) 구현.
  - `theseus_engine/rag/embeddings.py` [신규]: `BaseEmbeddingProvider` 추상 클래스 및 `LocalEmbeddingProvider`(sentence-transformers), `RemoteEmbeddingProvider`(OpenAI) 구현. Lazy-loading 패턴 적용.
  - `theseus_engine/rag/service.py` [신규]: 문서 청킹(Chunking), 임베딩, 적재(Ingestion), 벡터 검색을 통합하는 RAG 비즈니스 로직. 싱글톤 접근자 `get_rag_service()` 제공.
  - `theseus_engine/tools/knowledge_tool.py` [신규]: `search_knowledge_base` (RBAC Lv.1) 및 `ingest_document` (RBAC Lv.2) 에이전트 도구 구현.
  - `theseus_engine/core/engine_builder.py`: KB 도구 2종을 전역 `ToolRegistry`에 등록.
  - `theseus_engine/tui/tui_main.py`: RBAC 권한 맵에 `search_knowledge_base: 1`, `ingest_document: 2` 추가.
  - `requirements.txt`: `psycopg2-binary`, `numpy` 의존성 추가.
- **API 클라이언트 안정성 및 Gemini 호환성 강화 (thought_signature 파싱 버그 해결)**:
  - `theseus_engine/wrappers/llm_clients/gemini_compat.py` [신규]: Gemini 3.1 Pro의 비표준 `thought_signature` / `extra_content` 필드를 추출하고 재주입하며, 과거 세션 복구 시 Fallback을 제공하는 전용 호환성 모듈 신설.
  - `theseus_engine/wrappers/llm_clients/theseus_client.py`: 라우팅/스트리밍 역할만 남기고 Gemini 종속적 로직 분리 (리팩토링). 모든 API 클라이언트 초기화 시 타임아웃 기본값을 `120.0`초로 상향하여 긴 응답 시간으로 인한 `Request timed out` 에러 원천 차단.
  - **🚨 Gemini 400 Bad Request 에러 최종 수정 (Session 12)**: `gemini_compat.py`의 `_FALLBACK_EXTRA_CONTENT`에 사용하던 더미 서명 `"Executing tool call"`이 Google API의 Base64 Protobuf 디코딩 검증을 통과하지 못해 `Corrupted thought signature` 에러를 유발하는 것으로 최종 확인. Google 공식 문서(https://ai.google.dev/gemini-api/docs/gemini-3)에 명시된 공식 더미 문자열 `"context_engineering_is_the_way to_go"`로 교체하여 해결. 아울러 디버깅 목적으로 임시 삽입했던 `theseus_client.py`의 `debug_openai_messages.json` 덤프 코드도 제거하여 코드 정리 완료.

### 🚀 Session 10 (2026-04-28)
- **전체 코드베이스 한글 → 영어 국제화 (i18n)**:
  - `theseus_engine/tools/tools.py`: `DummyTool`, `SystemRebootTool`의 description, Field description, 출력 메시지 영어로 전환.
  - `theseus_engine/tools/tool_factory.py`: `ToolCreatorInput` Field descriptions, `ToolValidator` 전체 에러 메시지(16건), `ToolCreatorTool` 결과 메시지 영어로 전환.
  - `theseus_engine/models/rbac.py`: RBAC 거부/승인/보안정책 메시지 3건 영어로 전환.
  - `theseus_engine/validators/execution_validator.py`: 검증 경고/통과 메시지 영어로 전환.
  - `theseus_engine/validators/query_validator.py`: SQL DDL/DML/Injection 탐지 메시지 영어로 전환.
  - `theseus_engine/validators/analysis_validator.py`: AST 보안 분석 에러 메시지(금지 모듈/함수/던더) 영어로 전환.
- **프롬프트 아키텍처 문서 신규 작성**:
  - `docs/prompt/prompt_architecture_map.md` [신규]: Theseus 전용 프롬프트 파일 위치, 역할, 간단한 설명을 Mermaid 아키텍처 다이어그램과 함께 정리.

### 🐛 Bug Fixes (2026-04-28)
- **TUI 모드 전환 크래시 버그 수정**: `tui_main.py` 파일 내에서 `/agent`, `/plan`, `/ask` 등의 커맨드 실행 시 `build_filtered_registry`를 호출하지만 모듈 상단에 import 되지 않아 발생하던 `NameError` 크래시 버그 수정.

### 🚀 Session 9 (2026-04-28)
- **Phase 4: 관측성(Observability) 연동 — LangSmith 트레이싱 구현**:
  - `theseus_engine/observability/tracer.py` [신규]: Bypass 가능한 중앙 트레이싱 유틸리티 구현.
  - `theseus_engine/wrappers/hooks/theseus_hook_executor.py`: `execute()` 메서드에 `@theseus_traceable` 적용.
  - `theseus_engine/validators/*`: 각 Validator의 `validate()` 메서드에 트레이싱 적용.
  - `theseus_engine/core/engine_builder.py`: `get_tracing_tags()` / `get_tracing_metadata()` 추가.
  - `theseus_engine/tui/tui_main.py`: `submit_message()` 호출 래핑.
  - `requirements.txt`: `langsmith>=0.1.0` 의존성 추가.
- **TUI 사이드바 표시 수정**:
  - `permissions` 필드: `RBAC (Lv.5)` 형태로 표시.
  - `tokens` 필드: API에서 0으로 집계될 경우 `N/A`로 안전하게 표시.

### 🚀 아키텍처 확장 및 리팩토링 (2026-04-28)
- **검증기(Validators) 4종 분리 및 신규 구현**:
  - `AnalysisValidator`: AST 기반 보안 정적 분석기. 기존 `_check_security_violations` 대체.
  - `ExecutionValidator`: HTTP 상태 변경 및 파일 시스템 파괴 작업 감지.
  - `QueryValidator`: SQL DDL/DML 및 인젝션 의심 패턴 감지.
  - `SuggestionValidator`: LLM 기반 코드 품질 리뷰 Stub 구현.
- **Hooks 통합 및 래퍼 구현**:
  - `TheseusHookExecutor` 래퍼 구현: OpenHarness 공식 `HookExecutor` 상속. `PRE_TOOL_USE` 이벤트 시 Validator 연쇄 실행.
  - 중복 구현된 커스텀 훅(`file_hook.py` 등) 완전히 제거.
  - 선택적 에이전트 훅(`THESEUS_ENABLE_AGENT_HOOK`) 동적 등록 로직 추가.
- **LLM 클라이언트 구조 개편 (Monkey Patch 제거)**:
  - `gemini_patch.py` 삭제 및 몽키패치 청산.
  - `TheseusLLMClient` 라우터 신설: `OPENHARNESS_MODEL` 접두사에 따라 `AnthropicApiClient`, `TheseusGeminiClient`, `OpenAICompatibleClient` 등 동적 매핑.
  - `engine_builder.py`, `tui_main.py` 초기화 로직 단순화.

### 🚀 Session 8 (2026-04-28)
- **Theseus 에이전트 프롬프트 종합 리팩토링 (Prompt Engineering v2)**:
  - `state.py`: OpenHarness 원본 + Claude Code 에이전트 프롬프트 비교 분석 후 종합 적용.
  - "읽지 않은 코드를 수정하지 마라", 컨텍스트 자동 압축, RBAC 동적 필터링 인지 등 가드레일 대폭 추가.
  - `tool_factory.py`, `tools.py` 내 도구 설명(description) 고도화.
- **Theseus 엔진 모듈화 및 아키텍처 리팩토링 (Architecture Modularization)**:
  - 거대한 `tui_app.py`, `app.py`를 논리적 단위(`core/`, `tui/`, `models/`, `tools/`, `wrappers/`)로 완벽 분할.
  - 엔트리포인트를 `cli_main.py`와 `tui_main.py`로 명확히 분리.

### 🚀 Session 7 (2026-04-28)
- **TUI 명령어 및 시스템 프롬프트 덮어쓰기 문제 완벽 해결**:
  - Python MRO 기반 `_process_line` 오버라이드 구현.
  - 기존의 위험한 몽키패칭 및 런타임 우회 코드 제거.
  - 디버깅 리포트 `tui_command_registration_issue.md` 작성.

### 🚀 Session 6 (2026-04-27)
- **LLM API 통신 호환성 및 자동 복구(Auto-Recovery) 강화**:
  - Gemini 3.1 Pro 도구 호출(`thought_signature` 누락) 400 에러 해결 (초기 몽키패치 방식).
  - API `ErrorEvent` 발생 시 LLM에게 피드백하여 자가 치유를 시도하는 복구 루프 구축.

### 🚀 Session 5 (2026-04-27)
- **에이전트 보안 체계(Defense in Depth) 강화 및 UX 개선**:
  - 1차 방어: `StructuredPlanner` 시스템 프롬프트 제약 추가. 불필요한 리뷰 스킵 로직.
  - 2차 방어: `ToolValidator._check_security_violations` (AST 분석) 신규 추가.
- **Windows 비동기 셸 실행 버그 수정**:
  - `asyncio.WindowsProactorEventLoopPolicy()` 동적 설정 추가.

### 🚀 Session 4 (2026-04-27)
- **3대 도구 시스템 문제 전면 해결**:
  - Agent 모드 `create_tool` 남발 원천 차단 (Plan Executing 모드 전용으로 제한).
  - OpenHarness 빌트인 37개 도구 자동 등록 및 RBAC 레벨 매핑.
  - 동적 도구 등록 제약(`SAME turn` 금지) 및 절대 경로 사용 규칙 추가.
- **`ToolCreatorTool` permission_level 주입 로직 정규표현식으로 강화**.
- **Pydantic 입력 모델 네이밍 화이트리스트 검증 추가**.

### 🚀 Session 3 (2026-04-27)
- **Pydantic 기반 구조화된 출력(Structured Output) 파이프라인 완성**:
  - `StructuredPlanner` 구현 및 `response_format={"type": "json_object"}` 강제.
- **플랜 스키마 세분화 및 UI 렌더링 개선**:
  - `sub_tasks`, `key_decisions` 등 필드 추가. `[sub-a1b2c3d4]` ID 기반 렌더링.
  - 서브 아이템 단위 수정 인터페이스 (`edit N.M`) 지원.
- **에이전트 시스템 프롬프트 전면 영어화 및 최적화**.
- **기타 변경 사항**:
  - `schemas.py`, `structured_planner.py`, `state.py`, `test_phase2_3.py`, `tool_factory.py`, `query.py`, `time_weather_tool.py` 등 리팩토링 및 에러 래핑 적용.

### 📋 Documentation (2026-04-27)
- `docs/proposals/openharness_unused_features_proposal.md` 신규 작성 (미사용 핵심 모듈 8종 분석 및 로드맵 제안).

### 🚀 Session 2 (2026-04-24)
- **3-Mode 아키텍처 도입**: Ask, Agent, Plan(Drafting, Review, Executing) 다중 레이어 상태 모델.
- **ToolValidator AST 기반 엄격 검증 로직 3종 추가**.
- **OpenHarness 엔진 에러 복구 (Self-Healing) 강화**: `query.py` 툴 실행 에러 래핑.
- **대화 컨텍스트 유지 (Multi-turn Memory Fix)**.

### 🚀 Session 1 (2026-04-24)
- **에이전트 프롬프트 고도화**: 상태별 명확한 역할 부여 및 7가지 가이드라인 추가.
- **메타-툴링 시스템 (Tool Factory)**: `ToolCreatorTool` 및 동적 로딩 구현.
- **동적 권한 제어 (RBAC) 및 레지스트리 필터링**: `TheseusPermissionChecker` 및 `build_filtered_registry` 구현.

## ⚠️ Known Issues / Next Steps
- **Phase 5 (단기)**: Sandbox 도입, Memory System 통합, Hooks + LangSmith 연동 고도화, 세션 저장/복원
- **Phase 6 (중기)**: MCP Client 통합, 멀티 에이전트 (Swarm), Skills & Plugin System
