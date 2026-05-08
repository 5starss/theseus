# ToolPlan Kafka Payload Contract

## 전체 흐름

Tool PLAN 생성, 재생성, 실제 Tool build는 FE, API Server, Core Server가 아래 흐름으로 처리한다.

```text
FE
-> API Server
-> Kafka
-> Core Server
-> Kafka
-> API Server
-> Redis / SSE
-> FE
```

- FE는 API Server와만 HTTP/SSE로 통신한다.
- API Server는 인증, 프로젝트 접근 권한, PLAN 요청 권한, 승인 권한을 검증한다.
- API Server는 ToolPlanRun 생성, 사용자 메시지 저장, history snapshot 구성, Kafka 요청 이벤트 발행을 담당한다.
- API Server는 PLAN 요청 시점에 `tools` row를 생성하지 않는다.
- Core Server는 Kafka 요청 이벤트를 consume하고 Tool PLAN 생성/재생성 또는 Tool build를 수행한다.
- Core Server는 API Server 내부 HTTP로 PLAN이나 history를 조회하지 않는다.
- Core Server는 진행 이벤트와 완료/실패/skipped 이벤트를 Kafka로 발행한다.
- API Server는 Core 이벤트를 consume하고 DB 최종 반영, Redis 상태 저장, SSE 전달을 담당한다.

Kafka request 1개는 LLM 호출 1회가 아니라 Core Server의 장기 실행 run 하나를 시작하는 명령이다. Core 내부 `TheseusStateMachine` 상태와 tool-use trace는 Core PostgreSQL에 `runId` 기준 checkpoint로 저장한다.

`planSnapshot`, history 변환, progress/chunk 세부 규칙은 [ToolPlan Snapshot, History, Progress Rules](../architecture/tool-plan-runtime-rules.md)를 따른다.

## Kafka Topic

| Topic | Producer | Consumer | 용도 |
| --- | --- | --- | --- |
| `theseus.tool-plan.request` | API Server | Core Server | PLAN 생성/재생성 요청 |
| `theseus.tool-plan.event` | Core Server | API Server | PLAN progress, chunk, completed, skipped, failed 이벤트 |
| `theseus.tool-build.request` | API Server | Core Server | 승인된 PLAN 기반 실제 Tool 산출물 생성 요청 |
| `theseus.tool-build.event` | Core Server | API Server | Tool build completed, failed 이벤트 |

Kafka key는 `runId`를 사용한다.

## 공통 필드

| Field | Type | Required | Description |
| --- | --- | --- | --- |
| `eventType` | string | Y | 이벤트 타입 |
| `runId` | string | Y | Core 실행 1회 식별자 |
| `projectId` | number | Y | 프로젝트 ID |
| `chatSessionId` | number | Y | 채팅 세션 ID |
| `mode` | string | N | `PLAN`, `ASK`, `AGENT` 중 해당 모드 |
| `requestedAt` | datetime string | N | API Server 요청 생성 시각 |

datetime 값은 ISO-8601 문자열로 직렬화한다.

## PLAN Generate Request

API Server가 `theseus.tool-plan.request` topic으로 발행한다.

### 필드

| Field | Type | Required | Description |
| --- | --- | --- | --- |
| `eventType` | string | Y | `TOOL_PLAN_REQUESTED` |
| `mode` | string | Y | `PLAN` |
| `runId` | string | Y | PLAN 생성 실행 1회 식별자 |
| `projectId` | number | Y | 프로젝트 ID |
| `chatSessionId` | number | Y | 채팅 세션 ID |
| `requestedByUserId` | number | Y | 요청 사용자 ID |
| `requestedByProjectMemberId` | number | Y | 요청 프로젝트 멤버 ID |
| `prompt` | string | Y | 사용자가 입력한 PLAN 요청 |
| `history` | array | Y | 최근 대화 snapshot |
| `requestedAt` | datetime string | Y | 요청 시각 |

