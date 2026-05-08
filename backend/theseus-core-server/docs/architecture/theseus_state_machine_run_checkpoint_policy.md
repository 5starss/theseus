# TheseusStateMachine Run Checkpoint Policy

## 기준

- Kafka request 1개는 LLM 호출 1회가 아니라 Core Server의 장기 실행 run 하나를 시작하는 명령이다.
- Core Server는 `runId` 기준으로 agent loop checkpoint를 Core PostgreSQL에 저장한다.
- API Server MySQL은 ToolPlan/Tool의 서비스 최종 상태를 저장한다.
- Core PostgreSQL은 Core 내부 실행 상태, tool-use trace, 재시도 기준을 저장한다.
- `planSnapshot`은 FE 렌더링과 승인 감사를 위한 API-facing snapshot이며 Core checkpoint가 아니다.
- Core Server는 API Server 내부 HTTP로 PLAN이나 history를 조회하지 않는다.

## 저장 대상

`TheseusStateMachine`과 agent loop를 재개하기 위해 Core Server가 저장해야 하는 상태는 다음과 같다.

| 구분 | 저장 내용 |
| --- | --- |
| Run metadata | `runId`, `projectId`, `chatSessionId`, request type, mode |
| StateMachine | `mode`, `plan_phase`, `coordinator_phase`, `plan`, `plan_blocks`, `plan_document` |
| Conversation | Core `ConversationMessage` 목록 |
| Tool trace | `ToolUseBlock`, `ToolResultBlock`, tool call input/output/error |
| Progress cursor | 마지막 `stage`, `progressRate`, `eventSequence` |
| Retry cursor | retry count, last error, resume 가능 여부 |
| Lease | worker owner, lease 만료 시각 |

저장하지 않는 값:

- LLM provider credential
- 사용자 access token / refresh token
- API Server 내부 인증 header
- 대용량 artifact 본문
- FE 표시 전용 임시 chunk 누적 전문

대용량 artifact와 실행 로그 파일은 S3에 저장하고 checkpoint에는 S3 key만 저장한다.

## Core PostgreSQL 테이블

### `core_run_checkpoints`

`core_run_checkpoints`는 `runId`의 현재 실행 상태를 저장한다.

```sql
CREATE TABLE core_run_checkpoints (
    run_id VARCHAR(64) NOT NULL,
    project_id BIGINT NOT NULL,
    chat_session_id BIGINT NOT NULL,
    request_type VARCHAR(50) NOT NULL,
    mode VARCHAR(30) NOT NULL,
    status VARCHAR(30) NOT NULL,
    checkpoint_version INTEGER NOT NULL DEFAULT 1,
    state_machine_json JSONB NOT NULL,
    conversation_json JSONB NOT NULL,
    tool_trace_json JSONB NULL,
    progress_json JSONB NULL,
    last_event_sequence INTEGER NOT NULL DEFAULT 0,
    retry_count INTEGER NOT NULL DEFAULT 0,
    last_error_code VARCHAR(100) NULL,
    last_error_message TEXT NULL,
    lease_owner VARCHAR(100) NULL,
    lease_expires_at TIMESTAMPTZ NULL,
    requested_at TIMESTAMPTZ NOT NULL,
    updated_at TIMESTAMPTZ NOT NULL,
    completed_at TIMESTAMPTZ NULL,
    CONSTRAINT pk_core_run_checkpoints PRIMARY KEY (run_id)
);

CREATE INDEX idx_core_run_checkpoints_status_updated_at
    ON core_run_checkpoints (status, updated_at);

CREATE INDEX idx_core_run_checkpoints_project_session
    ON core_run_checkpoints (project_id, chat_session_id);
```

`status` 값:

```text
REQUESTED
RUNNING
WAITING_TOOL
COMPLETED
SKIPPED
FAILED
CANCELLED
```

### `core_run_events`

`core_run_events`는 Core가 Kafka로 발행한 이벤트 이력과 중복 발행 방지 기준을 저장한다.

