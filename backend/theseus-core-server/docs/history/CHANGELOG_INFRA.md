# Infrastructure Changelog

인프라 및 서버 런타임 관점의 변경 사항만 별도로 기록합니다!

## [2026-05-04] Plan Server Migration - Phase 1

### Plan 영속 모델 추가 (`src/db/models.py`)
- Core Server 로컬 DB에 `ToolPlan` 모델을 추가했습니다.
- 주요 필드는 다음과 같습니다.
  - `project_id`
  - `chat_session_id`
  - `status`
  - `goal`
  - `content`
  - `feedback`
  - `executing_started_at`
  - `executing_by_user_id`
- Plan 상태는 `drafting`, `wait_for_review`, `approved`, `rejected`, `executing`를 사용합니다.

### Plan 전용 패키지 및 스키마 신설 (`src/plan/`)
- `src/plan/schemas.py`를 추가해 Plan API 입출력 모델을 정의했습니다.
- `src/plan/service.py`를 추가해 상태 전이, 실행 바인딩, 복구 로직을 분리했습니다.
- `StructuredPlan`은 기존 `src/auth/schemas.py` 정의를 재사용하도록 연결했습니다.

### Plan 생명주기 API 추가 (`src/routes/plan.py`, `src/main.py`)
- 다음 엔드포인트를 Core Server에 추가했습니다.
  - `POST /api/v1/plans`
  - `GET /api/v1/plans/{plan_id}`
  - `GET /api/v1/sessions/{chat_session_id}/plans`
  - `PATCH /api/v1/plans/{plan_id}/submit`
  - `PATCH /api/v1/plans/{plan_id}/approve`
  - `PATCH /api/v1/plans/{plan_id}/reject`
  - `PATCH /api/v1/plans/{plan_id}/execute`
- `main.py`에 `plan.router`를 등록했습니다.

### 실행 상태 전이 및 동시성 제어 (`src/plan/service.py`)
- `approved -> executing` 전이만 허용하도록 제한했습니다.
- 동일 `chat_session_id` 내에서 이미 다른 플랜이 `executing` 상태이면 `409 Conflict`를 반환하도록 구현했습니다.
- 실행 전환 시 `executing_started_at`, `executing_by_user_id`를 기록하도록 했습니다.

### 스트림 경로 Plan 바인딩 추가 (`src/routes/stream.py`)
- `/api/v1/stream`에 선택적 `plan_id` 쿼리 파라미터를 추가했습니다.
- `plan_id`가 주어지면 다음 조건을 이중 검증합니다.
  - `project_id` 일치
  - `chat_session_id` 일치
  - `status == executing`
- Plan이 바인딩된 경우 엔진 모드를 `Agent`가 아니라 `Plan`으로 전환해 실행하도록 연결했습니다.
- 스트림 종료 시 `finally`에서 현재 실행 바인딩과 일치하는 경우에만 `executing -> approved`로 복구하도록 구현했습니다.

### `create_tool` 런타임 가드 추가 (`src/builder/engine.py`, `theseus_engine/wrappers/hooks/theseus_hook_executor.py`)
- `EngineBuildContext`에 `plan_id`, `plan_content`를 추가했습니다.
- Plan 바인딩이 있는 경우 Theseus 상태 머신을 `Plan/Executing` 프롬프트로 강제 초기화하도록 연결했습니다.
- Hook executor에 pre-tool guard 주입 지점을 추가했습니다.
- `create_tool` 호출 시 DB에서 해당 `plan_id`가 여전히 `executing` 상태인지 최종 확인하고, 아니면 hook 단계에서 즉시 차단하도록 구현했습니다.

