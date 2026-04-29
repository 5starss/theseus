# Tool API

## Common Rules

- 인증이 필요한 요청은 `Authorization: Bearer {accessToken}`을 사용한다.
- Tool 생성, 사용, 수정, 삭제 권한은 `project_members`의 Boolean 권한으로 판단한다.
- 승인과 반려는 프로젝트 `ADMIN` 또는 `MANAGER`가 수행한다.
- 승인된 Tool 접근 가능 여부는 `project_members.access_level >= tools.tool_grade`로 판단한다.
- 한 채팅 세션에서 여러 Tool을 생성할 수 있다.
- Tool 생성 또는 수정과 관련된 메시지는 `chat_messages.tool_id`로 해당 Tool에 연결한다.

## Status Values

| 구분 | 값 |
| --- | --- |
| `toolStatus` | `DRAFT`, `PENDING`, `REJECTED`, `APPROVED`, `DELETED` |
| `draftPhase` | `PLAN`, `REVIEW` |
| `approvalStatus` | `PENDING`, `REJECTED`, `APPROVED` |
| `senderType` | `USER`, `ASSISTANT`, `SYSTEM` |
| `messageType` | `CHAT`, `TOOL_DRAFT_REQUEST`, `TOOL_DRAFT_RESPONSE`, `TOOL_FEEDBACK`, `TOOL_REGENERATE_RESPONSE`, `TOOL_APPROVAL_REQUEST`, `SYSTEM_NOTICE` |
| `contentType` | `TEXT`, `MARKDOWN`, `JSON` |

`messageType`은 메시지가 어떤 업무 흐름에 속하는지 나타낸다. `contentType`은 메시지 본문을 어떤 형식으로 해석할지 나타낸다. 숫자, 배열, 객체 같은 구조화된 값은 `contentType = JSON`으로 저장한다.

## Draft Tool 생성

```http
POST /api/v1/projects/{projectId}/sessions/{sessionId}/tools/generate
Accept: application/json
Content-Type: application/json
Authorization: Bearer {accessToken}
```

권한:

- 프로젝트 멤버
- `project_members.status = 진행중`
- `project_members.can_create_tool = true`

요청:

```json
{
  "message": "CSV 파일을 업로드하면 매출 합계를 계산하는 Tool을 만들어줘.",
  "fileName": "sales-summary-tool"
}
```

동작:

- `tools`에 `status = DRAFT`, `draft_phase = PLAN`인 Tool을 생성한다.
- 사용자 요청 메시지를 `chat_messages`에 `message_type = TOOL_DRAFT_REQUEST`, `content_type = TEXT`로 저장하고 `tool_id`를 연결한다.
- Assistant가 계획 또는 명세를 작성한 뒤 `chat_messages`에 `message_type = TOOL_DRAFT_RESPONSE`, `content_type = MARKDOWN` 또는 `JSON`으로 저장하고 같은 `tool_id`를 연결한다.
- Assistant 계획 또는 명세가 사용자에게 제시되면 `tools.draft_phase = REVIEW`로 변경한다.
- 세션 전체 메시지 순서는 `message_order`로 증가한다.
- `file_name`은 같은 프로젝트 안에서 유일해야 한다.

응답:

```json
{
  "success": true,
  "code": 201,
  "message": "Draft Tool이 생성되었습니다.",
  "result": {
    "toolId": 1,
    "projectId": 1,
    "sessionId": 1,
    "fileName": "sales-summary-tool",
    "status": "DRAFT",
    "draftPhase": "REVIEW",
    "rawMarkdown": "### Tool 생성 계획...",
    "structuredPlanJson": "{...}",
    "draftSnapshot": "{...}"
  }
}
```

## Draft Tool 재생성

```http
PATCH /api/v1/projects/{projectId}/sessions/{sessionId}/tools/{toolId}/regenerate
Accept: application/json
Content-Type: application/json
Authorization: Bearer {accessToken}
```

권한:

