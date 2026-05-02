# Infrastructure Changelog

인프라 및 서버 런타임 관점의 변경 사항만 별도로 기록합니다.

## [2026-04-30] Server Runtime Alignment - Phase 1

### 서버 엔진 빌더 정렬 (`src/builder/engine.py`)
- 서버 스트리밍 엔진 조립 로직을 기존 read-only 3도구 기반 구조에서 `Theseus` 코어 엔진 계열 구조로 재작성했습니다.
- `EngineBuildContext`를 도입하여 서버가 다음 컨텍스트를 명시적으로 받도록 정리했습니다.
  - `user_level`
  - `project_tool_permissions`
  - `mode`
  - `approval_policy`
  - `user_query`
  - `history_messages`
  - `session_id`
- `TheseusLLMClient`를 사용하도록 변경하여 OpenAI/Gemini 등 멀티 프로바이더 라우팅 구조와 맞췄습니다.
- `TheseusStateMachine`, `ALL_CORE_TOOLS`, `build_filtered_registry`, `TheseusPermissionChecker`, `TheseusHookExecutor` 기준으로 서버 엔진을 조립하도록 변경했습니다.
- 기존 `READ_ONLY_TOOL_ALLOWLIST`를 제거했습니다.
- 서버에서는 대화형 승인 프롬프트를 지원하지 않으므로 approval-required 도구 요청은 `_deny_permission_prompt`로 명시 거절되도록 고정했습니다.
- 초기 단계에서는 서버에서 `create_tool`이 노출되지 않도록 non-`PLAN` 모드에서 제외 처리했습니다.
- 동적 도구 주입(`POST_TOOL_USE` 기반 Runtime Tool Injection)은 이번 단계에서 서버 경로에 아직 활성화하지 않았습니다.

### 스트리밍 라우트 정렬 (`src/routes/stream.py`)
- 스트리밍 라우트가 `SessionContext`를 직접 빌더에 넘기던 구조를 제거하고, `EngineBuildContext`를 만들어 전달하도록 변경했습니다.
- 서버 라우트에서는 초기 단계에 `AgentMode.AGENT`만 강제하도록 고정했습니다.
- `project_tool_permissions`를 라우트 레벨에서 먼저 확정한 뒤 빌더로 넘기도록 변경했습니다.
- `mock` 인증 모드에서는 명시적 프로젝트 도구 권한 맵을 사용하도록 추가했습니다.
- `spring` 모드에서는 프로젝트 도구 권한 조회 서비스가 아직 없으므로, 권한 정보를 확보할 수 없는 경우 `503 Project tool permissions are unavailable`로 fail-fast 하도록 처리했습니다.
- 기존 SSE 이벤트 계약은 유지했습니다.
  - `connected`
  - `chunk`
  - `status`
  - `tool_result`
  - `complete`
  - `error`

### 테스트 및 검증 (`tests/test_stream.py`)
- 스트림 테스트를 새 라우트 흐름에 맞춰 수정했습니다.
- `BillingOutboxRepository.enqueue(...)` 패치 기준으로 테스트를 정리했습니다.
- 권한 조회 실패 시 `503`을 반환하는 fail-fast 테스트 케이스를 추가했습니다.
- **단위 테스트 실행 및 검증 완료**: 프로젝트 가상 환경(`.venv`) 내 종속성을 업데이트하고 `unittest`를 통해 5개 테스트 케이스가 모두 통과함을 확인했습니다.
  - `python -m unittest tests/test_stream.py` (5 passed)

### 현재 상태
- 서버 스트리밍 경로가 더 이상 read-only 3도구 전용 빌더에 묶여 있지 않습니다.
- 서버 엔진 조립 방식이 `Theseus` 코어 구조와 같은 계열로 맞춰졌습니다.
- 단위 테스트를 통해 RBAC 필터링 및 Fail-fast 로직의 정상 작동을 확인했습니다.
- 다만 `spring` 모드의 실제 프로젝트별 도구 권한 조회 레이어는 아직 미구현 상태입니다.

### 다음 작업
- Spring 연동용 `project_tool_permissions` 조회 서비스 구현
- 멀티턴 세션 / 컨텍스트 압축 서버 이관
- Plan 모드 및 `create_tool` 서버 이관
