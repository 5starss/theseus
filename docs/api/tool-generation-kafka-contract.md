# Tool Generation Kafka Payload Contract

## 전체 흐름

Tool 생성과 재생성은 FE, API Server, Core Server가 아래 흐름으로 처리한다.

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
- API Server는 인증, 프로젝트 접근 권한, Tool 생성/수정 권한을 검증한다.
- API Server는 Tool row 생성, 사용자 메시지 저장, Kafka 요청 이벤트 발행을 담당한다.
- Core Server는 Kafka 요청 이벤트를 consume하고 Tool PLAN 생성/재생성을 수행한다.
- Core Server는 진행 이벤트와 완료/실패 이벤트를 Kafka로 발행한다.
- API Server는 Core 이벤트를 consume하고 Redis 상태 저장, DB 최종 반영, SSE 전달을 담당한다.
- Core Server는 재생성 시 API Server 내부 HTTP로 Draft를 조회하지 않고 Kafka payload의 `baseDraft`를 사용한다.

## Kafka Topic

| Topic | Producer | Consumer | 용도 |
| --- | --- | --- | --- |
| `theseus.tool-generation.request` | API Server | Core Server | 최초 Tool PLAN 생성 요청 |
| `theseus.tool-regeneration.request` | API Server | Core Server | 기존 Tool PLAN 재생성 요청 |
| `theseus.tool-generation.event` | Core Server | API Server | progress, chunk, completed, failed 이벤트 |

Kafka key는 현재 `runId`를 사용한다.

## Generate Request Payload

API Server가 `theseus.tool-generation.request` topic으로 발행한다.

### 필드

| Field | Type | Required | Description |
| --- | --- | --- | --- |
| `eventType` | string | Y | `TOOL_GENERATION_REQUESTED` |
| `runId` | string | Y | Tool 생성 실행 1회 식별자 |
| `projectId` | number | Y | 프로젝트 ID |
| `chatSessionId` | number | Y | 채팅 세션 ID |
| `toolId` | number | Y | 생성된 Tool ID |
| `requestedByUserId` | number | Y | 요청 사용자 ID |
| `requestedByProjectMemberId` | number | Y | 요청 프로젝트 멤버 ID |
| `prompt` | string | Y | 사용자가 입력한 Tool 생성 요청 |
| `fileName` | string | Y | Tool 파일명 |
| `projectRole` | string | Y | 요청자의 프로젝트 역할 |
| `toolPermission` | object | Y | 요청자의 Tool 권한 |
| `requestedAt` | datetime | Y | API Server 요청 생성 시각 |

### 예시

```json
{
  "eventType": "TOOL_GENERATION_REQUESTED",
  "runId": "f2adc89f-0ca4-425b-b312-a2ca1ca9b0a7",
  "projectId": 2,
  "chatSessionId": 360,
  "toolId": 736,
  "requestedByUserId": 8,
  "requestedByProjectMemberId": 2,
  "prompt": "장애 로그를 분석하고 자동 복구 가이드를 만드는 Tool을 만들어줘.",
  "fileName": "incident-recovery-guide",
  "projectRole": "ADMIN",
  "toolPermission": {
    "canCreateTool": true,
    "canUseTool": true,
    "canUpdateTool": true,
    "canDeleteTool": true
  },
  "requestedAt": "2026-05-08T10:15:08"
}
```

## Regenerate Request Payload

API Server가 `theseus.tool-regeneration.request` topic으로 발행한다.

### 필드

| Field | Type | Required | Description |
| --- | --- | --- | --- |
| `eventType` | string | Y | `TOOL_REGENERATION_REQUESTED` |
| `runId` | string | Y | Tool 재생성 실행 1회 식별자 |
| `projectId` | number | Y | 프로젝트 ID |
| `chatSessionId` | number | Y | 채팅 세션 ID |
| `toolId` | number | Y | 재생성 대상 Tool ID |
| `requestedByUserId` | number | Y | 요청 사용자 ID |
| `requestedByProjectMemberId` | number | Y | 요청 프로젝트 멤버 ID |
| `baseDraftVersion` | number | Y | 사용자가 피드백한 Draft 버전 |
| `feedbackItems` | array | Y | 블록별 피드백 목록 |
| `baseDraft` | object | Y | 재생성 기준 Draft |
| `projectRole` | string | Y | 요청자의 프로젝트 역할 |
| `toolPermission` | object | Y | 요청자의 Tool 권한 |
| `requestedAt` | datetime | Y | API Server 요청 생성 시각 |

