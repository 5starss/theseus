# Tool API

## 공통 규칙

- 인증이 필요한 요청은 `Authorization: Bearer {accessToken}`을 사용한다.
- Tool 생성, 사용, 수정, 삭제 권한은 `project_members`의 Boolean 권한으로 판단한다.
- Tool 승인과 반려는 프로젝트 `ADMIN` 또는 `MANAGER`가 수행한다.
- 승인된 Tool 접근 가능 여부는 `project_members.access_level >= tools.tool_grade`로 판단한다.
- 한 채팅 세션에서 여러 Tool을 생성할 수 있다.
- Tool 생성 또는 수정과 관련된 메시지는 `chat_messages.tool_id`로 해당 Tool에 연결한다.
- AI 생성 중 progress/chunk는 Redis와 SSE로만 전달하고 `chat_messages`에는 저장하지 않는다.
- 최종 USER, ASSISTANT, SYSTEM 메시지만 `chat_messages`에 저장한다.

## 상태 값

| 구분 | 값 |
| --- | --- |
| `toolStatus` | `DRAFT`, `PENDING`, `REJECTED`, `APPROVED`, `DELETED` |
| `draftPhase` | `PLAN`, `REVIEW` |
| `approvalStatus` | `PENDING`, `REJECTED`, `APPROVED` |
| `senderType` | `USER`, `ASSISTANT`, `SYSTEM` |
| `messageType` | `CHAT`, `TOOL_DRAFT_REQUEST`, `TOOL_DRAFT_RESPONSE`, `TOOL_FEEDBACK`, `TOOL_REGENERATE_RESPONSE`, `TOOL_APPROVAL_REQUEST`, `SYSTEM_NOTICE` |
| `contentType` | `TEXT`, `MARKDOWN`, `JSON` |

`messageType`은 메시지가 속한 업무 흐름을 나타낸다. `contentType`은 메시지 본문을 렌더링하거나 파싱할 형식을 나타낸다. 숫자, 배열, 객체 같은 구조화된 값은 `contentType = JSON`으로 저장한다.

Draft Tool의 PLAN은 `tools.structured_plan_json`에 구조화된 JSON으로 저장한다. PLAN JSON은 `version`과 `blocks[].blockId`를 포함할 수 있다. 오래된 PLAN 피드백 여부는 `structured_plan_json.version`이 아니라 `tools.draft_version`을 기준으로 검증한다. `blockId`는 블록별 피드백을 기존 PLAN 블록과 매칭하기 위한 식별자다.

## Tool 목록 조회

```http
GET /api/v1/projects/{projectId}/tools?scope=accessible&status=APPROVED&page=0&size=20
Accept: application/json
Authorization: Bearer {accessToken}
```

### 권한

- 프로젝트 멤버
- `project_members.status = 진행중`
- `project_members.can_use_tool = true`

### Query Parameters

| 이름 | 필수 | 기본값 | 설명 |
| --- | --- | --- | --- |
| `scope` | N | `accessible` | 접근 가능한 Tool만 조회한다. |
| `status` | N | `APPROVED` | 승인된 Tool만 조회한다. |
| `page` | N | `0` | 0부터 시작하는 페이지 번호다. |
| `size` | N | `20` | 페이지 크기다. |

### 동작

- `scope`는 `accessible`만 지원한다.
- `status`는 `APPROVED`만 지원한다.
- `tools.tool_grade IS NULL`이거나 `project_members.access_level >= tools.tool_grade`인 Tool만 조회한다.
- `tools.updated_at DESC` 순서로 조회한다.

### Response Body

```json
{
  "isSuccess": true,
  "code": "COMMON-200",
  "message": "성공입니다.",
  "result": {
    "content": [
      {
        "toolId": 7,
        "projectId": 1,
        "chatSessionId": 10,
        "createdByProjectMemberId": 3,
        "createdByUserId": 5,
        "createdByUserName": "홍길동",
        "fileName": "sales-summary-tool",
        "displayName": "매출 요약 Tool",
        "displayDescription": "CSV 매출 데이터를 요약합니다.",
        "status": "APPROVED",
        "draftPhase": "REVIEW",
        "draftVersion": 1,
        "toolGrade": 2,
        "createdAt": "2026-04-30T10:00:00",
        "updatedAt": "2026-04-30T10:10:00"
      }
    ],
    "page": 0,
    "size": 20,
    "totalElements": 1,
    "totalPages": 1
  }
}
```

## Tool 상세 조회

```http
GET /api/v1/projects/{projectId}/tools/{toolId}
Accept: application/json
Authorization: Bearer {accessToken}
```

### 권한