- Tool 생성자 또는 `can_update_tool = true`인 프로젝트 멤버
- `tools.status = DRAFT` 또는 `REJECTED`

요청:

```json
{
  "message": "2번 블록에서 입력 파일 형식을 xlsx도 허용하도록 수정해줘."
}
```

동작:

- 사용자 첨삭 메시지를 `chat_messages`에 `message_type = TOOL_FEEDBACK`, `content_type = TEXT`로 저장하고 `tool_id`를 연결한다.
- 첨삭을 받은 시점에 `tools.draft_phase = PLAN`으로 변경한다.
- Assistant가 수정된 계획 또는 명세를 다시 작성해 `chat_messages`에 `message_type = TOOL_REGENERATE_RESPONSE`, `content_type = MARKDOWN` 또는 `JSON`으로 저장하고 같은 `tool_id`를 연결한다.
- 수정된 계획 또는 명세가 사용자에게 제시되면 `tools.draft_phase = REVIEW`로 변경한다.
- 같은 세션 안의 다른 Tool 관련 메시지와 섞이지 않도록 `tool_id` 기준으로 Draft 대화 이력을 조회한다.

응답:

```json
{
  "success": true,
  "code": 200,
  "message": "Draft Tool이 재생성되었습니다.",
  "result": {
    "toolId": 1,
    "status": "DRAFT",
    "draftPhase": "REVIEW",
    "rawMarkdown": "### 수정된 Tool 생성 계획...",
    "structuredPlanJson": "{...}",
    "draftSnapshot": "{...}"
  }
}
```

## Tool 승인 요청

```http
POST /api/v1/projects/{projectId}/tools/{toolId}/approval-requests
Accept: application/json
Content-Type: application/json
Authorization: Bearer {accessToken}
```

권한:

- Tool 생성자
- `tools.status = DRAFT`
- `tools.draft_phase = REVIEW`

동작:

- `tool_approvals`에 `approval_status = PENDING`인 승인 요청을 생성한다.
- `request_number`는 같은 Tool 안에서 1부터 증가한다.
- `tools.status = PENDING`으로 변경한다.
- 승인 요청 메시지를 대화 이력에 남길 경우 `message_type = TOOL_APPROVAL_REQUEST`로 저장한다.

## 승인 이력 조회

```http
GET /api/v1/projects/{projectId}/tools/{toolId}/approval-requests
Accept: application/json
Authorization: Bearer {accessToken}
```

권한:

- 프로젝트 멤버

## 승인 요청 목록 조회

```http
GET /api/v1/projects/{projectId}/tool-approvals?approvalStatus=PENDING&page=0&size=20
Accept: application/json
Authorization: Bearer {accessToken}
```

권한:

- 프로젝트 `ADMIN`
- 프로젝트 `MANAGER`

## Tool 승인

```http
PATCH /api/v1/projects/{projectId}/tool-approvals/{toolApprovalId}/approve
Accept: application/json
Content-Type: application/json
Authorization: Bearer {accessToken}
```

권한:

- 프로젝트 `ADMIN`
- 프로젝트 `MANAGER`

요청:

```json
{
  "toolGrade": 3,
  "reviewFeedback": "승인합니다."
}
```

동작:

- `tool_approvals.approval_status = APPROVED`로 변경한다.
- `tools.status = APPROVED`로 변경한다.
- `tools.tool_grade`를 저장한다.

## Tool 반려

```http
PATCH /api/v1/projects/{projectId}/tool-approvals/{toolApprovalId}/reject
Accept: application/json
Content-Type: application/json
Authorization: Bearer {accessToken}
```

권한:

- 프로젝트 `ADMIN`
- 프로젝트 `MANAGER`

요청:

```json
{
  "reviewFeedback": "보안 검증 단계가 더 필요합니다."
}
```

동작:

- `tool_approvals.approval_status = REJECTED`로 변경한다.
- `tools.status = REJECTED`로 변경한다.
- 반려 이후 생성자는 Draft Tool 재생성 API로 계획을 수정할 수 있다.
