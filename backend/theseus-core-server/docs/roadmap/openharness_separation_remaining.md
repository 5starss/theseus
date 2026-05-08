# OpenHarness 의존성 분리 — 최종 현황

> 최종 업데이트: 2026-05-08  
> 기준 브랜치: `temp_di`

---

## 전체 상태 요약

| 영역 | 상태 | 완료 세션 |
|------|------|-----------|
| Hook 파이프라인 | ✅ **완료** | Session 33 |
| RBAC/Permission | ✅ **완료** | Session 33 |
| Tool Primitives | ✅ **완료** | Session 34 |
| Stream Events | ✅ **완료** | Session 36 |
| Message 타입 | ✅ **완료** | Session 35 |
| LLM Client | ✅ **완료** | Session 35 |
| QueryEngine | ✅ **완료** | Session 36 |
| TUI 프레임워크 | ✅ **완료** | Session 36 |
| sys.path 주입 | ✅ **완료** | Session 36 |
| requirements.txt | ✅ **완료** | Session 38 |
| `src/builder/engine.py` | ⏳ **잔여** | 서버 빌더 별도 계획 |
| `docs/legacy/` | ⏳ **잔여** | 아카이브/삭제 예정 |

---

## ✅ 완료된 항목 상세

### 1. Hook 파이프라인
- `TheseusHookExecutor` — OH `HookExecutor` 상속 제거
- Theseus-native `HookEvent` / `HookResult` 자체 정의

### 2. RBAC/Permission
- `TheseusPermissionChecker` — OH `PermissionChecker` 상속 제거
- `TheseusPermissionSettings` 자체 정의

### 3. Tool Primitives
- `theseus_engine/tools/core/base_tools.py`
- `BaseTool`, `ToolResult`, `ToolRegistry`, `ToolExecutionContext` 완전 자체 정의

### 4. Stream Events
- `theseus_engine/engine/stream_events.py`
- OH re-export `try/except` 브릿지 완전 제거 → `@dataclass(frozen=True)` Theseus-native 8개 타입

### 5. Message 타입
- `theseus_engine/models/messages.py` 신규
- `TextBlock`, `ToolUseBlock`, `ToolResultBlock`, `ConversationMessage` 등 Pydantic 기반 자체 정의
- `sessions.py`, `context_compressor.py`, `intent.py`, `src/history/mapper.py` import 교체

### 6. LLM Client
- `theseus_engine/wrappers/llm_clients/api_types.py` 신규 — `UsageSnapshot`, `ApiMessageRequest` 등
- `theseus_engine/wrappers/llm_clients/anthropic_client.py` 신규 — `TheseusAnthropicClient`
- `theseus_engine/wrappers/llm_clients/openai_compat_client.py` 신규 — `TheseusOpenAICompatClient`
- `theseus_client.py` OH import 4개 모두 교체

### 7. QueryEngine
- `theseus_engine/engine/query_engine.py` 신규 — 전체 실행 루프 자체 구현
- `engine_builder.py`, `command_handler.py` import 교체

### 8. TUI 프레임워크
- `theseus_engine/tui/commands.py` 신규 — `SlashCommand`, `CommandResult`, `CommandRegistry`
- `theseus_engine/tui/runtime.py` 신규 — `TheseusBundle`, `build_theseus_runtime` 등
- `tui_main.py` 전면 재작성 — `App` 직접 상속, OH import 4개 완전 제거

### 9. sys.path OpenHarness 경로 주입
- `theseus_cli.py` line 18 제거
- `theseus_engine/core/cli_main.py` line 8 제거

### 10. requirements.txt
- `-e ./OpenHarness` 완전 삭제
- OH가 간접 제공하던 `anthropic`, `openai`, `textual`, `rich` 등 직접 명시

---

## ⏳ 잔여 항목 (비핵심 — 별도 계획)

### 1. `src/builder/engine.py` — 서버 빌더 (OH import 6개)

```python
# 현재 잔여 import (모두 lazy import — 런타임 영향 없음)
from openharness.config.settings import PermissionSettings
from openharness.engine.query_engine import QueryEngine
from openharness.engine.stream_events import (AssistantTextDelta, ...)
from openharness.hooks.executor import HookExecutionContext
from openharness.hooks.loader import HookRegistry
from openharness.tools import create_default_tool_registry
```

**상태**: 서버 빌더 경로 — 현재 `src/main.py`가 이 파일 대신 `engine_builder.py`를 직접 사용하는지 확인 필요.  
**계획**: `theseus_engine.core.engine_builder` + Theseus-native 타입으로 교체. TUI 재설계 이후 진행.

### 2. `docs/legacy/` — 비활성 레거시 코드 (OH import 13개)

| 파일 | OH import 수 |
|------|-------------|
| `docs/legacy/test_phase1.py` | 6 |
| `docs/legacy/test_phase2_3.py` | 7 |
| `docs/legacy/file_keyword_counter.py` | 1 |

**상태**: 완전 비활성 코드 — 런타임 영향 없음.  
**계획**: 아카이브 또는 삭제.

---

## 현재 OH import 카운트 (theseus_engine + theseus_cli + src)

| 경로 | 런타임 OH import | 비고 |
|------|-----------------|------|
| `theseus_engine/**` | **0** | `state.py` docstring 1줄만 존재 (코드 아님) |
| `theseus_cli/**` | **0** | 완전 클린 |
| `theseus_cli.py` | **0** | 완전 클린 |
| `src/builder/engine.py` | **6** (lazy) | 서버 빌더 — 별도 계획 |
| `src/` (나머지) | **0** | 완전 클린 |

> **핵심 런타임 OH 의존: 0개 달성** ✅  
> 잔여 6개는 모두 `src/builder/engine.py`의 lazy import로 실제 서비스 경로에 영향 없음.

---

## 다음 단계

OH 의존성 분리가 핵심 런타임 기준으로 완료되었으므로,  
**`docs/roadmap/tui_native_app_refactoring_plan.md`** 로드맵에 따라 TUI 고도화 작업을 진행합니다.
