# Tool / ToolPlan API

## 공통 규칙

- 인증이 필요한 요청은 `Authorization: Bearer {accessToken}`을 사용한다.
- FE는 API Server와만 HTTP/SSE로 통신한다.
- API Server와 Core Server 사이의 PLAN 생성, 재생성, Tool build는 Kafka로 통신한다.
- PLAN 모드 요청은 Tool 생성 요청이 아니라 Tool PLAN 후보 생성 요청이다.
- 승인 전에는 `tools` row를 생성하지 않는다.
- 승인 대상은 `toolId`가 아니라 `toolPlanId`다.
- 실제 Tool은 승인된 ToolPlan을 기반으로 Core Server가 코드/파일 산출물 생성을 완료한 뒤 생성된다.
- AI 생성 중 progress/chunk는 Redis와 SSE로만 전달하고 `chat_messages`에는 저장하지 않는다.
- completed/skipped/failed는 DB commit 이후 Redis/SSE로 전달한다.

## 상태 값

| 구분 | 값 |
| --- | --- |
| `toolPlanGroupStatus` | `PLANNING`, `REVIEW`, `PENDING`, `APPROVED`, `BUILDING`, `BUILT`, `REJECTED`, `CANCELLED`, `FAILED` |
| `toolPlanStatus` | `REVIEW`, `PENDING`, `APPROVED`, `REJECTED`, `SUPERSEDED`, `FAILED` |
| `toolPlanRunStatus` | `REQUESTED`, `GENERATING`, `COMPLETED`, `FAILED`, `SKIPPED` |
| `toolPlanRunRequestType` | `GENERATE_PLAN`, `REGENERATE_PLAN`, `BUILD_TOOL` |
| `toolStatus` | `ACTIVE`, `INACTIVE`, `DELETED`, `BUILD_FAILED` |
| `approvalStatus` | `PENDING`, `REJECTED`, `APPROVED` |
| `senderType` | `USER`, `ASSISTANT`, `SYSTEM` |
| `messageType` | `CHAT`, `TOOL_PLAN_REQUEST`, `TOOL_PLAN_RESPONSE`, `TOOL_FEEDBACK`, `TOOL_APPROVAL_REQUEST`, `TOOL_BUILD_NOTICE`, `SYSTEM_NOTICE` |
| `contentType` | `TEXT`, `MARKDOWN`, `JSON` |

## Tool 목록 조회

실제 build가 완료된 Tool만 조회한다.

```http
GET /api/v1/projects/{projectId}/tools?scope=accessible&status=ACTIVE&page=0&size=20
Accept: application/json
Authorization: Bearer {accessToken}
```
### 권한