### DB 스키마 부트스트랩 경로 추가 (`src/db/postgres.py`, `src/main.py`, `scratch/create_db.py`, `README.md`)
- Alembic이 없는 현재 구조를 유지하면서 `init_db()`를 추가했습니다.
- 서버 기동 시 `init_db()`가 자동 실행되어 `tool_plans` 포함 전체 메타데이터를 생성하도록 했습니다.
- 수동 생성용 `scratch/create_db.py`도 동일 경로를 사용하도록 변경했습니다.
- README에 DB 스키마 초기화 절차를 추가했습니다.

### 테스트 추가 (`tests/test_plan_lifecycle.py`, `tests/test_plan_concurrency.py`, `tests/test_plan_stream.py`)
- Plan 상태 전이 테스트를 추가했습니다.
- 동일 세션 내 복수 플랜 실행 전환 시 `409`를 검증하는 테스트를 추가했습니다.
- `/stream?plan_id=...` 경로의 세션 불일치 차단과 종료 후 `approved` 복구 테스트를 추가했습니다.

### 검증 상태
- 변경 파일 기준 `py_compile` 문법 검증은 통과했습니다.
- `unittest` 실실행은 현재 로컬 Python 환경에 `pydantic` 미설치로 완료하지 못했습니다.
- 실제 DB 연결 및 API 동작 검증은 런타임 의존성 설치 후 추가 확인이 필요합니다.

## [2026-05-04] Session & History Layer - Phase 1

### 세션/히스토리 설정 추가 (`src/config.py`)
- Spring 내부 히스토리 저장 엔드포인트 설정값 `SPRING_BOOT_INTERNAL_HISTORY_MESSAGES_URL`를 추가했습니다.
- 기본값은 `http://localhost:8080/api/internal/history/messages`로 고정했습니다.

### 히스토리 패키지 신설 (`src/history/`)
- 서버 런타임에서 Spring `ChatSession` / `ChatMessage`를 재사용하기 위한 history 전용 패키지를 추가했습니다.
- 다음 구성요소를 분리했습니다.
  - `client.py`: Spring chat message 조회/저장 클라이언트
  - `schemas.py`: 히스토리 조회/저장 payload 스키마
  - `mapper.py`: Spring message record → 엔진 history message 변환기
  - `service.py`: load/compress/persist orchestration
- 저장 계약은 단순 assistant text 전용이 아니라 다음 필드를 받는 일반 메시지 계약으로 확장했습니다.
  - `senderType`
  - `messageType`
  - `contentType`
  - `toolId`
  - `content`

### 스트리밍 세션 계약 변경 (`src/routes/stream.py`)
- `/api/v1/stream` 요청에 `chat_session_id`를 필수 쿼리 파라미터로 추가했습니다.
- 기존 임시 세션 키 `project_id:user_id`를 라우트 계약에서 제거하고, 엔진 `session_id`는 `chat_session_id` 기반으로 전달되도록 변경했습니다.
- 스트림 시작 전 Spring 히스토리를 로드하고, 압축 후 `EngineBuildContext.history_messages`에 주입하도록 연결했습니다.
- 스트림 종료 후에는 assistant 최종 텍스트만 저장하고, progress/chunk 이벤트는 영속 저장하지 않도록 유지했습니다.

### 엔진 히스토리 주입 연결 (`src/builder/engine.py`)
- 서버 엔진 조립 후 `build_context.history_messages`가 존재하면 `engine.load_messages(...)`를 호출하도록 연결했습니다.
- 이로써 CLI/TUI와 동일하게 서버 경로도 로드된 대화 문맥을 엔진 초기 상태에 주입할 수 있게 됐습니다.

### 히스토리 메시지 변환 규칙 추가 (`src/history/mapper.py`)
- 일반 `CHAT` 메시지는 그대로 텍스트 히스토리로 변환합니다.
- `TOOL_FEEDBACK` + `JSON` 메시지는 raw JSON 그대로 넣지 않고, 블록별 코멘트 요약 문자열로 변환해 엔진 히스토리에 포함하도록 구현했습니다.
- `TOOL_APPROVAL_REQUEST`는 요약 문장으로 정규화할 수 있도록 기본 변환 규칙을 추가했습니다.
- 결과적으로 채팅 저장 포맷과 LLM 입력 포맷을 분리하는 최소 변환 계층이 생겼습니다.