- 프로젝트 멤버
- `project_members.status = 진행중`
- `project_members.can_use_tool = true`
- `tools.status = APPROVED`
- `tools.tool_grade IS NULL` 또는 `project_members.access_level >= tools.tool_grade`

### Response Body

```json
{
  "isSuccess": true,
  "code": "COMMON-200",
  "message": "성공입니다.",
  "result": {
    "toolId": 7,
    "projectId": 1,
    "chatSessionId": 10,
    "createdByProjectMemberId": 3,
    "createdByUserId": 5,
    "createdByUserName": "홍길동",
    "fileName": "sales-summary-tool",
    "displayName": "매출 요약 Tool",
    "displayDescription": "CSV 매출 데이터를 요약합니다.",
    "status": "APPROVED",
    "draftPhase": "REVIEW",
    "draftVersion": 1,
    "toolGrade": 2,
    "rawMarkdown": "## Tool Plan...",
    "structuredPlanJson": "{\"steps\":[]}",
    "draftSnapshot": "{\"version\":1}",
    "createdAt": "2026-04-30T10:00:00",
    "updatedAt": "2026-04-30T10:10:00"
  }
}
```

## Draft Tool 생성

```http
POST /api/v1/projects/{projectId}/sessions/{sessionId}/tools/generate
Accept: application/json
Content-Type: application/json
Authorization: Bearer {accessToken}
```

### 권한

- 프로젝트 멤버
- `project_members.status = 진행중`
- `project_members.can_create_tool = true`

### Request Body

```json
{
  "userMessage": "CSV 파일을 업로드하면 매출 합계를 계산하는 Tool을 만들어줘.",
  "fileName": "sales-summary-tool"
}
```

### Response Body

```json
{
  "isSuccess": true,
  "code": 202,
  "message": "Draft Tool 생성을 시작하였습니다.",
  "result": {
    "runId": "3f2a2d5e-0e4a-4a3f-8d0f-9b5a3e2c0d11",
    "toolId": 7,
    "projectId": 1,
    "sessionId": 10,
    "status": "DRAFT",
    "draftPhase": "PLAN",
    "draftVersion": 0,
    "sseUrl": "/api/v1/projects/1/sessions/10/tools/7/events"
  }
}
```

### 동작

- BE가 Access Token, 프로젝트 멤버, Tool 생성 권한을 검증한다.
- BE가 `tools.status = DRAFT`, `tools.draft_phase = PLAN`인 Tool을 생성한다.
- BE가 AI 생성 실행 ID인 `runId`를 생성한다.
- Redis 진행 상태와 SSE 복구 기준은 `toolId`다.
- BE가 Kafka에 USER 메시지 저장 이벤트를 발행한다.
- BE가 AI 서버에 `runId`, `projectId`, `chatSessionId`, `toolId`, `prompt`를 포함해 생성 요청한다.
- AI progress/chunk는 `tool:generation:{toolId}:state`에 최신 상태로 저장하고 SSE로 FE에 전달한다.
- AI 완료 후 BE가 전체 응답을 취합하고 Kafka에 완료 이벤트를 발행한다.
- Kafka Consumer가 최종 ASSISTANT 메시지를 저장하고 Tool draft 데이터를 갱신한다.
- Kafka Consumer가 `tools.draft_phase = REVIEW`로 변경한다.
- 저장과 상태 변경이 끝난 뒤 `completed` 이벤트를 FE에 전달한다.

## Draft Tool 재생성

```http
PATCH /api/v1/projects/{projectId}/sessions/{sessionId}/tools/{toolId}/regenerate
Accept: application/json
Content-Type: application/json
Authorization: Bearer {accessToken}
```

### 권한

- Tool 생성자 또는 `can_update_tool = true`인 프로젝트 멤버
- `tools.status = DRAFT` 또는 `REJECTED`
- `tools.draft_phase = REVIEW`

### Request Body

```json
{
  "baseDraftVersion": 1,
  "feedbackItems": [
    {
      "blockId": "input-format",
      "comment": "입력 파일 형식을 xlsx도 허용하도록 수정해줘."
    },
    {
      "blockId": "error-handling",
      "comment": "파일 파싱 실패 시 사용자에게 원인을 보여줘."
    }
  ]
}
```

### Response Body

```json
{
  "isSuccess": true,
  "code": 202,
  "message": "Draft Tool 재생성을 시작하였습니다.",
  "result": {
    "runId": "74bd2d5e-0e4a-4a3f-8d0f-9b5a3e2c0d22",
    "toolId": 7,
    "projectId": 1,
    "sessionId": 10,
    "status": "DRAFT",
    "draftPhase": "PLAN",
    "draftVersion": 1,
    "sseUrl": "/api/v1/projects/1/sessions/10/tools/7/events"
  }
}
```