`toolId`는 포함하지 않는다. 아직 실제 Tool이 없기 때문이다.

### 예시

```json
{
  "eventType": "TOOL_PLAN_REQUESTED",
  "mode": "PLAN",
  "runId": "f2adc89f-0ca4-425b-b312-a2ca1ca9b0a7",
  "projectId": 2,
  "chatSessionId": 360,
  "requestedByUserId": 8,
  "requestedByProjectMemberId": 2,
  "prompt": "장애 로그를 분석하고 자동 복구 가이드를 만드는 Tool 명세를 작성해줘.",
  "history": [
    {
      "role": "user",
      "messageType": "CHAT",
      "contentType": "TEXT",
      "content": "최근 장애 로그가 자주 발생해."
    }
  ],
  "requestedAt": "2026-05-08T10:15:08"
}
```

## PLAN Regenerate Request

API Server가 `theseus.tool-plan.request` topic으로 발행한다.

### 필드

| Field | Type | Required | Description |
| --- | --- | --- | --- |
| `eventType` | string | Y | `TOOL_PLAN_REGENERATION_REQUESTED` |
| `mode` | string | Y | `PLAN` |
| `runId` | string | Y | PLAN 재생성 실행 1회 식별자 |
| `projectId` | number | Y | 프로젝트 ID |
| `chatSessionId` | number | Y | 채팅 세션 ID |
| `baseToolPlanId` | number | Y | 피드백 기준 PLAN ID |
| `planGroupId` | number | Y | 같은 Tool 후보 흐름 ID |
| `basePlanVersion` | number | Y | 사용자가 피드백한 PLAN 버전 |
| `basePlan` | object | Y | 재생성 기준 PLAN |
| `feedbackItems` | array | Y | 블록별 피드백 목록 |
| `history` | array | Y | 최근 대화 snapshot |
| `requestedAt` | datetime string | Y | 요청 시각 |

### `basePlan`

| Field | Type | Required | Description |
| --- | --- | --- | --- |
| `rawMarkdown` | string | Y | 기준 PLAN 원문 Markdown |
| `structuredPlanJson` | object | Y | 기준 PLAN 구조화 JSON |
| `planSnapshot` | object | Y | API-facing PLAN 고정본 |

### `feedbackItems`

| Field | Type | Required | Description |
| --- | --- | --- | --- |
| `blockId` | string | Y | 피드백 대상 PLAN block ID |
| `comment` | string | Y | 사용자 피드백 내용 |

### 예시

```json
{
  "eventType": "TOOL_PLAN_REGENERATION_REQUESTED",
  "mode": "PLAN",
  "runId": "74bd1c34-b9ab-45cc-9c1f-3baf1efef1c7",
  "projectId": 2,
  "chatSessionId": 360,
  "baseToolPlanId": 736,
  "planGroupId": 51,
  "basePlanVersion": 1,
  "basePlan": {
    "rawMarkdown": "## Tool Plan\n\n...",
    "structuredPlanJson": {
      "version": 1,
      "blocks": [
        {
          "blockId": "analysis-summary",
          "title": "분석 요약",
          "content": "최근 장애 로그 분석 결과..."
        }
      ]
    },
    "planSnapshot": {
      "schemaVersion": 1,
      "planVersion": 1,
      "title": "장애 로그 분석 Tool",
      "summary": "최근 장애 로그를 수집하고 원인을 분류합니다.",
      "blocks": [
        {
          "blockId": "analysis-summary",
          "title": "분석 요약",
          "content": "최근 장애 로그 분석 결과...",
          "order": 1
        }
      ],
      "createdAt": "2026-05-08T10:18:00"
    }
  },
  "feedbackItems": [
    {
      "blockId": "analysis-summary",
      "comment": "504 에러 원인을 더 구체적으로 나눠줘."
    }
  ],
  "history": [],
  "requestedAt": "2026-05-08T10:20:00"
}
```

## Core PLAN Event Payload