### `feedbackItems`

| Field | Type | Required | Description |
| --- | --- | --- | --- |
| `blockId` | string | Y | 피드백 대상 PLAN block ID |
| `comment` | string | Y | 사용자 피드백 내용 |

### `baseDraft`

현재 API Server는 재생성 요청에 아래 Draft 데이터를 포함한다.

| Field | Type | Required | Description |
| --- | --- | --- | --- |
| `rawMarkdown` | string \| null | N | 현재 Draft 원문 Markdown |
| `structuredPlanJson` | object | Y | 현재 Draft 구조화 PLAN JSON |
| `draftSnapshot` | object \| null | N | 현재 Draft snapshot |

Core Server는 재생성 시 `baseDraft.structuredPlanJson`과 `feedbackItems`를 사용해 최신 전체 PLAN을 다시 생성한다.

### 예시

```json
{
  "eventType": "TOOL_REGENERATION_REQUESTED",
  "runId": "74bd1c34-b9ab-45cc-9c1f-3baf1efef1c7",
  "projectId": 2,
  "chatSessionId": 360,
  "toolId": 736,
  "requestedByUserId": 8,
  "requestedByProjectMemberId": 2,
  "baseDraftVersion": 1,
  "feedbackItems": [
    {
      "blockId": "analysis-summary",
      "comment": "504 에러 원인을 더 구체적으로 나눠줘."
    }
  ],
  "baseDraft": {
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
    "draftSnapshot": {
      "version": 1
    }
  },
  "projectRole": "ADMIN",
  "toolPermission": {
    "canCreateTool": true,
    "canUseTool": true,
    "canUpdateTool": true,
    "canDeleteTool": true
  },
  "requestedAt": "2026-05-08T10:20:00"
}
```

## Core Event Payload

Core Server가 `theseus.tool-generation.event` topic으로 발행한다.

### progress

생성 진행 문구와 진행률을 전달한다. DB에는 저장하지 않고 Redis 최신 상태와 SSE로만 사용한다.

| Field | Type | Required | Description |
| --- | --- | --- | --- |
| `eventType` | string | Y | `progress` |
| `runId` | string | Y | 실행 ID |
| `projectId` | number | Y | 프로젝트 ID |
| `chatSessionId` | number | Y | 채팅 세션 ID |
| `toolId` | number | Y | Tool ID |
| `message` | string | Y | 진행 상태 문구 |
| `progressRate` | number | Y | 진행률. API Server는 그대로 Redis/SSE에 반영한다. |

### chunk

생성 중인 내용 일부를 전달한다. DB에는 저장하지 않고 Redis 최신 상태와 SSE로만 사용한다.

| Field | Type | Required | Description |
| --- | --- | --- | --- |
| `eventType` | string | Y | `chunk` |
| `runId` | string | Y | 실행 ID |
| `projectId` | number | Y | 프로젝트 ID |
| `chatSessionId` | number | Y | 채팅 세션 ID |
| `toolId` | number | Y | Tool ID |
| `content` | string | Y | 생성 중인 content |

### TOOL_GENERATION_COMPLETED

PLAN 생성/재생성이 성공했을 때 발행한다.

| Field | Type | Required | Description |
| --- | --- | --- | --- |
| `eventType` | string | Y | `TOOL_GENERATION_COMPLETED` |
| `runId` | string | Y | 실행 ID |
| `projectId` | number | Y | 프로젝트 ID |
| `chatSessionId` | number | Y | 채팅 세션 ID |
| `toolId` | number | Y | Tool ID |
| `assistantMessage` | object | Y | chat_messages에 저장할 Assistant 메시지 |
| `toolDraft` | object | Y | tools 테이블에 반영할 Draft 데이터 |
| `completedAt` | datetime | N | Core Server 완료 시각 |

#### `assistantMessage`

| Field | Type | Required | Description |
| --- | --- | --- | --- |
| `messageType` | string | Y | 최초 생성 완료: `TOOL_DRAFT_RESPONSE`, 재생성 완료: `TOOL_REGENERATE_RESPONSE` |
| `contentType` | string | Y | 현재 계약: `MARKDOWN` |
| `content` | string | Y | 사용자에게 보여줄 Assistant 메시지 |

