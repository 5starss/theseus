# 2026-04-28 Stream, Billing, Sandbox Integration

## 개요

이번 작업은 `theseus-core-server`를 문서/목업 중심 상태에서 실제 서버 실행 경로 기준으로 한 단계 끌어올리는 데 집중했다.

범위는 크게 세 축이다.

- Theseus 엔진 스트리밍 실연결
- 과금 안정화 (Outbox 패턴)
- Docker 기반 샌드박스 실행기 및 서비스 레벨 진입점 준비

이번 브랜치에서는 메타-툴링 전체 이관이나 `ToolCreatorTool` 서버 연동까지는 진행하지 않았다. 대신, 이후 연동 작업이 가능한 기반 계층과 서버 진입점을 먼저 고정하는 방향으로 작업했다.

---

## 1. Theseus 엔진 스트리밍 통합

### 목표

기존 `src/routes/stream.py`의 더미 SSE 스트리밍을 제거하고, 실제 Theseus/OpenHarness 엔진이 `prompt`를 받아 응답을 스트리밍하는 서버 경로를 만든다.

### 핵심 변경

- `src/builder/engine.py` 신규 추가
  - `get_query_engine(session)` 팩토리 구현
  - `OpenHarness` lazy import 적용
  - `EngineInitializationError` 도입
  - `AgentMode.AGENT` 전용 엔진 조립
  - Read-only allowlist 기반 도구 제한
    - `read_file`
    - `glob`
    - `grep`

- `src/routes/stream.py` 리팩토링
  - `GET /api/v1/stream?prompt=...` 입력 계약 적용
  - request-agnostic handler(`stream_agent_response`) 분리
  - OpenHarness 이벤트를 SSE로 매핑
    - `AssistantTextDelta -> chunk`
    - `ToolExecutionStarted -> status`
    - `ToolExecutionCompleted -> tool_result`
    - `ErrorEvent -> error`
  - `prompt` 공백 입력 방어
  - 툴 결과 길이 제한 추가
  - 엔진 초기화 실패 시 프로세스를 죽이지 않고 stream-level `error` SSE 반환

### 결과

- `src` 서버 경로에서 실제 Theseus 엔진을 single-turn 방식으로 호출할 수 있는 기반이 마련됨
- `OpenHarness` 미설치 환경에서도 앱 전체가 import 단계에서 즉시 죽지 않도록 방어됨

---

## 2. 과금 안정화: Outbox 패턴 도입

### 목표

기존 `BackgroundTasks` 기반 직접 과금 전송 구조를 제거하고, 사용량을 먼저 로컬 DB에 적재한 뒤 비동기 재전송할 수 있는 구조로 바꾼다.

### Phase 2.1: Outbox foundation

- `src/db/models.py`
  - `BillingOutbox` 모델 추가
  - 주요 필드:
    - `id`
    - `user_id`
    - `project_id`
    - `usage_data`
    - `status`
    - `retry_count`
    - `last_error`
    - `next_retry_at`
    - `created_at`
    - `updated_at`

- `src/db/repositories/billing.py` 신규 추가
  - `enqueue`
  - `claim_batch`
  - `mark_sent`
  - `mark_failed`
  - `to_usage_report`

- `src/auth/client.py`
  - `billing_client.report_usage()`에 `idempotency_key` 파라미터 추가
  - `X-Idempotency-Key` 헤더 전송 지원

- `src/routes/stream.py`
  - 스트림 종료 후 외부 API 직접 호출 제거
  - `BillingOutboxRepository.enqueue(...)`로 저장만 수행하도록 변경

- `src/builder/worker.py` 신규 추가
  - `process_billing_outbox()` 구현
  - 수동 flush 가능한 Phase 2.1 워커 기반 마련

### Phase 2.2: Scheduler integration

- `src/config.py`
  - `BILLING_OUTBOX_BATCH_SIZE`
  - `BILLING_OUTBOX_FLUSH_INTERVAL_SECONDS`
  설정 추가

- `src/builder/worker.py`
  - `setup_scheduler()` 추가
  - `APScheduler` lazy import 적용
  - 환경에 스케줄러가 없으면 서버를 죽이지 않고 경고만 남기도록 처리

- `src/main.py`
  - `lifespan` 도입
  - 앱 시작 시 과금 outbox 스케줄러 시작
  - 앱 종료 시 안전하게 stop

### 결과

- 스트림 종료 시 과금 데이터가 외부 API 성공 여부와 무관하게 먼저 DB에 적재됨
- 전송 실패 시 `failed + retry_count + next_retry_at` 기반 재시도가 가능해짐
- direct send 단일 실패로 과금 데이터가 증발하던 구조를 제거함

### 남은 운영 체크

- 실제 DB에 `billing_outbox` 테이블 생성 필요
- Spring Boot 측 `X-Idempotency-Key` 처리 확인 필요
- 실환경에서 outbox 상태 전이(`pending -> processing -> sent/failed`) 점검 필요