Core Server가 `theseus.tool-plan.event` topic으로 발행한다.

### progress

생성 진행 문구와 진행률을 전달한다. DB에는 저장하지 않고 Redis 최신 상태와 SSE로만 사용한다.

| Field | Type | Required | Description |
| --- | --- | --- | --- |
| `eventType` | string | Y | `progress` |
| `runId` | string | Y | 실행 ID |
| `eventSequence` | number | Y | run 내부 단조 증가 이벤트 순서 |
| `projectId` | number | Y | 프로젝트 ID |
| `chatSessionId` | number | Y | 채팅 세션 ID |
| `stage` | string | Y | 현재 진행 단계 |
| `message` | string | Y | 진행 상태 문구 |
| `progressRate` | number | N | UI 표시용 0-100 정수 추정 진행률 |
| `updatedAt` | datetime string | Y | 이벤트 발생 시각 |

권장 progress 단계:

```text
REQUEST_RECEIVED
INTENT_CHECKING
HISTORY_LOADING
PLAN_DRAFTING
TOOL_CALLING
TOOL_RESULT_READING
PLAN_STRUCTURING
PLAN_VALIDATING
PLAN_COMPLETED
PLAN_SKIPPED
PLAN_FAILED
```

`progressRate`는 같은 run 안에서 감소하지 않는다. 실패나 skipped는 terminal event와 함께 100으로 종료할 수 있다.

### chunk

생성 중인 내용 일부를 전달한다. DB에는 저장하지 않고 Redis 최신 상태와 SSE로만 사용한다.

| Field | Type | Required | Description |
| --- | --- | --- | --- |
| `eventType` | string | Y | `chunk` |
| `runId` | string | Y | 실행 ID |
| `eventSequence` | number | Y | run 내부 단조 증가 이벤트 순서 |
| `projectId` | number | Y | 프로젝트 ID |
| `chatSessionId` | number | Y | 채팅 세션 ID |
| `content` | string | Y | 생성 중인 content |
| `updatedAt` | datetime string | Y | 이벤트 발생 시각 |

`chunk`는 임시 표시용 스트리밍 조각이다. 최종 Assistant 메시지는 `TOOL_PLAN_COMPLETED.assistantMessage`만 저장한다.

### TOOL_PLAN_COMPLETED

PLAN 생성/재생성이 성공했을 때 발행한다.

| Field | Type | Required | Description |
| --- | --- | --- | --- |
| `eventType` | string | Y | `TOOL_PLAN_COMPLETED` |
| `runId` | string | Y | 실행 ID |
| `eventSequence` | number | Y | run 내부 단조 증가 이벤트 순서 |
| `projectId` | number | Y | 프로젝트 ID |
| `chatSessionId` | number | Y | 채팅 세션 ID |
| `assistantMessage` | object | Y | chat_messages에 저장할 Assistant 메시지 |
| `toolPlan` | object | Y | tool_plans에 저장할 PLAN 데이터 |
| `completedAt` | datetime string | N | Core Server 완료 시각 |

#### `assistantMessage`

| Field | Type | Required | Description |
| --- | --- | --- | --- |
| `messageType` | string | Y | `TOOL_PLAN_RESPONSE` |
| `contentType` | string | Y | `MARKDOWN` 또는 `TEXT` |
| `content` | string | Y | 사용자에게 보여줄 Assistant 메시지 |

#### `toolPlan`

| Field | Type | Required | Description |
| --- | --- | --- | --- |
| `rawMarkdown` | string | Y | PLAN 원문 Markdown |
| `structuredPlanJson` | object | Y | 구조화 PLAN JSON |
| `planSnapshot` | object | Y | UI 렌더링과 승인 감사용 PLAN 고정본 |

`structuredPlanJson.blocks[].blockId/title/content`는 필수다.

`planSnapshot`은 Core checkpoint가 아니다. Core checkpoint는 Core PostgreSQL에 `runId` 기준으로 저장한다.