```sql
CREATE TABLE core_run_events (
    id BIGSERIAL NOT NULL,
    run_id VARCHAR(64) NOT NULL,
    event_sequence INTEGER NOT NULL,
    event_type VARCHAR(80) NOT NULL,
    payload_json JSONB NOT NULL,
    published_at TIMESTAMPTZ NOT NULL,
    CONSTRAINT pk_core_run_events PRIMARY KEY (id),
    CONSTRAINT uk_core_run_events_run_sequence UNIQUE (run_id, event_sequence),
    CONSTRAINT fk_core_run_events_checkpoint
        FOREIGN KEY (run_id) REFERENCES core_run_checkpoints (run_id)
);

CREATE INDEX idx_core_run_events_run_id
    ON core_run_events (run_id);
```

Kafka는 at-least-once 전달을 전제로 한다. Core Server는 `runId + eventSequence`를 중복 방지 키로 사용한다.

## Checkpoint JSON

### `state_machine_json`

```json
{
  "schemaVersion": 1,
  "mode": "PLAN",
  "planPhase": "DRAFTING",
  "coordinatorPhase": null,
  "plan": "## Tool Plan...",
  "planBlocks": [
    {
      "blockId": "analysis-summary",
      "title": "분석 요약",
      "content": "최근 장애 로그를 수집하고 원인을 분류합니다."
    }
  ],
  "planDocument": {
    "version": 1,
    "blocks": []
  }
}
```

### `conversation_json`

```json
[
  {
    "role": "user",
    "content": [
      {
        "type": "text",
        "text": "장애 로그 분석 Tool 명세를 작성해줘."
      }
    ]
  },
  {
    "role": "assistant",
    "content": [
      {
        "type": "tool_use",
        "id": "toolu_01",
        "name": "search_logs",
        "input": {
          "query": "recent 504 errors"
        }
      }
    ]
  },
  {
    "role": "user",
    "content": [
      {
        "type": "tool_result",
        "tool_use_id": "toolu_01",
        "content": "504 errors increased between 09:00 and 10:30."
      }
    ]
  }
]
```

`conversation_json`은 Core `ConversationMessage` 직렬화 결과다. API Server가 보낸 `history`는 run 시작 입력이며, Core 실행 중 발생한 tool-use 대화는 Core checkpoint에 저장한다.

### `tool_trace_json`

```json
{
  "calls": [
    {
      "sequence": 1,
      "toolUseId": "toolu_01",
      "name": "search_logs",
      "input": {
        "query": "recent 504 errors"
      },
      "status": "SUCCEEDED",
      "startedAt": "2026-05-08T10:20:01Z",
      "completedAt": "2026-05-08T10:20:04Z",
      "outputPreview": "504 errors increased between 09:00 and 10:30.",
      "artifactKeys": []
    }
  ]
}
```

tool output이 크면 `outputPreview`만 checkpoint에 저장하고 원문은 S3에 저장한다.

### `progress_json`

```json
{
  "stage": "TOOL_CALLING",
  "message": "장애 로그를 조회하고 있습니다.",
  "progressRate": 55,
  "lastEventSequence": 4,
  "updatedAt": "2026-05-08T10:20:04Z"
}
```

## 저장 시점

Core Server는 다음 시점에 checkpoint를 저장한다.

| 시점 | 처리 |
| --- | --- |
| Kafka request consume 직후 | `REQUESTED` checkpoint 생성 |
| agent loop 시작 | `RUNNING` 전환 |
| LLM 응답 수신 후 | conversation과 StateMachine 저장 |
| tool call 시작 전 | `WAITING_TOOL` 또는 `RUNNING` 상태 저장 |
| tool call 완료 후 | tool result, trace 저장 |
| progress/chunk 발행 전 | `last_event_sequence` 증가, progress 저장 |
| completed/skipped/failed 발행 전 | terminal 상태와 최종 event 저장 |

이벤트 발행 순서:

```text
checkpoint 저장
core_run_events 저장
DB commit
Kafka publish
```

Kafka publish 실패 시 `core_run_events`에 남은 미발행 이벤트를 재발행한다.

## Lease

Core worker는 run 처리 전에 lease를 획득한다.

```text
lease_owner = worker instance id
lease_expires_at = now + lease ttl
```

규칙:

- lease가 살아 있는 run은 다른 worker가 처리하지 않는다.
- worker는 장기 실행 중 주기적으로 lease를 연장한다.
- lease가 만료된 `RUNNING`, `WAITING_TOOL` run은 재시도 대상이다.
- terminal 상태의 run은 lease를 해제한다.

