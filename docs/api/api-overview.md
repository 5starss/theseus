# API Overview

## 공통 규칙

- 인증이 필요한 API는 `Authorization: Bearer {accessToken}`을 사용한다.
- 로그인 성공 시 Access Token은 응답 본문으로 전달한다.
- Refresh Token은 HttpOnly Cookie로 전달한다.
- 시스템 권한은 `users.system_role`로 판단한다.
- 프로젝트 내부 권한은 `project_members.project_role`과 Tool 권한 필드로 판단한다.
- 프로젝트 대표 담당자(PM)는 `projects.project_admin_user_id`로 판단한다.
- PM은 활성 사용자이며 해당 프로젝트의 `ADMIN`, `진행중` 멤버여야 한다.
- Tool 접근 가능 여부는 `project_members.access_level >= tools.tool_grade`로 판단한다.
- 응답은 프로젝트 공통 응답 포맷을 사용한다.

## 공통 응답

```json
{
  "success": true,
  "code": 200,
  "message": "요청에 성공하였습니다.",
  "result": {}
}
```

```json
{
  "success": false,
  "code": 400,
  "message": "요청에 실패하였습니다.",
  "result": null
}
```

## Endpoint 목록

| 분류 | 기능 | Method | Endpoint |
| --- | --- | --- | --- |
| Auth | 로그인 | `POST` | `/api/v1/auth/login` |
| Auth | Access Token 재발급 | `POST` | `/api/v1/auth/refresh` |
| Auth | 로그아웃 | `POST` | `/api/v1/auth/logout` |
| Account | 내 정보 조회 | `GET` | `/api/v1/users/me` |
| Account | 비밀번호 변경 | `PATCH` | `/api/v1/users/me/password` |
| Admin User | 사용자 목록 조회 | `GET` | `/api/v1/admin/users?status=ACTIVE&page=0&size=20` |
| Admin User | 사용자 상세 조회 | `GET` | `/api/v1/admin/users/{userId}` |
| Admin User | 사용자 등록 | `POST` | `/api/v1/admin/users` |
| Admin User | 사용자 정보 수정 | `PATCH` | `/api/v1/admin/users/{userId}` |
| Admin User | 사용자 상태 변경 | `PATCH` | `/api/v1/admin/users/{userId}/status` |
| Project | 내 프로젝트 목록 조회 | `GET` | `/api/v1/projects` |
| Project | 전체 프로젝트 목록 조회 | `GET` | `/api/v1/admin/projects?status=ACTIVE&page=0&size=20` |
| Project | 프로젝트 생성 | `POST` | `/api/v1/projects` |
| Project | 프로젝트 정보 수정 | `PATCH` | `/api/v1/projects/{projectId}` |
| Project | 프로젝트 내 본인 권한 조회 | `GET` | `/api/v1/projects/{projectId}/me` |
| Project Member | 프로젝트 멤버 목록 조회 | `GET` | `/api/v1/projects/{projectId}/members?status=진행중` |
| Project Member | 프로젝트 멤버 등록 | `POST` | `/api/v1/projects/{projectId}/members` |
| Project Member | 프로젝트 멤버 권한 수정 | `PATCH` | `/api/v1/projects/{projectId}/members/{projectMemberId}` |
| Chat Session | 채팅 세션 생성 | `POST` | `/api/v1/projects/{projectId}/sessions` |
| Chat Session | 채팅 세션 목록 조회 | `GET` | `/api/v1/projects/{projectId}/sessions?page=0&size=20` |
| Chat Session | 채팅 세션 상세 조회 | `GET` | `/api/v1/projects/{projectId}/sessions/{sessionId}` |
| Chat Session | 채팅 세션 제목 수정 | `PATCH` | `/api/v1/projects/{projectId}/sessions/{sessionId}` |
| Chat Session | 채팅 세션 종료 | `PATCH` | `/api/v1/projects/{projectId}/sessions/{sessionId}/close` |
| Chat Message | 채팅 메시지 등록 | `POST` | `/api/v1/projects/{projectId}/sessions/{sessionId}/messages` |
| Chat Message | 채팅 메시지 목록 조회 | `GET` | `/api/v1/projects/{projectId}/sessions/{sessionId}/messages` |
| Tool | Draft Tool 생성 | `POST` | `/api/v1/projects/{projectId}/sessions/{sessionId}/tools/generate` |
| Tool | Draft Tool 재생성 | `PATCH` | `/api/v1/projects/{projectId}/sessions/{sessionId}/tools/{toolId}/regenerate` |
| Tool | Tool 목록 조회 | `GET` | `/api/v1/projects/{projectId}/tools?scope=accessible&status=APPROVED&page=0&size=20` |
| Tool | Tool 상세 조회 | `GET` | `/api/v1/projects/{projectId}/tools/{toolId}` |
| Tool | Tool 실행 | `POST` | `/api/v1/projects/{projectId}/tools/{toolId}/execute` |
| Tool | Tool 정보 수정 | `PATCH` | `/api/v1/projects/{projectId}/tools/{toolId}` |
| Tool | Tool 상태 변경 | `PATCH` | `/api/v1/projects/{projectId}/tools/{toolId}/status` |
| Tool Approval | Tool 승인 요청 | `POST` | `/api/v1/projects/{projectId}/tools/{toolId}/approval-requests` |
| Tool Approval | Tool 승인 이력 조회 | `GET` | `/api/v1/projects/{projectId}/tools/{toolId}/approval-requests` |
| Tool Approval | 승인 요청 목록 조회 | `GET` | `/api/v1/projects/{projectId}/tool-approvals?approvalStatus=PENDING&page=0&size=20` |
| Tool Approval | 승인 요청 상세 조회 | `GET` | `/api/v1/projects/{projectId}/tool-approvals/{toolApprovalId}` |
| Tool Approval | Tool 승인 | `PATCH` | `/api/v1/projects/{projectId}/tool-approvals/{toolApprovalId}/approve` |
| Tool Approval | Tool 반려 | `PATCH` | `/api/v1/projects/{projectId}/tool-approvals/{toolApprovalId}/reject` |
| Tool Run | AI 생성 이벤트 구독 | `GET` | `/api/v1/tool-runs/{runId}/events` |
| Tool Run | AI 생성 run 상태 조회 | `GET` | `/api/v1/tool-runs/{runId}` |

