# ToolPlan Snapshot, History, Progress Rules

## 기준

- `planSnapshot`은 API Server와 FE가 동일한 PLAN 화면을 복구하기 위한 고정본이다.
- `planSnapshot`은 Core Server의 `TheseusStateMachine` checkpoint가 아니다.
- Core Server의 agent loop, tool-use trace, intermediate state는 Core PostgreSQL에 `runId` 기준으로 저장한다.
- Core checkpoint 저장 정책은 [TheseusStateMachine Run Checkpoint Policy](../../backend/theseus-core-server/docs/architecture/theseus_state_machine_run_checkpoint_policy.md)를 따른다.
- API Server는 Kafka payload에 최근 대화 history snapshot을 포함한다.
- Core Server는 API Server 내부 HTTP로 PLAN이나 history를 조회하지 않는다.
- `progress`와 `chunk`는 Redis/SSE 전용 진행 이벤트이며 `chat_messages`에 저장하지 않는다.

## planSnapshot

`planSnapshot`은 특정 `ToolPlan` 버전을 사용자에게 보여주고 승인 감사에 남기기 위한 API-facing snapshot이다.

저장 위치:

```text
tool_plans.plan_snapshot
```

저장 시점:

```text
Core TOOL_PLAN_COMPLETED 수신
-> API Server가 ToolPlan 생성
-> tool_plans.plan_snapshot 저장
```

용도:

- 채팅 대시보드의 PLAN 카드 렌더링
- 사용자가 피드백한 PLAN 버전 복구
- 승인 요청 시 검토 대상 고정
- 승인/반려 감사 이력 확인
- 새로고침 후 PLAN 화면 복구

비용도:

- Core Server agent loop 재개용 checkpoint
- tool-use trace 저장소
- LLM 내부 reasoning 저장소
- Core `TheseusStateMachine` 직렬화 결과

### 필수 필드

```json
{
  "schemaVersion": 1,
  "planVersion": 1,
  "title": "장애 로그 복구 가이드 Tool",
  "summary": "최근 장애 로그를 분석하고 복구 가이드를 생성합니다.",
  "blocks": [
    {
      "blockId": "analysis-summary",
      "title": "분석 요약",
      "content": "최근 장애 로그를 수집하고 원인을 분류합니다.",
      "order": 1
    }
  ],
  "createdAt": "2026-05-08T10:21:00"
}
```

| Field | Required | Description |
| --- | --- | --- |
| `schemaVersion` | Y | snapshot 구조 버전 |
| `planVersion` | Y | `tool_plans.plan_version`과 같은 값 |
| `title` | Y | PLAN 카드 제목 |
| `summary` | Y | PLAN 요약 |
| `blocks` | Y | 블록별 피드백과 렌더링 기준 목록 |
| `blocks[].blockId` | Y | 블록 식별자 |
| `blocks[].title` | Y | 블록 제목 |
| `blocks[].content` | Y | 블록 본문 |
| `blocks[].order` | Y | 화면 표시 순서 |
| `createdAt` | Y | Core completed 기준 생성 시각 |

### 선택 필드

```json
{
  "assumptions": [],
  "inputs": [],
  "outputs": [],
  "permissions": [],
  "risks": [],
  "estimatedSteps": []
}
```

선택 필드는 FE 렌더링과 승인 판단에 필요할 때 추가한다. 선택 필드를 추가해도 필수 필드의 의미를 바꾸지 않는다.

## structuredPlanJson

`structuredPlanJson`은 Core가 생성한 기계 처리용 PLAN 구조다.

용도:

- 재생성 시 `basePlan.structuredPlanJson`으로 전달
- Tool build 시 승인된 PLAN 구조 입력
- Core Server가 PLAN 의미 구조를 해석하는 기준

필수 조건:

```text
structuredPlanJson.blocks[].blockId
structuredPlanJson.blocks[].title
structuredPlanJson.blocks[].content
```

`planSnapshot.blocks`는 `structuredPlanJson.blocks`에서 FE와 승인에 필요한 항목을 고정한 표현이다. 두 값은 같은 PLAN 버전을 설명해야 한다.

## blockId

`blockId`는 블록별 피드백의 기준 식별자다.

규칙:

- 같은 의미의 블록은 재생성 후에도 같은 `blockId`를 유지한다.
- 본문만 수정되고 역할이 같으면 같은 `blockId`를 유지한다.
- 새 의미의 블록은 새 `blockId`를 생성한다.
- 삭제된 블록은 새 PLAN에서 제외한다.
- 분할된 블록은 대표 의미를 가진 블록 하나에 기존 `blockId`를 유지하고 나머지는 새 `blockId`를 생성한다.
- 병합된 블록은 핵심 의미가 가장 큰 기존 `blockId` 하나를 유지한다.