- 프로젝트 멤버
- `project_members.status = 진행중`
- `project_members.can_use_tool = true`

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
        "sourceToolPlanId": 21,
        "createdByProjectMemberId": 3,
        "createdByUserId": 5,
        "createdByUserName": "홍길동",
        "fileName": "incident-recovery-guide.py",
        "displayName": "장애 복구 가이드",
        "displayDescription": "최근 장애 로그를 분석하고 복구 가이드를 생성합니다.",
        "moduleName": "incident_recovery_guide",
        "artifactPath": "projects/1/incident_recovery_guide.py",
        "status": "ACTIVE",
        "toolGrade": 2,
        "createdAt": "2026-05-08T10:00:00",
        "updatedAt": "2026-05-08T10:10:00"
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
- `tools.status = ACTIVE`
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
    "sourceToolPlanId": 21,
    "fileName": "incident-recovery-guide.py",
    "displayName": "장애 복구 가이드",
    "displayDescription": "최근 장애 로그를 분석하고 복구 가이드를 생성합니다.",
    "moduleName": "incident_recovery_guide",
    "artifactPath": "projects/1/incident_recovery_guide.py",
    "codeSnapshot": "...",
    "metadataJson": "{\"runtime\":\"python\"}",
    "status": "ACTIVE",
    "toolGrade": 2,
    "createdAt": "2026-05-08T10:00:00",
    "updatedAt": "2026-05-08T10:10:00"
  }
}
```

## PLAN 생성 요청

```http
POST /api/v1/projects/{projectId}/sessions/{sessionId}/tool-plans/generate
Accept: application/json
Content-Type: application/json
Authorization: Bearer {accessToken}
```

### 권한

- 프로젝트 멤버
- `project_members.status = 진행중`
- `project_members.can_create_tool = true`
- ChatSession이 해당 프로젝트에 속해야 한다.

### Request Body

```json
{
  "mode": "PLAN",
  "prompt": "장애 로그를 분석하고 자동 복구 가이드를 만드는 Tool 명세를 작성해줘."
}
```

### Response Body

```json
{
  "isSuccess": true,
  "code": "COMMON-202",
  "message": "Tool PLAN 생성을 시작하였습니다.",
  "result": {
    "runId": "3f2a2d5e-0e4a-4a3f-8d0f-9b5a3e2c0d11",
    "projectId": 1,
    "sessionId": 10,
    "status": "GENERATING",
    "sseUrl": "/api/v1/projects/1/sessions/10/tool-plan-runs/3f2a2d5e-0e4a-4a3f-8d0f-9b5a3e2c0d11/events"
  }
}
```

### 동작

- API Server는 ToolPlanRun을 생성한다.
- API Server는 USER `TOOL_PLAN_REQUEST` 메시지를 저장한다.
- API Server는 최근 history snapshot을 구성한다.
- API Server는 `TOOL_PLAN_REQUESTED` Kafka 이벤트를 발행한다.
- 이 시점에는 `tools`와 `tool_plans`를 생성하지 않는다.
- Core Server가 유효한 Tool 명세 요청이라고 판단하면 `TOOL_PLAN_COMPLETED` 이벤트를 발행한다.
- Core Server가 Tool 명세 요청이 아니라고 판단하면 `TOOL_PLAN_SKIPPED` 이벤트를 발행한다.

## PLAN 재생성 요청

```http
PATCH /api/v1/projects/{projectId}/sessions/{sessionId}/tool-plans/{toolPlanId}/regenerate
Accept: application/json
Content-Type: application/json
Authorization: Bearer {accessToken}
```

### 권한

- 프로젝트 멤버
- `project_members.status = 진행중`
- Tool 생성자 또는 `project_members.can_update_tool = true`
- 대상 ToolPlan이 해당 project/session에 속해야 한다.
- 대상 ToolPlan 상태는 `REVIEW` 또는 `REJECTED`여야 한다.

### Request Body

```json
{
  "mode": "PLAN",
  "basePlanVersion": 1,
  "feedbackItems": [
    {
      "blockId": "input-format",
      "comment": "입력 파일 형식 예시를 더 자세히 작성해줘."
    }
  ],
  "instruction": "코멘트가 있는 블록을 중심으로 PLAN 전체를 다시 작성해줘."
}
```

### Response Body

```json
{
  "isSuccess": true,
  "code": "COMMON-202",
  "message": "Tool PLAN 재생성을 시작하였습니다.",
  "result": {
    "runId": "74bd1c34-b9ab-45cc-9c1f-3baf1efef1c7",
    "projectId": 1,
    "sessionId": 10,
    "baseToolPlanId": 21,
    "planGroupId": 5,
    "status": "GENERATING",
    "sseUrl": "/api/v1/projects/1/sessions/10/tool-plan-runs/74bd1c34-b9ab-45cc-9c1f-3baf1efef1c7/events"
  }
}
```

### 동작

- `basePlanVersion`은 사용자가 피드백한 시점의 `tool_plans.plan_version` 값이다.
- 현재 ToolPlan의 `plan_version`과 `basePlanVersion`이 다르면 재생성을 시작하지 않는다.
- 재생성 요청 시점에도 새 ToolPlan은 즉시 생성하지 않는다.
- Core Server가 `TOOL_PLAN_COMPLETED` 이벤트를 발행하면 같은 `planGroupId` 아래 새 ToolPlan 버전을 생성한다.
- Core Server는 수정된 블록만 반환하지 않고 최신 전체 PLAN을 반환한다.

## ToolPlanRun SSE 구독

```http
GET /api/v1/projects/{projectId}/sessions/{sessionId}/tool-plan-runs/{runId}/events
Accept: text/event-stream
Authorization: Bearer {accessToken}
```

### 권한

- 프로젝트 멤버
- `project_members.status = 진행중`
- run이 해당 project/session에 속해야 한다.

### 이벤트 이름

```text
connected
progress
chunk
completed
skipped
failed
```

### completed 예시

```text
event: completed
data: {"eventType":"completed","runId":"3f2a2d5e-0e4a-4a3f-8d0f-9b5a3e2c0d11","projectId":1,"chatSessionId":10,"toolPlanGroupId":5,"toolPlanId":21,"planVersion":1,"status":"REVIEW"}
```

### skipped 예시

```text
event: skipped
data: {"eventType":"skipped","runId":"3f2a2d5e-0e4a-4a3f-8d0f-9b5a3e2c0d11","message":"Tool 명세로 만들 목표, 입력, 출력, 실행 조건을 더 구체적으로 알려주세요."}
```

## ToolPlanRun 상태 조회

```http
GET /api/v1/projects/{projectId}/sessions/{sessionId}/tool-plan-runs/{runId}/state
Accept: application/json
Authorization: Bearer {accessToken}
```

### 동작

- Redis `tool:plan:{runId}:state` 최신 상태가 있으면 Redis 값을 우선 반환한다.
- Redis 상태가 없거나 조회에 실패하면 DB의 `tool_plan_runs`, `tool_plans`, `tool_plan_groups` 기준으로 fallback 응답을 반환한다.
- `FAILED`, `SKIPPED`, `COMPLETED`도 run 기준으로 복구한다.

### Response Body

```json
{
  "isSuccess": true,
  "code": "COMMON-200",
  "message": "성공입니다.",
  "result": {
    "runId": "3f2a2d5e-0e4a-4a3f-8d0f-9b5a3e2c0d11",
    "projectId": 1,
    "chatSessionId": 10,
    "toolPlanGroupId": 5,
    "toolPlanId": 21,
    "planVersion": 1,
    "eventType": "completed",
    "status": "REVIEW",
    "progressRate": 100,
    "message": "Tool PLAN 생성이 완료되었습니다.",
    "updatedAt": "2026-05-08T10:10:00"
  }
}
```

## ToolPlan 승인 요청

```http
POST /api/v1/projects/{projectId}/tool-plans/{toolPlanId}/approval-requests
Accept: application/json
Content-Type: application/json
Authorization: Bearer {accessToken}
```

### 권한

- 프로젝트 멤버
- `project_members.status = 진행중`
- 대상 ToolPlan이 해당 프로젝트에 속해야 한다.
- 대상 ToolPlan 상태는 `REVIEW`여야 한다.

### Request Body

```json
{
  "requestComment": "현재 PLAN으로 Tool 생성을 승인 요청합니다."
}
```

### 동작

- `tool_approvals.tool_plan_id`에 승인 대상 ToolPlan을 저장한다.
- `tool_plans.status = PENDING`으로 변경한다.
- `tool_plan_groups.status = PENDING`으로 변경한다.
- 이 시점에도 `tools` row는 생성하지 않는다.

## ToolPlan 승인

```http
PATCH /api/v1/projects/{projectId}/tool-plan-approvals/{approvalId}/approve
Accept: application/json
Content-Type: application/json
Authorization: Bearer {accessToken}
```

### 권한

- 프로젝트 `ADMIN` 또는 `MANAGER`

### 동작

- `tool_plans.status = APPROVED`로 변경한다.
- `tool_plan_groups.status = APPROVED`로 변경한다.
- API Server가 `TOOL_BUILD_REQUESTED` Kafka 이벤트를 발행한다.
- Core Server가 실제 코드/파일을 생성한다.
- Core Server가 `TOOL_BUILD_COMPLETED` 이벤트를 발행하면 API Server가 `tools` row를 생성한다.

## ToolPlan 반려

```http
PATCH /api/v1/projects/{projectId}/tool-plan-approvals/{approvalId}/reject
Accept: application/json
Content-Type: application/json
Authorization: Bearer {accessToken}
```

### Request Body

```json
{
  "reviewFeedback": "입력과 출력 형식을 더 구체적으로 작성해주세요."
}
```

### 동작

- `tool_plans.status = REJECTED`로 변경한다.
- `tool_plan_groups.status = REJECTED`로 변경한다.
- 사용자는 반려된 ToolPlan을 기준으로 재생성을 요청할 수 있다.

## ToolPlan 상세 조회

```http
GET /api/v1/projects/{projectId}/tool-plans/{toolPlanId}
Accept: application/json
Authorization: Bearer {accessToken}
```

### Response Body

```json
{
  "isSuccess": true,
  "code": "COMMON-200",
  "message": "성공입니다.",
  "result": {
    "toolPlanId": 21,
    "planGroupId": 5,
    "projectId": 1,
    "chatSessionId": 10,
    "planVersion": 1,
    "status": "REVIEW",
    "mode": "PLAN",
    "rawMarkdown": "## Tool Plan...",
    "structuredPlanJson": "{\"version\":1,\"blocks\":[]}",
    "planSnapshot": "{\"schemaVersion\":1,\"blocks\":[]}",
    "createdAt": "2026-05-08T10:00:00",
    "updatedAt": "2026-05-08T10:10:00"
  }
}
```