#### `planSnapshot`

| Field | Type | Required | Description |
| --- | --- | --- | --- |
| `schemaVersion` | number | Y | snapshot 구조 버전 |
| `planVersion` | number | Y | `tool_plans.plan_version`과 같은 값 |
| `title` | string | Y | PLAN 카드 제목 |
| `summary` | string | Y | PLAN 요약 |
| `blocks` | array | Y | 화면 렌더링과 피드백 기준 블록 |
| `blocks[].blockId` | string | Y | 블록 식별자 |
| `blocks[].title` | string | Y | 블록 제목 |
| `blocks[].content` | string | Y | 블록 본문 |
| `blocks[].order` | number | Y | 화면 표시 순서 |
| `createdAt` | datetime string | Y | Core completed 기준 생성 시각 |

### TOOL_PLAN_SKIPPED

Core Server가 PLAN 모드 입력을 Tool 명세 생성 대상으로 판단하지 않은 경우 발행한다.

| Field | Type | Required | Description |
| --- | --- | --- | --- |
| `eventType` | string | Y | `TOOL_PLAN_SKIPPED` |
| `runId` | string | Y | 실행 ID |
| `eventSequence` | number | Y | run 내부 단조 증가 이벤트 순서 |
| `projectId` | number | Y | 프로젝트 ID |
| `chatSessionId` | number | Y | 채팅 세션 ID |
| `assistantMessage` | object | Y | 사용자에게 표시할 안내 메시지 |
| `completedAt` | datetime string | N | 종료 시각 |

### TOOL_PLAN_FAILED

PLAN 생성/재생성 실패 시 발행한다.

| Field | Type | Required | Description |
| --- | --- | --- | --- |
| `eventType` | string | Y | `TOOL_PLAN_FAILED` |
| `runId` | string | Y | 실행 ID |
| `eventSequence` | number | Y | run 내부 단조 증가 이벤트 순서 |
| `projectId` | number | Y | 프로젝트 ID |
| `chatSessionId` | number | Y | 채팅 세션 ID |
| `code` | string | Y | 실패 코드 |
| `message` | string | Y | 실패 메시지 |
| `failedAt` | datetime string | N | 실패 시각 |

## Tool Build Request

API Server가 `theseus.tool-build.request` topic으로 발행한다.

| Field | Type | Required | Description |
| --- | --- | --- | --- |
| `eventType` | string | Y | `TOOL_BUILD_REQUESTED` |
| `runId` | string | Y | build 실행 ID |
| `projectId` | number | Y | 프로젝트 ID |
| `chatSessionId` | number | Y | 채팅 세션 ID |
| `toolPlanId` | number | Y | 승인된 PLAN ID |
| `planGroupId` | number | Y | PLAN 그룹 ID |
| `approvedByProjectMemberId` | number | Y | 승인자 프로젝트 멤버 ID |
| `approvedPlan` | object | Y | 승인된 PLAN |
| `requestedAt` | datetime string | Y | 요청 시각 |

## Tool Build Event Payload

Core Server가 `theseus.tool-build.event` topic으로 발행한다.

### TOOL_BUILD_COMPLETED

| Field | Type | Required | Description |
| --- | --- | --- | --- |
| `eventType` | string | Y | `TOOL_BUILD_COMPLETED` |
| `runId` | string | Y | build 실행 ID |
| `eventSequence` | number | Y | run 내부 단조 증가 이벤트 순서 |
| `projectId` | number | Y | 프로젝트 ID |
| `chatSessionId` | number | Y | 채팅 세션 ID |
| `toolPlanId` | number | Y | 승인된 PLAN ID |
| `artifact` | object | Y | 실제 Tool 산출물 정보 |
| `completedAt` | datetime string | N | 완료 시각 |

#### `artifact`