### 동작

- 사용자 첨삭 메시지는 `TOOL_FEEDBACK`, `JSON`으로 저장한다.
- `baseDraftVersion`은 사용자가 피드백한 시점의 `tools.draft_version` 값이다.
- `feedbackItems[].blockId`는 `structured_plan_json.blocks[].blockId`와 매칭한다.
- 완성된 PLAN을 확인한 뒤 피드백하는 흐름이므로 `draft_phase = REVIEW`인 Tool만 재생성할 수 있다.
- 현재 Tool의 `tools.draft_version`과 `baseDraftVersion`이 다르면 재생성을 시작하지 않는다.
- 대상 Tool은 AI 재생성 시작 시 `draft_phase = PLAN`으로 변경한다.
- 재생성마다 새 `runId`를 발급한다.
- 최종 Assistant 응답은 `TOOL_REGENERATE_RESPONSE`로 저장한다.
- 수정된 계획 또는 명세가 저장되면 `draft_phase = REVIEW`로 변경한다.

## AI 생성 이벤트 구독

```http
GET /api/v1/projects/{projectId}/sessions/{sessionId}/tools/{toolId}/events
Accept: text/event-stream
Authorization: Bearer {accessToken}
```

### 권한

- 해당 프로젝트의 활성 프로젝트 멤버
- `sessionId`가 해당 `projectId`에 속해야 한다.
- `toolId`가 해당 `projectId`와 `sessionId`에 속해야 한다.

연결 직후 `connected` 이벤트를 전송한다. Redis에 `tool:generation:{toolId}:state` 최신 상태가 있으면 현재 상태 이벤트를 최초 1회 전송한다. 주기적 `heartbeat` 이벤트는 후속 이슈에서 구현한다.

### Event: connected

```text
event: connected
data: {"eventType":"connected","projectId":1,"chatSessionId":10,"toolId":7,"message":"connected"}
```

### Event: progress

```text
event: progress
data: {"eventType":"progress","projectId":1,"chatSessionId":10,"toolId":7,"status":"GENERATING","draftPhase":"PLAN","progressRate":35,"message":"입력 파일 구조를 분석하고 있습니다."}
```

### Event: chunk

```text
event: chunk
data: {"eventType":"chunk","projectId":1,"chatSessionId":10,"toolId":7,"status":"GENERATING","draftPhase":"PLAN","content":"## Tool Plan\n\n1. CSV 업로드..."}
```

### Event: completed

```text
event: completed
data: {"eventType":"completed","projectId":1,"chatSessionId":10,"toolId":7,"status":"COMPLETED","draftPhase":"REVIEW","draftVersion":1}
```

### Event: failed

```text
event: failed
data: {"eventType":"failed","projectId":1,"chatSessionId":10,"toolId":7,"status":"FAILED","errorCode":"AI_GENERATION_FAILED","errorMessage":"Tool 초안 생성에 실패했습니다."}
```

## AI 생성 상태 복구

- 별도 `runId` 상태 조회 API는 제공하지 않는다.
- FE는 `GET /api/v1/projects/{projectId}/sessions/{sessionId}/tools/{toolId}/events`로 다시 연결한다.
- BE는 Redis의 `tool:generation:{toolId}:state` 최신 상태가 있으면 연결 직후 최초 상태 이벤트로 전송한다.
- Redis TTL이 만료되면 FE는 Tool 상세 조회와 ChatMessage 목록 조회로 최종 DB 상태를 복구한다.
- `runId`는 Kafka/Core 이벤트 추적용 실행 ID이며 FE SSE 구독/복구 기준이 아니다.

## Tool 승인 요청

```http
POST /api/v1/projects/{projectId}/tools/{toolId}/approval-requests
Accept: application/json
Authorization: Bearer {accessToken}
```

### 권한

- Tool 생성자
- `tools.status = DRAFT`
- `tools.draft_phase = REVIEW`

### 동작

- `tool_approvals`에 `approval_status = PENDING`인 승인 요청을 생성한다.
- `request_number`는 같은 Tool 안에서 1부터 증가한다.
- `tools.status = PENDING`으로 변경한다.
- 승인 요청 메시지는 `message_type = TOOL_APPROVAL_REQUEST`, `content_type = JSON`으로 저장한다.

## 승인 이력 조회

```http
GET /api/v1/projects/{projectId}/tools/{toolId}/approval-requests
Accept: application/json
Authorization: Bearer {accessToken}
```

### 권한

- 프로젝트 멤버

## 승인 요청 목록 조회