#### `toolDraft`

| Field | Type | Required | Description |
| --- | --- | --- | --- |
| `rawMarkdown` | string | Y | Draft Markdown 원문 |
| `structuredPlanJson` | object | Y | 구조화 PLAN JSON |
| `draftSnapshot` | object | Y | Draft snapshot |

`structuredPlanJson.blocks[]`는 Core Server가 아래 필드를 보장한다.

| Field | Type | Required | Description |
| --- | --- | --- | --- |
| `blockId` | string | Y | 블록별 피드백 대상 ID |
| `title` | string | Y | PLAN block 제목 |
| `content` | string | Y | PLAN block 본문 |

### completed 예시

```json
{
  "eventType": "TOOL_GENERATION_COMPLETED",
  "runId": "f2adc89f-0ca4-425b-b312-a2ca1ca9b0a7",
  "projectId": 2,
  "chatSessionId": 360,
  "toolId": 736,
  "assistantMessage": {
    "messageType": "TOOL_DRAFT_RESPONSE",
    "contentType": "MARKDOWN",
    "content": "## Tool Plan\n\n..."
  },
  "toolDraft": {
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
    "draftSnapshot": {
      "version": 1
    }
  },
  "completedAt": "2026-05-08T10:21:00Z"
}
```

API Server는 completed 이벤트 처리 성공 후 아래 작업을 수행한다.

```text
Tool draft 데이터 갱신
-> Tool draftPhase = REVIEW
-> Tool draftVersion 증가
-> ASSISTANT chat_messages 저장
-> Redis completed state 저장
-> SSE completed 전달
```

### TOOL_GENERATION_FAILED

PLAN 생성/재생성이 실패했을 때 발행한다.

| Field | Type | Required | Description |
| --- | --- | --- | --- |
| `eventType` | string | Y | `TOOL_GENERATION_FAILED` |
| `runId` | string | Y | 실행 ID |
| `projectId` | number | Y | 프로젝트 ID |
| `chatSessionId` | number | Y | 채팅 세션 ID |
| `toolId` | number | Y | Tool ID |
| `code` | string | Y | 실패 코드 |
| `message` | string | Y | 실패 메시지 |
| `failedAt` | datetime | N | Core Server 실패 시각 |

### failed 예시

```json
{
  "eventType": "TOOL_GENERATION_FAILED",
  "runId": "f2adc89f-0ca4-425b-b312-a2ca1ca9b0a7",
  "projectId": 2,
  "chatSessionId": 360,
  "toolId": 736,
  "code": "AI_GENERATION_FAILED",
  "message": "Tool PLAN 생성에 실패했습니다.",
  "failedAt": "2026-05-08T10:22:00Z"
}
```

API Server는 failed 이벤트 처리 후 아래 작업을 수행한다.

```text
Tool 상태를 재시도 가능한 PLAN 단계로 유지
-> SYSTEM_NOTICE chat_messages 저장
-> Redis failed state 저장
-> SSE failed 전달
```

## Local Kafka Test

아래 명령은 `infra/docker/local` 기준 local Docker Compose 환경에서 실행한다.

### 1. Topic 확인

```bash
docker exec theseus-local-kafka kafka-topics \
  --bootstrap-server theseus-local-kafka:29092 \
  --list
```

```bash
docker exec theseus-local-kafka kafka-topics \
  --bootstrap-server theseus-local-kafka:29092 \
  --describe \
  --topic theseus.tool-generation.request
```

```bash
docker exec theseus-local-kafka kafka-topics \
  --bootstrap-server theseus-local-kafka:29092 \
  --describe \
  --topic theseus.tool-regeneration.request
```

```bash
docker exec theseus-local-kafka kafka-topics \
  --bootstrap-server theseus-local-kafka:29092 \
  --describe \
  --topic theseus.tool-generation.event
```

### 2. Generate request 발행 확인

FE 또는 Swagger에서 아래 API를 호출한다.

```http
POST /api/v1/projects/{projectId}/sessions/{sessionId}/tools/generate
```

request topic을 확인한다.

```bash
docker exec theseus-local-kafka kafka-console-consumer \
  --bootstrap-server theseus-local-kafka:29092 \
  --topic theseus.tool-generation.request \
  --from-beginning \
  --timeout-ms 10000
```

### 3. Regenerate request 발행 확인