---

## 3. Docker 기반 실제 샌드박스 실행기 통합

### 목표

기존 mock 상태였던 `DockerExecutor`를 실제 Docker SDK 기반 실행기로 교체하고, 이후 코드 실행 도구를 이 경로로 연결할 수 있는 기반을 만든다.

### 핵심 변경

- `requirements.txt`
  - `docker==7.0.0` 추가

- `src/config.py`
  - 샌드박스 설정값 추가
    - `SANDBOX_IMAGE`
    - `SANDBOX_MEMORY_LIMIT`
    - `SANDBOX_CPU_QUOTA`
    - `SANDBOX_CPU_PERIOD`
    - `SANDBOX_KEEP_FAILED_CONTAINERS`

- `src/sandbox/base.py`
  - `SandboxUnavailableError` 추가
  - `SandboxOutput` 보강
    - `exit_code`
    - `timed_out`
    - `resource_limited`
  - `SandboxExecutionRequest` 추가

- `src/sandbox/sandbox_runner.py` 신규 추가
  - 고정 계약 runner 구현
  - 입력:
    - `/sandbox/input/payload.json`
    - `/sandbox/input/tool_code.py`
  - 실행 계약:
    - `tool_code.py`는 `main(payload)` 함수 제공
  - 출력:
    - `/sandbox/output/result.json`
  - stdout 오염과 무관하게 결과 파일만 신뢰하는 구조 적용

- `src/sandbox/docker_executor.py` 실구현
  - Docker SDK lazy init
  - `docker.from_env()` + `ping()` 검증
  - Docker 미가용 시 `SandboxUnavailableError` 반환
  - input/output mount 분리
  - `network_disabled=True`
  - memory/cpu 제한 적용
  - timeout 시 `kill`
  - `result.json` 기반 결과 수집
  - 실패 컨테이너 보존 옵션 지원

### 검증 준비

- `tests/test_sandbox.py`
  - Docker SDK 부재 시 controlled error 검증
  - `sandbox_runner` 성공/실패 계약 검증
  - timeout 및 결과 수집 경로 mocking 기반 검증

---

## 4. 샌드박스 서비스 레벨 진입점 준비

### 목표

샌드박스 실행기를 단순 유틸리티가 아니라 실제 애플리케이션 라우트에서 호출 가능한 상태로 올린다.

### 핵심 변경

- `src/routes/sandbox.py` 신규 추가
  - `POST /api/v1/sandbox/execute`
  - 인증 세션 기반 `project_id` 강제 바인딩
  - 관리자 수준 권한(`permission_level >= 3`) 요구
  - `SandboxUnavailableError -> 503` 변환

- `src/main.py`
  - `sandbox.router` 연결

- `tests/test_sandbox_route.py`
  - 권한 부족 시 `403`
  - 샌드박스 불가 시 `503`
  - 성공 응답 구조 검증

### 결과

- 상위 서비스 레벨에서 실제 Docker 샌드박스 실행기를 호출할 수 있는 최소 진입점이 생김
- 추후 `ToolCreatorTool` 또는 코드 실행 브릿지 작업 시 재사용 가능한 서버 경로 확보

---

## 5. 이번 브랜치에서 의도적으로 제외한 것

이번 브랜치에서는 다음 작업을 진행하지 않았다.

- `ToolCreatorTool`의 서버형 이관 완료
- Plan 모드 서버형 이관
- `create_tool` 산출물의 샌드박스 강제 실행 경로 연결
- multi-turn 세션 메모리 서버 통합

이 항목들은 모두 변경 폭이 크고 도메인 로직 리뷰 포인트가 다르기 때문에, 이번 브랜치의 인프라/안정화 작업과 분리하는 것이 맞다고 판단했다.

---

## 6. 현재 상태 요약

이번 작업 이후 `theseus-core-server`는 다음 상태가 되었다.

- 스트리밍:
  - 더미 SSE 제거
  - 실제 Theseus 엔진 single-turn 스트리밍 경로 확보

- 과금:
  - direct send 제거
  - outbox 저장 + scheduler 기반 재전송 구조 확보

- 샌드박스:
  - Docker 기반 실제 실행기 구현
  - 고정 runner 계약 확정
  - 서비스 레벨 실행 진입점 확보

즉, 서버 외곽만 존재하던 상태에서, 실제 실행 가능한 엔진/과금/격리 실행 기반이 한 세트로 정리되었다.

---

## 7. 다음 권장 작업

다음 브랜치에서는 다음 순서가 적절하다.

1. `ToolCreatorTool` / Plan 모드 서버 이관
2. 생성 코드 실행 경로를 샌드박스에 강제 연결
3. 관련 승인/검증 파이프라인 정리

이번 브랜치는 여기서 종료하는 것이 경계상 가장 깔끔하다.