금지:

- 표시 순서만으로 `blockId`를 생성하지 않는다.
- 매 재생성마다 모든 `blockId`를 새로 만들지 않는다.
- 사용자가 피드백한 `blockId`가 사라진 경우 조용히 무시하지 않는다.

피드백 대상 `blockId`가 현재 `basePlan`에 없으면 Core는 재생성을 실패시키거나, 해당 피드백을 미적용 항목으로 명시해야 한다.

## History Snapshot

API Server는 Kafka 요청 payload에 최근 대화 history snapshot을 포함한다.

저장 위치:

```text
tool_plan_runs.history_snapshot_json
```

생성 시점:

```text
PLAN 생성/재생성 요청 수신
-> 요청 사용자 메시지 저장
-> chatSessionId 기준 최근 메시지 조회
-> Core 입력용 history로 변환
-> tool_plan_runs.history_snapshot_json 저장
-> Kafka payload.history에 포함
```

Core Server는 이 history snapshot을 LLM context로 사용한다. Core Server는 API Server 내부 HTTP로 history를 다시 조회하지 않는다.

### 메시지 포함 기준

포함:

- 일반 USER/ASSISTANT `CHAT`
- USER `TOOL_PLAN_REQUEST`
- ASSISTANT `TOOL_PLAN_RESPONSE`
- USER `TOOL_FEEDBACK`
- 사용자에게 의미 있는 `SYSTEM_NOTICE`

제외:

- `progress`
- `chunk`
- 내부 오류 stack trace
- 승인 감사 전용 시스템 이벤트
- Core 내부 tool-use trace
- Core 내부 `ToolUseBlock`, `ToolResultBlock`

Core 내부 tool-use trace는 Core PostgreSQL checkpoint에 저장한다.

### 변환 규칙

| ChatMessage | Core history role | Core history content |
| --- | --- | --- |
| `senderType = USER`, `messageType = CHAT` | `user` | `content` text |
| `senderType = ASSISTANT`, `messageType = CHAT` | `assistant` | `content` text |
| `TOOL_PLAN_REQUEST` | `user` | PLAN 요청 text |
| `TOOL_PLAN_RESPONSE` | `assistant` | PLAN 요약과 핵심 block text |
| `TOOL_FEEDBACK` | `user` | feedbackItems 요약 text |
| `SYSTEM_NOTICE` | `system` 또는 제외 | 사용자 판단에 필요한 안내만 압축 |

`TOOL_PLAN_RESPONSE` 전체 Markdown이 너무 길면 API Server는 요약본과 `toolPlanId`, `planVersion`, 주요 block title/content만 포함할 수 있다. 원본 PLAN은 Kafka 재생성 payload의 `basePlan`으로 전달한다.

### Core 입력 예시

```json
[
  {
    "role": "user",
    "messageType": "CHAT",
    "contentType": "TEXT",
    "content": "최근 장애 로그가 자주 발생해."
  },
  {
    "role": "assistant",
    "messageType": "CHAT",
    "contentType": "TEXT",
    "content": "어떤 로그를 기준으로 분석하면 될까요?"
  },
  {
    "role": "user",
    "messageType": "TOOL_PLAN_REQUEST",
    "contentType": "TEXT",
    "content": "장애 로그 분석 Tool 명세를 작성해줘."
  }
]
```

### 길이 제한

- API Server는 최근 메시지 N개 또는 token budget 기준으로 history를 제한한다.
- 오래된 메시지는 요약 메시지로 압축할 수 있다.
- 압축된 history는 `messageType = CHAT`, `role = system` 또는 `assistant` 요약으로 전달한다.
- 압축 규칙은 Core 입력 안정성을 우선한다.

## Progress Event

`progress`는 사용자가 이해할 수 있는 단계 상태다. 숫자 진행률은 정확한 작업량 비율이 아니라 UI 표시용 추정값이다.

저장 위치:

```text
Redis: tool:plan:{runId}:state
```

DB 저장:

```text
저장하지 않음
```

필수 필드:

```json
{
  "eventType": "progress",
  "runId": "3f2a2d5e-0e4a-4a3f-8d0f-9b5a3e2c0d11",
  "eventSequence": 3,
  "projectId": 1,
  "chatSessionId": 10,
  "stage": "PLAN_DRAFTING",
  "message": "PLAN 구조를 작성하고 있습니다.",
  "progressRate": 35,
  "updatedAt": "2026-05-08T14:30:00"
}
```