권장값:

```text
lease ttl = 60초
heartbeat interval = 20초
max retry count = 3
stale running timeout = 30분
```

## 장애 복구

### Worker 재시작

```text
1. Core Server 시작
2. REQUESTED, RUNNING, WAITING_TOOL 상태의 stale run 조회
3. lease 만료 여부 확인
4. retry_count < max retry count면 resume
5. resume 불가하거나 retry 초과면 FAILED 처리
6. TOOL_PLAN_FAILED 또는 TOOL_BUILD_FAILED 발행
```

### Resume 기준

resume 가능:

- checkpoint JSON schemaVersion을 지원한다.
- conversation_json을 `ConversationMessage`로 복원할 수 있다.
- StateMachine mode/phase를 복원할 수 있다.
- 마지막 tool call이 완료 상태이거나 안전하게 재실행 가능하다.

resume 불가:

- checkpoint JSON parsing 실패
- 지원하지 않는 schemaVersion
- 진행 중 tool call의 멱등성이 보장되지 않음
- sandbox 실행 중 외부 side effect 여부가 불명확함

resume 불가 run은 `FAILED`로 마감하고 사용자에게 재시도 가능한 실패 메시지를 보낸다.

## Progress / Event Sequence

Core Server는 `runId` 안에서 `eventSequence`를 단조 증가시킨다.

```text
eventSequence = core_run_checkpoints.last_event_sequence + 1
```

규칙:

- checkpoint와 event 저장은 같은 DB transaction으로 처리한다.
- terminal event 이후 progress/chunk는 발행하지 않는다.
- `progressRate`는 같은 run 안에서 감소하지 않는다.
- Kafka key는 `runId`를 사용한다.
- API Server는 `runId + eventSequence`로 중복 이벤트를 방어한다.

## 기존 파일 세션 저장과의 관계

현재 `theseus_engine.models.sessions`는 `.theseus_sessions/{session}.json`에 `history`와 `plan_state`를 저장할 수 있다.

서버 Kafka worker 기준 정책:

- `.theseus_sessions` 파일 저장은 CLI/TUI 로컬 실행용으로 유지한다.
- API/Core 통합 서버 실행에서는 Core PostgreSQL checkpoint를 기준으로 한다.
- 파일 기반 `plan_state`는 운영 run 복구 기준으로 사용하지 않는다.
- 전환 기간에는 동일한 직렬화 구조를 재사용할 수 있지만 저장소는 PostgreSQL로 분리한다.

## API Server와의 경계

API Server MySQL에 저장하는 값:

- ToolPlanRun 상태
- ToolPlanGroup / ToolPlan / Tool
- ChatMessage 최종 메시지
- 승인 이력

Core PostgreSQL에 저장하는 값:

- StateMachine checkpoint
- ConversationMessage 전체 실행 상태
- ToolUseBlock / ToolResultBlock
- tool call trace
- Core retry/lease 정보

Redis에 저장하는 값:

- `tool:plan:{runId}:state`
- FE 재연결용 최신 progress/chunk/terminal 상태

S3에 저장하는 값:

- 대용량 tool output
- artifact
- sandbox 실행 로그

## 구현 체크리스트

- `core_run_checkpoints` repository 추가
- `core_run_events` repository 추가
- `TheseusStateMachine` 직렬화/역직렬화 함수 추가
- `ConversationMessage` 직렬화/역직렬화 함수 재사용
- Kafka request consume 직후 checkpoint 생성
- progress/chunk/completed/skipped/failed 발행 전 eventSequence 증가
- terminal event 중복 발행 방지
- worker lease 획득/연장/해제
- stale run 복구 스케줄러
- `.theseus_sessions` 파일 저장과 서버 checkpoint 저장 경계 분리

## 테스트 기준

- StateMachine checkpoint JSON round-trip
- ConversationMessage, ToolUseBlock, ToolResultBlock round-trip
- progress 발행 시 eventSequence 증가
- terminal event 이후 progress/chunk 발행 차단
- Kafka publish 실패 후 core_run_events 기반 재발행
- lease 만료 run 재시도
- retry 초과 run FAILED 마감
- 파일 기반 plan_state가 서버 checkpoint에 영향을 주지 않음