| Field | Type | Required | Description |
| --- | --- | --- | --- |
| `fileName` | string | Y | Tool 파일명 |
| `moduleName` | string | N | 모듈명 |
| `artifactPath` | string | N | 산출물 저장 경로 |
| `codeSnapshot` | string | N | 코드 snapshot |
| `metadataJson` | object | N | 부가 메타데이터 |

### TOOL_BUILD_FAILED

| Field | Type | Required | Description |
| --- | --- | --- | --- |
| `eventType` | string | Y | `TOOL_BUILD_FAILED` |
| `runId` | string | Y | build 실행 ID |
| `projectId` | number | Y | 프로젝트 ID |
| `chatSessionId` | number | Y | 채팅 세션 ID |
| `toolPlanId` | number | Y | 승인된 PLAN ID |
| `code` | string | Y | 실패 코드 |
| `message` | string | Y | 실패 메시지 |
| `failedAt` | datetime string | N | 실패 시각 |

## History 변환 규칙

API Server는 Kafka payload에 최근 대화 history snapshot을 포함한다.

저장 위치:

```text
tool_plan_runs.history_snapshot_json
```

| ChatMessage | Core history role | Core history content |
| --- | --- | --- |
| `senderType = USER`, `messageType = CHAT` | `user` | `content` text |
| `senderType = ASSISTANT`, `messageType = CHAT` | `assistant` | `content` text |
| `TOOL_PLAN_REQUEST` | `user` | PLAN 요청 text |
| `TOOL_PLAN_RESPONSE` | `assistant` | PLAN 요약과 핵심 block text |
| `TOOL_FEEDBACK` | `user` | feedbackItems 요약 text |
| `SYSTEM_NOTICE` | `system` 또는 제외 | 사용자 판단에 필요한 안내만 압축 |

Core 내부 ToolUseBlock, ToolResultBlock은 API history에서 복원하지 않는다. Core 내부 tool-use trace는 Core checkpoint에서 관리한다.

`TOOL_PLAN_RESPONSE` 전체 Markdown이 너무 길면 API Server는 요약본과 `toolPlanId`, `planVersion`, 주요 block title/content만 포함할 수 있다. 원본 PLAN은 재생성 payload의 `basePlan`으로 전달한다.

history는 최근 메시지 개수 또는 token budget 기준으로 제한한다. 오래된 메시지는 요약 메시지로 압축할 수 있다.

## blockId 규칙

- 동일한 의미의 블록은 재생성 후에도 같은 `blockId`를 유지한다.
- 내용이 수정되어도 역할이 같으면 같은 `blockId`를 유지한다.
- 새 의미의 블록은 새 `blockId`를 생성한다.
- 삭제된 블록은 다음 PLAN에서 제외한다.
- 분할된 블록은 기존 `blockId`를 대표 블록 하나에만 유지하고 나머지는 새 `blockId`를 생성한다.
- 병합된 블록은 핵심 의미가 가장 큰 기존 `blockId` 하나를 유지한다.

## Event Ordering

Core Server는 같은 `runId` 안에서 `eventSequence`를 단조 증가시킨다.

```text
eventSequence = 1, 2, 3, ...
```

- `progress`, `chunk`, `completed`, `skipped`, `failed`는 같은 sequence 공간을 사용한다.
- API Server는 이미 처리한 `runId + eventSequence` 이벤트를 다시 처리하지 않는다.
- 늦게 도착한 낮은 sequence 이벤트는 Redis/SSE 최신 상태를 덮어쓰지 않는다.
- `completed`, `skipped`, `failed`는 terminal event다.
- terminal event 이후 같은 run의 progress/chunk는 무시한다.

## 저장 순서

요청은 DB에 먼저 기록한 뒤 Kafka로 발행한다.

```text
ToolPlanRun 저장
ChatMessage 저장
Outbox 저장 또는 after-commit 발행 예약
DB commit
Kafka 발행
```

completed/skipped/failed 이벤트는 DB commit 후 Redis/SSE를 처리한다.

```text
Kafka event 수신
idempotency 확인
DB 상태 변경
ChatMessage 저장
DB commit
Redis 상태 저장
SSE 전송
```