| Field | Required | Description |
| --- | --- | --- |
| `eventType` | Y | `progress` |
| `runId` | Y | 실행 ID |
| `eventSequence` | Y | run 내부 단조 증가 순서 |
| `projectId` | Y | 프로젝트 ID |
| `chatSessionId` | Y | 채팅 세션 ID |
| `stage` | Y | 현재 단계 |
| `message` | Y | 사용자 표시 문구 |
| `progressRate` | N | 0-100 정수 |
| `updatedAt` | Y | 이벤트 발생 시각 |

### stage

| Stage | 권장 progressRate | 의미 |
| --- | --- | --- |
| `REQUEST_RECEIVED` | 0 | 요청 수신 |
| `INTENT_CHECKING` | 5 | Tool 명세 생성 대상 여부 판단 |
| `HISTORY_LOADING` | 10 | history/context 구성 |
| `PLAN_DRAFTING` | 25-45 | PLAN 초안 작성 |
| `TOOL_CALLING` | 45-65 | 검색, 분석, 파일 처리 등 tool call 실행 |
| `TOOL_RESULT_READING` | 55-75 | tool call 결과 반영 |
| `PLAN_STRUCTURING` | 70-85 | structuredPlanJson/planSnapshot 구성 |
| `PLAN_VALIDATING` | 85-95 | blockId, 필수 필드 검증 |
| `PLAN_COMPLETED` | 100 | PLAN 생성 완료 |
| `PLAN_SKIPPED` | 100 | Tool 명세 대상 아님 |
| `PLAN_FAILED` | 100 | 실패 |

`progressRate`는 같은 run 안에서 감소하지 않는다. 단, 실패 이벤트는 즉시 `PLAN_FAILED`, `progressRate = 100`으로 종료할 수 있다.

## Chunk Event

`chunk`는 LLM 스트리밍 텍스트 조각이다.

필수 필드:

```json
{
  "eventType": "chunk",
  "runId": "3f2a2d5e-0e4a-4a3f-8d0f-9b5a3e2c0d11",
  "eventSequence": 4,
  "projectId": 1,
  "chatSessionId": 10,
  "content": "## 입력 정의...",
  "updatedAt": "2026-05-08T14:30:03"
}
```

규칙:

- DB에 저장하지 않는다.
- Redis에는 최신 chunk 또는 최신 state만 저장한다.
- FE는 chunk를 임시 표시로 사용할 수 있다.
- 최종 Assistant 메시지는 `TOOL_PLAN_COMPLETED.assistantMessage`만 `chat_messages`에 저장한다.
- Core가 tool call 실행 중이면 chunk가 없을 수 있다.

## Event Ordering

Core Server는 같은 `runId` 안에서 `eventSequence`를 단조 증가시킨다.

규칙:

- `eventSequence`는 1부터 시작한다.
- `progress`, `chunk`, `completed`, `skipped`, `failed`는 같은 sequence 공간을 사용한다.
- API Server는 이미 처리한 `runId + eventSequence` 이벤트를 다시 처리하지 않는다.
- 늦게 도착한 낮은 sequence 이벤트는 Redis/SSE 최신 상태를 덮어쓰지 않는다.
- `completed`, `skipped`, `failed`는 terminal event다.
- terminal event 이후 같은 run의 progress/chunk는 무시한다.

## Terminal Event

Terminal event는 DB commit 이후 Redis/SSE로 전달한다.

```text
Core terminal event consume
-> idempotency 확인
-> DB 상태 변경
-> ChatMessage 저장
-> DB commit
-> Redis state 저장
-> SSE terminal event 전송
-> emitter complete
```

Terminal event 종류:

- `TOOL_PLAN_COMPLETED`
- `TOOL_PLAN_SKIPPED`
- `TOOL_PLAN_FAILED`
- `TOOL_BUILD_COMPLETED`
- `TOOL_BUILD_FAILED`

## Error Handling

Core Server가 복구 가능한 tool call 실패를 만난 경우:

```text
progress PLAN_FAILED 또는 TOOL_CALLING 실패 문구 발행
TOOL_PLAN_FAILED 발행
```

API Server 처리:

```text
ToolPlanRun.status = FAILED
SYSTEM_NOTICE 또는 ASSISTANT 안내 메시지 저장
Redis failed 저장
SSE failed 전송
```

Core Server가 skipped로 판단한 경우:

```text
ToolPlanRun.status = SKIPPED
ToolPlanGroup 미생성
ToolPlan 미생성
Tool 미생성
ASSISTANT CHAT 안내 메시지 저장
Redis skipped 저장
SSE skipped 전송
```