### Spring 내부 히스토리 저장 API 추가 (`backend/theseus-api-server`)
- Spring API 서버에 `POST /api/internal/history/messages`를 추가했습니다.
- public user message API를 넓히지 않고, internal endpoint를 통해 다음 메시지 타입을 저장할 수 있는 경로를 분리했습니다.
  - `USER`
  - `ASSISTANT`
  - `SYSTEM`
- 내부 저장 요청은 `toolId`를 선택적으로 받아 Tool 관련 메시지를 `chat_messages.tool_id`와 연결할 수 있도록 열어뒀습니다.
- `ChatMessageService`에는 sender/message/content/tool 기반의 일반 내부 저장 진입점을 추가했습니다.

### 테스트 및 검증 (`tests/test_stream.py`)
- 스트림 테스트를 `chat_session_id` 필수 계약 기준으로 갱신했습니다.
- user/assistant 히스토리 저장 hook과 history load hook을 patch하는 구조로 수정했습니다.
- `chat_session_id` 누락 시 `422`를 검증하는 케이스를 추가했습니다.
- 현재 환경 기준 검증 상태는 다음과 같습니다.
  - `py_compile` 문법 검증 통과
  - Spring `./gradlew compileJava` 성공
  - `unittest` 실실행은 로컬 Python 환경에 `fastapi` 미설치로 미완료

### 현재 상태
- 서버 스트림 경로가 이제 session-aware 히스토리 로드/주입 구조를 가집니다.
- Spring chat message 저장소를 그대로 사용하면서도, Tool 관련 메시지 타입 확장을 받을 수 있는 internal history 저장 경로가 분리되었습니다.
- progress/chunk 비영속, 최종 메시지 영속이라는 채팅 대시보드 설계 원칙을 서버 런타임 레벨에서 반영했습니다.

### 다음 작업
- Tool generate/regenerate/approval API에서 `TOOL_DRAFT_REQUEST`, `TOOL_DRAFT_RESPONSE`, `TOOL_FEEDBACK`, `TOOL_REGENERATE_RESPONSE`, `TOOL_APPROVAL_REQUEST`, `SYSTEM_NOTICE`를 실제로 history 저장 경로에 연결
- AI 요청 계약의 `llmInput.history` 구성 규칙을 Tool 플로우와 맞춰 구체화
- `completed` / `failed` 이벤트와 DB 반영 성공 조건을 tool 상태 전이와 함께 정렬

## [2026-05-02] Permission Inquiry Layer - Phase 1

### 권한 조회 설정 추가 (`src/config.py`, `.env.example`)
- Spring 기반 프로젝트 도구 권한 조회 엔드포인트 설정값 `SPRING_BOOT_PROJECT_PERMISSIONS_URL`를 추가했습니다.
- 기본값은 `http://localhost:8080/api/internal/project/permissions`로 고정했습니다.
- `.env.example`에도 동일 설정을 반영해 런타임/문서 설정 차이를 줄였습니다.

### 권한 조회 클라이언트 분리 (`src/auth/client.py`)
- 기존 인증/과금/플랜 저장 클라이언트와 별도로 `PermissionClient`를 추가했습니다.
- Spring 내부 API에 `POST` 요청으로 `projectId`, `userId`를 전달하도록 구현했습니다.
- 권한 조회 전용 예외를 다음과 같이 분리했습니다.
  - `PermissionAccessDeniedError`
  - `PermissionInvalidResponseError`
  - `PermissionBackendUnavailableError`
- 응답 스키마는 `dict[str, int]`로 검증하도록 추가했습니다.
- `403`은 접근 거부, 스키마 불일치는 invalid response, 네트워크/백엔드 장애는 unavailable로 분리했습니다.