## Auth

| 기능 | 핵심 규칙 |
| --- | --- |
| 로그인 | 사번과 비밀번호를 검증하고 Access Token, Refresh Token을 발급한다. |
| Access Token 재발급 | HttpOnly Cookie의 Refresh Token을 검증하고 새 Access Token을 발급한다. |
| 로그아웃 | 저장소의 Refresh Token을 삭제하고 Refresh Token Cookie를 만료한다. |

## User

| 기능 | 핵심 규칙 |
| --- | --- |
| 사용자 목록 조회 | Super Admin만 조회할 수 있다. |
| 사용자 상세 조회 | Super Admin만 조회할 수 있다. |
| 사용자 등록 | Super Admin이 계정을 발급한다. 일반 회원가입은 제공하지 않는다. |
| 사용자 정보 수정 | 이름, 이메일, 시스템 권한 등 기본 정보를 수정한다. |
| 사용자 상태 변경 | 활성 프로젝트의 PM은 `INACTIVE` 처리할 수 없다. |

## Project

| 기능 | 핵심 규칙 |
| --- | --- |
| 내 프로젝트 목록 조회 | `project_members.status = 진행중`인 프로젝트를 조회한다. |
| 전체 프로젝트 목록 조회 | Super Admin만 전체 프로젝트를 조회한다. |
| 프로젝트 생성 | Super Admin이 생성하며, 사번과 이름으로 PM을 지정한다. |
| 프로젝트 정보 수정 | 기본 정보는 Super Admin 또는 프로젝트 ADMIN이 수정하고, PM 변경은 Super Admin만 수행한다. |
| 프로젝트 내 본인 권한 조회 | 프로젝트 역할, 멤버 상태, Tool 권한, 접근 레벨을 조회한다. |

## Project Member

| 기능 | 핵심 규칙 |
| --- | --- |
| 멤버 목록 조회 | 프로젝트 접근 권한이 있는 사용자가 조회한다. |
| 멤버 등록 | 프로젝트 ADMIN만 등록할 수 있고, 대상 사용자는 활성 상태여야 한다. |
| 멤버 권한 수정 | 프로젝트 ADMIN만 수정할 수 있으며, 현재 PM은 `ADMIN`, `진행중` 상태에서 벗어날 수 없다. |

## Chat Session

- 프로젝트 멤버가 대화 세션을 생성한다.
- 한 세션 안에서 여러 Tool 생성 흐름을 진행할 수 있다.
- 로그인한 프로젝트 멤버는 본인이 생성한 세션 목록을 조회한다.
- 세션 상세 조회는 `chat_messages.message_order ASC` 기준으로 메시지를 반환한다.
- 세션 제목은 `PATCH /api/v1/projects/{projectId}/sessions/{sessionId}`로 수정한다.
- 종료된 세션에는 새 Tool 생성 요청을 제한한다.

## Chat Message

- 외부 메시지 등록 API는 USER 메시지를 저장한다.
- `message_order`는 세션 안의 전체 메시지 순서다.
- `(chat_session_id, message_order)`는 유일하다.
- 일반 대화 메시지는 `tool_id = null`로 저장한다.
- Tool 생성, 계획 제시, 첨삭, 재제시, 승인 요청 메시지는 같은 `tool_id`로 묶는다.
- 진행 중 progress/chunk 이벤트는 `chat_messages`에 저장하지 않는다.
- 최종 USER, ASSISTANT, SYSTEM 메시지만 `chat_messages`에 저장한다.
- ASSISTANT 메시지는 AI 완료 후 Kafka Consumer가 내부 저장 로직으로 저장한다.

## Tool

- Draft Tool 생성과 재생성은 `runId` 기반 비동기 생성 흐름을 사용한다.
- BE는 권한 검증 후 Tool을 `DRAFT / PLAN` 상태로 만들고 AI 생성 run을 시작한다.
- AI progress/chunk는 Redis에 누적하고 SSE로 FE에 전달한다.
- AI 완료 후 Kafka Consumer가 최종 ASSISTANT 메시지 저장, Tool draft 데이터 갱신, `draft_phase = REVIEW` 전환을 처리한다.
- 승인 요청은 `DRAFT / REVIEW` 상태에서만 가능하다.
- 승인되면 `tools.status = APPROVED`, 반려되면 `tools.status = REJECTED`로 변경한다.

## Tool Run

- `runId`는 AI 생성 1회를 식별한다.
- `runId`는 `chatSessionId`가 아니다.
- Redis는 run 상태, 진행 이벤트, 재연결 복구 정보를 TTL 기반으로 저장한다.
- SSE `completed` 이벤트는 DB 저장과 Tool 상태 변경이 끝난 뒤에만 전달한다.