FE 또는 Swagger에서 아래 API를 호출한다.

```http
PATCH /api/v1/projects/{projectId}/sessions/{sessionId}/tools/{toolId}/regenerate
```

regeneration request topic을 확인한다.

```bash
docker exec theseus-local-kafka kafka-console-consumer \
  --bootstrap-server theseus-local-kafka:29092 \
  --topic theseus.tool-regeneration.request \
  --from-beginning \
  --timeout-ms 10000
```

### 4. Mock completed event produce

아래 값은 실제 DB에 존재하는 `projectId`, `chatSessionId`, `toolId`, `runId`로 바꿔서 사용한다.

```bash
cat <<'JSON' | docker exec -i theseus-local-kafka kafka-console-producer \
  --bootstrap-server theseus-local-kafka:29092 \
  --topic theseus.tool-generation.event
{"eventType":"TOOL_GENERATION_COMPLETED","runId":"f2adc89f-0ca4-425b-b312-a2ca1ca9b0a7","projectId":2,"chatSessionId":360,"toolId":736,"assistantMessage":{"messageType":"TOOL_DRAFT_RESPONSE","contentType":"MARKDOWN","content":"## Tool Plan\n\n1. 로그 수집\n2. 장애 원인 분석\n3. 복구 가이드 생성"},"toolDraft":{"rawMarkdown":"## Tool Plan\n\n1. 로그 수집\n2. 장애 원인 분석\n3. 복구 가이드 생성","structuredPlanJson":{"version":1,"blocks":[{"blockId":"analysis-summary","title":"분석 요약","content":"최근 장애 로그를 수집하고 원인을 분류합니다."}]},"draftSnapshot":{"version":1}},"completedAt":"2026-05-08T10:21:00Z"}
JSON
```

### 5. Mock failed event produce

아래 값은 실제 DB에 존재하는 `projectId`, `chatSessionId`, `toolId`, `runId`로 바꿔서 사용한다.

```bash
cat <<'JSON' | docker exec -i theseus-local-kafka kafka-console-producer \
  --bootstrap-server theseus-local-kafka:29092 \
  --topic theseus.tool-generation.event
{"eventType":"TOOL_GENERATION_FAILED","runId":"f2adc89f-0ca4-425b-b312-a2ca1ca9b0a7","projectId":2,"chatSessionId":360,"toolId":736,"code":"AI_GENERATION_FAILED","message":"Tool PLAN 생성에 실패했습니다.","failedAt":"2026-05-08T10:22:00Z"}
JSON
```

### 6. Redis state 확인

```bash
docker exec theseus-local-redis redis-cli GET tool:generation:{toolId}:state
```

예시:

```bash
docker exec theseus-local-redis redis-cli GET tool:generation:736:state
```

### 7. SSE 수신 확인

FE는 Tool 생성/재생성 API 응답의 `sseUrl`로 SSE를 구독한다.

```http
GET /api/v1/projects/{projectId}/sessions/{sessionId}/tools/{toolId}/events
Authorization: Bearer {accessToken}
Accept: text/event-stream
```

SSE 연결 직후 API Server는 `connected` 이벤트를 전송한다. Redis에 최신 상태가 있으면 해당 상태를 최초 1회 추가 전송한다.

## AI 담당자 구현 체크리스트

- Core Server는 API Server 내부 HTTP로 Draft를 조회하지 않는다.
- Core Server는 재생성 시 Kafka payload의 `baseDraft`를 사용한다.
- Core Server는 재생성 결과로 변경 블록만이 아니라 최신 전체 PLAN을 반환한다.
- Core Server는 생성 완료 시 `assistantMessage.messageType = TOOL_DRAFT_RESPONSE`를 사용한다.
- Core Server는 재생성 완료 시 `assistantMessage.messageType = TOOL_REGENERATE_RESPONSE`를 사용한다.
- Core Server는 실패 이벤트에 `code`와 `message`를 포함한다.
- Core Server는 `structuredPlanJson.blocks[].blockId/title/content`를 포함한 PLAN 구조를 반환한다.

## TODO

- `baseDraft`에 DB 기준 `draftVersion`을 직접 포함할지 검토한다.
- failed 이벤트의 `code/message`를 `errorCode/errorMessage`로 통일할지 검토한다.
- Kafka key를 `runId`로 유지할지 `toolId`로 변경할지 검토한다.
