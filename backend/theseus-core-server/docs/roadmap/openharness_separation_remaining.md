# OpenHarness 의존성 분리 — 잔여 작업 목록

> 작성일: 2026-05-07  
> 기준 브랜치: `temp_di`

---

## 현재 상태 요약

| 영역 | 상태 | 비고 |
|------|------|------|
| Hook 파이프라인 | **완료** | `TheseusHookExecutor` — OH 상속 제거, Theseus-native `HookEvent`/`HookResult` |
| RBAC/Permission | **완료** | `TheseusPermissionChecker` — OH `PermissionChecker` 상속 제거 |
| Tool Primitives | **완료** | `base_tools.py` — `BaseTool`, `ToolResult`, `ToolRegistry` 자체 정의 |
| Stream Events | **완료** | Theseus-native frozen dataclass — OH re-export 브릿지 제거 |
| LLM Client | **완료** | `api_types.py`, `anthropic_client.py`, `openai_compat_client.py` 신규 — OH 의존 0개 |
| QueryEngine | **완료** | `theseus_engine/engine/query_engine.py` 신규 — OH 의존 0개 |
| TUI | **완료** | `tui_main.py` — `App` 직접 상속, `commands.py`/`runtime.py` 신규 — OH 의존 0개 |
| Message 타입 | **완료** | `theseus_engine/models/messages.py` 신규 — OH 의존 0개 |

---

## 잔여 OH import 전체 목록

### 1. LLM Client (`theseus_engine/wrappers/llm_clients/theseus_client.py`)

**의존 모듈 6개 — 가장 복잡한 단일 파일**

```
from openharness.api.client import (
    ApiMessageRequest, ApiStreamEvent, SupportsStreamingMessages,
    AnthropicApiClient, ApiTextDeltaEvent, ApiMessageCompleteEvent,
)
from openharness.api.openai_client import (
    OpenAICompatibleClient,
    _convert_messages_to_openai, _convert_tools_to_openai,
    _token_limit_param_for_model, _strip_think_blocks,
)
from openharness.engine.messages import (
    ConversationMessage, ContentBlock, TextBlock, ToolUseBlock,
)
from openharness.api.usage import UsageSnapshot
```

**작업 내용:**
- `TheseusLLMClient`가 직접 Anthropic/OpenAI SDK를 호출하도록 리팩터링
- OH의 `ApiMessageRequest` → Theseus-native request dataclass 정의
- OH의 `OpenAICompatibleClient` 내부 변환 함수 4개(`_convert_messages_to_openai` 등) Theseus로 이식
- `ConversationMessage`, `TextBlock`, `ToolUseBlock` → Theseus message 타입으로 교체 (Task 4와 연동)
- `UsageSnapshot` → Theseus-native 정의

**난이도:** 높음 | **우선순위:** P1 (다른 모듈의 전제 조건)

---

### 2. QueryEngine (`theseus_engine/core/engine_builder.py`, `command_handler.py`)

```
# engine_builder.py:5
from openharness.engine.query_engine import QueryEngine

# command_handler.py:1
from openharness.engine.query_engine import QueryEngine
```

**작업 내용:**
- `QueryEngine`을 Theseus-native로 재구현하거나 래핑
- 핵심 인터페이스: `submit_message(text) -> AsyncIterator[StreamEvent]`, `set_system_prompt(prompt)`
- Tool 실행 루프, Permission 체크, Hook 실행을 Theseus 파이프라인으로 직접 구현
- 완료 시 `stream_events.py`의 OH re-export를 Theseus-native 정의로 전환 가능

**난이도:** 매우 높음 | **우선순위:** P1 (최종 목표)

---

### 3. Message 타입 (`ConversationMessage`, `TextBlock`, `ToolUseBlock` 등)

```
# sessions.py:5
from openharness.engine.messages import ConversationMessage

# context_compressor.py:119 (lazy import)
from openharness.engine.messages import ConversationMessage, TextBlock

# theseus_cli/intent.py:27 (lazy import)
from openharness.engine.messages import ConversationMessage, TextBlock
```

**작업 내용:**
- `theseus_engine/models/messages.py` (신규) 생성
- `ConversationMessage(role: str, content: list[ContentBlock])` — frozen dataclass
- `ContentBlock` = `TextBlock | ToolUseBlock | ToolResultBlock`
- `TextBlock(type="text", text: str)`, `ToolUseBlock(type="tool_use", id: str, name: str, input: dict)`
- `sessions.py`, `context_compressor.py`, `intent.py` import 변경

**난이도:** 중간 | **우선순위:** P2 (LLM Client와 동시 진행 가능)

---

### 4. API Client 타입 (`theseus_cli/intent.py`)

```
# intent.py:26 (lazy import)
from openharness.api.client import ApiMessageRequest, ApiTextDeltaEvent
```

**작업 내용:**
- `intent.py`의 LLM 호출을 `TheseusLLMClient.generate()`로 교체
- OH `ApiMessageRequest` 직접 생성 대신 `TheseusLLMClient` 인터페이스 사용
- Task 1(LLM Client) 완료 후 자동으로 해결 가능