```http
GET /api/v1/projects/{projectId}/tool-approvals?approvalStatus=PENDING&page=0&size=20
Accept: application/json
Authorization: Bearer {accessToken}
```

### 권한

- 프로젝트 `ADMIN`
- 프로젝트 `MANAGER`
- `project_members.status = 진행중`

### Query Parameters

| 이름 | 필수 | 기본값 | 설명 |
| --- | --- | --- | --- |
| `approvalStatus` | N | 없음 | `PENDING`, `APPROVED`, `REJECTED` 중 하나로 필터링한다. 생략하면 전체 승인 요청을 조회한다. |
| `page` | N | `0` | 0부터 시작하는 페이지 번호다. |
| `size` | N | `20` | 페이지 크기다. |

### 동작

- 프로젝트 `ADMIN` 또는 `MANAGER`만 조회할 수 있다.
- `approvalStatus`가 전달되면 해당 상태의 승인 요청만 조회한다.
- `approvalStatus`가 전달되지 않으면 프로젝트의 전체 승인 요청을 조회한다.
- `requested_at DESC` 순서로 조회한다.

### Response Body

```json
{
  "isSuccess": true,
  "code": "COMMON-200",
  "message": "성공입니다.",
  "result": {
    "content": [
      {
        "toolApprovalId": 11,
        "projectId": 1,
        "toolId": 7,
        "fileName": "sales-summary-tool",
        "displayName": "매출 요약 Tool",
        "requestNumber": 1,
        "approvalStatus": "PENDING",
        "requestedByProjectMemberId": 3,
        "requestedByUserId": 5,
        "requestedByUserName": "홍길동",
        "reviewedByProjectMemberId": null,
        "reviewedByUserId": null,
        "reviewedByUserName": null,
        "reviewFeedback": null,
        "requestedAt": "2026-04-30T10:20:00",
        "reviewedAt": null,
        "toolStatus": "PENDING",
        "draftPhase": "REVIEW"
      }
    ],
    "page": 0,
    "size": 20,
    "totalElements": 1,
    "totalPages": 1
  }
}
```

## 승인 요청 상세 조회

```http
GET /api/v1/projects/{projectId}/tool-approvals/{toolApprovalId}
Accept: application/json
Authorization: Bearer {accessToken}
```

### 권한

- 프로젝트 `ADMIN`
- 프로젝트 `MANAGER`
- `project_members.status = 진행중`

### 동작

- 프로젝트 `ADMIN` 또는 `MANAGER`만 조회할 수 있다.
- 요청한 `toolApprovalId`가 해당 프로젝트에 속하지 않으면 조회할 수 없다.

### Response Body

```json
{
  "isSuccess": true,
  "code": "COMMON-200",
  "message": "성공입니다.",
  "result": {
    "toolApprovalId": 11,
    "projectId": 1,
    "toolId": 7,
    "fileName": "sales-summary-tool",
    "displayName": "매출 요약 Tool",
    "requestNumber": 1,
    "approvalStatus": "PENDING",
    "requestedByProjectMemberId": 3,
    "requestedByUserId": 5,
    "requestedByUserName": "홍길동",
    "reviewedByProjectMemberId": null,
    "reviewedByUserId": null,
    "reviewedByUserName": null,
    "reviewFeedback": null,
    "requestedAt": "2026-04-30T10:20:00",
    "reviewedAt": null,
    "toolStatus": "PENDING",
    "draftPhase": "REVIEW"
  }
}
```

## Tool 승인

```http
PATCH /api/v1/projects/{projectId}/tool-approvals/{toolApprovalId}/approve
Accept: application/json
Content-Type: application/json
Authorization: Bearer {accessToken}
```

### Request Body

```json
{
  "toolGrade": 3,
  "reviewFeedback": "승인합니다."
}
```

### 동작

- `tool_approvals.approval_status = APPROVED`로 변경한다.
- `tool_approvals.reviewed_by_project_member_id`에 검토자를 저장한다.
- `tools.status = APPROVED`로 변경한다.
- `tools.tool_grade`를 저장한다.

## Tool 반려

```http
PATCH /api/v1/projects/{projectId}/tool-approvals/{toolApprovalId}/reject
Accept: application/json
Content-Type: application/json
Authorization: Bearer {accessToken}
```

### Request Body

```json
{
  "reviewFeedback": "보안 검증 단계가 더 필요합니다."
}
```

### 동작

- `tool_approvals.approval_status = REJECTED`로 변경한다.
- `tool_approvals.reviewed_by_project_member_id`에 검토자를 저장한다.
- `tools.status = REJECTED`로 변경한다.
- 반려 이후 생성자는 Draft Tool 재생성 API로 계획을 수정할 수 있다.