DB commit 전에 Redis/SSE를 먼저 처리하지 않는다.

## Idempotency

Kafka는 at-least-once 전달이 가능하므로 중복 이벤트를 전제로 처리한다.

권장 기준:

```text
tool_plan_runs.run_id unique
runId + eventType
runId + eventSequence
chat_messages.idempotency_key unique
tool_plans(plan_group_id, plan_version) unique
tools.source_tool_plan_id unique
```

중복 completed 처리 규칙:

- `ToolPlanRun.status`가 이미 `COMPLETED`, `SKIPPED`, `FAILED`이면 skip한다.
- 동일 `idempotency_key`의 ChatMessage가 있으면 insert하지 않는다.
- `tools.source_tool_plan_id`가 이미 존재하면 build completed로 Tool을 중복 생성하지 않는다.

## Local Kafka 테스트 절차

### Topic 확인

```bash
docker exec theseus-local-kafka kafka-topics \
  --bootstrap-server localhost:19092 \
  --list
```

필수 topic:

```text
theseus.tool-plan.request
theseus.tool-plan.event
theseus.tool-build.request
theseus.tool-build.event
```

### PLAN request 확인

```bash
docker exec -it theseus-local-kafka kafka-console-consumer \
  --bootstrap-server localhost:19092 \
  --topic theseus.tool-plan.request \
  --from-beginning
```

### mock PLAN completed produce

```bash
docker exec -i theseus-local-kafka kafka-console-producer \
  --bootstrap-server localhost:19092 \
  --topic theseus.tool-plan.event
```

```json
{
  "eventType": "TOOL_PLAN_COMPLETED",
  "runId": "f2adc89f-0ca4-425b-b312-a2ca1ca9b0a7",
  "eventSequence": 10,
  "projectId": 2,
  "chatSessionId": 360,
  "assistantMessage": {
    "messageType": "TOOL_PLAN_RESPONSE",
    "contentType": "MARKDOWN",
    "content": "## Tool Plan\n\n1. 로그 수집\n2. 장애 원인 분석"
  },
  "toolPlan": {
    "rawMarkdown": "## Tool Plan\n\n1. 로그 수집\n2. 장애 원인 분석",
    "structuredPlanJson": {
      "version": 1,
      "blocks": [
        {
          "blockId": "analysis-summary",
          "title": "분석 요약",
          "content": "최근 장애 로그를 수집하고 원인을 분류합니다."
        }
      ]
    },
    "planSnapshot": {
      "schemaVersion": 1,
      "planVersion": 1,
      "title": "장애 로그 분석 Tool",
      "summary": "최근 장애 로그를 수집하고 원인을 분류합니다.",
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
  },
  "completedAt": "2026-05-08T10:21:00"
}
```

### Redis state 확인

```bash
docker exec theseus-local-redis redis-cli GET tool:plan:{runId}:state
```

### SSE 수신 확인

```bash
curl -N \
  -H "Authorization: Bearer {accessToken}" \
  http://localhost:8080/api/v1/projects/{projectId}/sessions/{sessionId}/tool-plan-runs/{runId}/events
```

## AI 담당자 체크리스트

- Core는 API 내부 HTTP로 PLAN이나 history를 조회하지 않는다.
- Core는 Kafka payload의 `history`, `basePlan`, `feedbackItems`를 사용한다.
- PLAN 모드 입력이 Tool 명세 대상이 아니면 `TOOL_PLAN_SKIPPED`를 발행한다.
- PLAN 재생성 결과는 최신 전체 PLAN을 반환한다.
- `structuredPlanJson.blocks[].blockId/title/content`를 보장한다.
- 같은 의미의 블록은 재생성 후에도 같은 `blockId`를 유지한다.
- Core 내부 StateMachine checkpoint는 Core PostgreSQL에 저장한다.
- failed 이벤트는 `code`, `message`를 사용한다.