**난이도:** 낮음 | **우선순위:** P3 (Task 1 이후)

---

### 5. TUI 프레임워크 (`theseus_engine/tui/tui_main.py`)

```
from openharness.ui.textual_app import OpenHarnessTerminalApp
from openharness.ui.runtime import build_runtime, start_runtime, handle_line
from openharness.engine.query import MaxTurnsExceeded
from openharness.commands.registry import SlashCommand, CommandResult
```

**작업 내용:**
- `OpenHarnessTerminalApp` 상속 → Theseus-native Textual App으로 교체
- `build_runtime`, `start_runtime`, `handle_line` → Theseus 자체 런타임 루프 구현
- `MaxTurnsExceeded` → Theseus-native exception 정의
- `SlashCommand`, `CommandResult` → Theseus command 레지스트리 정의
- `sys.path.insert(0, ... / "OpenHarness" / "src")` 제거

**난이도:** 높음 | **우선순위:** P2

---

### 6. Stream Events 브릿지 전환 (`theseus_engine/engine/stream_events.py`)

```
try:
    from openharness.engine.stream_events import (
        AssistantTextDelta, AssistantTurnComplete, ...
    )
except ImportError:
    # Theseus-native 폴백 (이미 구현됨)
```

**작업 내용:**
- QueryEngine(Task 2) 완료 후, OH re-export 제거하고 Theseus-native 폴백을 기본으로 전환
- `try/except` 블록 제거, Theseus 정의만 남김

**난이도:** 낮음 | **우선순위:** P3 (Task 2 이후 자동)

---

### 7. `sys.path` OpenHarness 경로 주입 제거

```
# theseus_cli.py:18
sys.path.insert(0, str(PROJECT_ROOT / "OpenHarness" / "src"))

# cli_main.py:8
sys.path.insert(0, str(PROJECT_ROOT / "OpenHarness" / "src"))

# tui_main.py:9
sys.path.insert(0, str(PROJECT_ROOT / "OpenHarness" / "src"))
```

**작업 내용:**
- 모든 OH import가 제거된 후 `sys.path` 주입 삭제
- 최종 단계에서 일괄 처리

**난이도:** 낮음 | **우선순위:** P3 (최후 정리)

---

### 8. 비활성 코드 (docs/legacy, src/builder, tests)

| 파일 | OH import 수 | 상태 |
|------|-------------|------|
| `docs/legacy/test_phase1.py` | 5 | 레거시 테스트 |
| `docs/legacy/test_phase2_3.py` | 7 | 레거시 테스트 |
| `docs/legacy/file_keyword_counter.py` | 1 | 레거시 도구 |
| `src/builder/engine.py` | 6 | 서버 빌더 (별도 경로) |
| `src/history/mapper.py` | 1 | 서버 히스토리 |
| `tests/test_markdown_to_pdf.py` | 1 | 테스트 |

**작업 내용:**
- `docs/legacy/` — 삭제 또는 아카이브 (비활성 코드)
- `src/builder/engine.py` — 서버 배포 경로, 별도 분리 계획 필요
- `tests/` — 활성 코드 분리 완료 후 import 변경

**난이도:** 낮음 | **우선순위:** P3

---

## 권장 실행 순서

```
Phase 1 (P1) — 핵심 런타임
├── Task 3: Message 타입 자체 정의 (messages.py)
├── Task 1: LLM Client OH 의존 제거 (theseus_client.py)
└── Task 2: QueryEngine Theseus-native 구현

Phase 2 (P2) — UI/UX 계층
└── Task 5: TUI OH 프레임워크 분리 (tui_main.py)

Phase 3 (P3) — 정리
├── Task 4: intent.py OH import 제거
├── Task 6: stream_events.py 브릿지 → native 전환
├── Task 7: sys.path OpenHarness 경로 제거
└── Task 8: 비활성 코드 정리/삭제
```

---

## 의존성 그래프

```
QueryEngine (OH)
  ├── stream_events (브릿지)
  ├── ConversationMessage / TextBlock (OH)
  │     ├── sessions.py
  │     ├── context_compressor.py
  │     └── intent.py
  └── theseus_client.py
        ├── ApiMessageRequest, ApiStreamEvent (OH api.client)
        ├── OpenAICompatibleClient (OH api.openai_client)
        ├── ConversationMessage, TextBlock, ToolUseBlock (OH engine.messages)
        └── UsageSnapshot (OH api.usage)

TUI (OH)
  ├── OpenHarnessTerminalApp (OH ui.textual_app)
  ├── build_runtime, start_runtime, handle_line (OH ui.runtime)
  ├── MaxTurnsExceeded (OH engine.query)
  └── SlashCommand, CommandResult (OH commands.registry)
```

> **핵심 병목**: `theseus_client.py`와 `QueryEngine`이 OH 의존의 ~70%를 차지.  
> Message 타입을 먼저 정의하면 두 모듈의 분리가 동시에 가능해짐.