### 권한 조회 서비스 도입 (`src/auth/permissions.py`)
- 새 진입점 `get_project_tool_permissions(project_id, user_id, session_id=None)`를 추가했습니다.
- `AUTH_MODE=mock`에서는 기존 mock 권한 맵을 서비스 내부에서 반환하도록 이동했습니다.
- `AUTH_MODE=spring`에서는 `PermissionClient`를 호출하도록 연결했습니다.
- 외부로 노출되는 에러 메시지를 다음 세 가지로 표준화했습니다.
  - `403 Project access denied`
  - `502 Permission service returned invalid data`
  - `503 Permission service unavailable`
- `session_id`는 추후 세션 연동을 위해 시그니처에 열어두고, 현재 단계에서는 reserved 처리했습니다.

### 스트리밍 라우트 권한 조회 이관 (`src/routes/stream.py`)
- 라우트 내부의 `MOCK_PROJECT_TOOL_PERMISSIONS` 상수와 `_get_project_tool_permissions(...)` 헬퍼를 제거했습니다.
- `/api/v1/stream`는 이제 권한 조회 service를 직접 호출해 `EngineBuildContext.project_tool_permissions`를 채웁니다.
- 빈 권한 맵 `{}`는 더 이상 `503`으로 fail-fast 하지 않도록 수정했습니다.
- zero-tool 상태는 라우트가 아니라 엔진 초기화 단계에서 처리되도록 경계를 정리했습니다.
  - 결과적으로 HTTP는 `200`을 유지하고 SSE `error` 이벤트로 종료될 수 있습니다.

### 테스트 보강 (`tests/test_auth_permissions.py`, `tests/test_stream.py`)
- 권한 service/client 전용 테스트 파일 `tests/test_auth_permissions.py`를 추가했습니다.
- 다음 케이스를 명시적으로 테스트하도록 구성했습니다.
  - `mock` 모드 정상 반환
  - `spring` 모드 정상 반환
  - `403` 접근 거부
  - `502` invalid schema
  - `503` backend unavailable
- `tests/test_stream.py`는 새 권한 service를 patch하는 구조로 변경했습니다.
- 스트림 라우트에서 다음 동작을 검증하도록 갱신했습니다.
  - 정상 권한 맵 수신 시 `200`
  - 빈 권한 맵 수신 시 엔진 `error` SSE 이벤트
  - `403/502/503` 예외 전파

### 검증 상태
- 변경 파일 기준 `py_compile` 문법 검증은 통과했습니다.
  - `python3 -m py_compile src/config.py src/auth/client.py src/auth/permissions.py src/routes/stream.py tests/test_auth_permissions.py tests/test_stream.py`
- `unittest` 실실행은 현재 로컬 런타임 의존성 문제로 완료하지 못했습니다.
  - 시스템 Python에는 `fastapi`, `httpx`가 없어 import 실패
  - 프로젝트 `.venv`는 Windows 레이아웃이라 WSL에서 직접 실행 불가
  - `PYTHONPATH=.venv/Lib/site-packages` 우회 실행 시 `exceptiongroup` 누락으로 import 단계 실패

### 현재 상태
- 서버 스트림 경로가 더 이상 라우트 내부 mock 권한 맵에 직접 의존하지 않습니다.
- `AUTH_MODE=spring`에서 실제 운영 권한 소스를 붙일 수 있는 최소 권한 조회 계층이 분리되었습니다.
- 권한 조회 실패 정책이 `403/502/503`으로 명확히 분리되었습니다.
- 빈 권한 맵은 정상 응답으로 취급하며, zero-tool UX는 엔진 계층으로 위임됩니다.

### 다음 작업
- Spring Boot 측 `POST /api/internal/project/permissions` 실제 엔드포인트 연결 및 payload 검증
- 세션/히스토리 서버 이관
- Plan 상태 및 `create_tool` 서버 이관 준비

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
