# API Overview

## Project

### POST `/projects`

Super Admin이 프로젝트를 생성하고 대표 담당자(PM)를 지정한다. 담당자는 `users`에 이미 존재해야 하며, 사번과 이름이 모두 일치해야 한다.

Request:

```json
{
  "name": "프로젝트명",
  "description": "프로젝트 설명",
  "adminEmployeeNumber": "123123",
  "adminName": "김철수"
}
```

## Chat Session

### POST `/api/v1/projects/{projectId}/sessions`

프로젝트 멤버가 대화 세션을 생성한다. 한 세션 안에서 여러 Tool 생성 흐름을 진행할 수 있다.

Behavior:

- `chat_sessions.project_id`에는 대상 프로젝트를 저장한다.
- `chat_sessions.project_member_id`에는 요청한 사용자의 프로젝트 멤버 ID를 저장한다.
- 세션 접근 권한은 `project_members.status = 진행중`인 멤버를 기준으로 판단한다.

## Chat Message

채팅 메시지는 별도 공개 API보다 ChatSession, Tool 생성, Tool 재생성 흐름에서 함께 저장된다.

Behavior:

- `message_order`는 세션 안의 전체 메시지 순서다.
- `(chat_session_id, message_order)`는 유일하다.
- 일반 대화 메시지는 `tool_id = null`로 저장한다.
- Tool 생성, 계획 제시, 첨삭, 재제시 메시지는 같은 `tool_id`로 묶는다.
- `senderType`은 `USER`, `ASSISTANT`, `SYSTEM`을 사용한다.
- `messageType`은 메시지가 어떤 업무 흐름에 속하는지 나타낸다.
- `contentType`은 메시지 본문을 어떤 형식으로 해석할지 나타낸다.
- 숫자, 배열, 객체 같은 구조화된 값은 `contentType = JSON`으로 저장한다.

## Tool

### POST `/api/v1/projects/{projectId}/sessions/{sessionId}/tools/generate`

프로젝트 멤버가 채팅 세션 안에서 Draft Tool 생성을 시작한다.

Behavior:

- `canCreateTool = true`인 프로젝트 멤버만 호출할 수 있다.
- 요청 메시지는 `chat_messages`에 `senderType = USER`로 저장한다.
- 서버는 `tools.status = DRAFT`, `tools.draftPhase = PLAN` 상태의 Tool을 생성한다.
- Assistant가 계획 또는 명세를 제시하면 `chat_messages`에 `senderType = ASSISTANT`로 저장한다.
- Tool 관련 메시지는 모두 같은 `toolId`를 가진다.
- 계획 또는 명세가 사용자에게 제시되면 `draftPhase = REVIEW`로 변경한다.

### PATCH `/api/v1/projects/{projectId}/sessions/{sessionId}/tools/{toolId}/regenerate`

사용자 첨삭을 반영해 Draft Tool 계획 또는 명세를 다시 생성한다.

Behavior:

- 사용자 첨삭 메시지는 대상 `toolId`와 함께 저장한다.
- 첨삭을 받은 Tool은 `draftPhase = PLAN`으로 변경한다.
- 수정된 계획 또는 명세가 제시되면 `draftPhase = REVIEW`로 변경한다.

### POST `/api/v1/projects/{projectId}/tools/{toolId}/approval-requests`

Draft Tool에 대한 승인 요청을 생성한다.

Behavior:

- Tool 생성자만 승인 요청을 생성할 수 있다.
- 승인 요청 가능 상태는 `status = DRAFT`, `draftPhase = REVIEW`다.
- 승인 요청이 생성되면 `tools.status = PENDING`으로 변경한다.

Behavior:

- `projects.created_by_user_id`에는 요청한 Super Admin을 저장한다.
- `projects.project_admin_user_id`에는 사번과 이름으로 조회한 담당자 사용자를 저장한다.
- 담당자 사용자는 `project_members`에 `project_role = ADMIN`으로 자동 등록된다.

Response:

```json
{
  "id": 1,
  "name": "프로젝트명",
  "description": "프로젝트 설명",
  "status": "ACTIVE",
  "createdByUserId": 1,
  "createdByUserName": "최초 사용자",
  "projectAdminUserId": 3,
  "projectAdminEmployeeNumber": "123123",
  "projectAdminName": "김철수",
  "createdAt": "2026-04-28T16:00:00",
  "updatedAt": "2026-04-28T16:00:00"
}
```
