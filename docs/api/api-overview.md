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
- 프로젝트 `ADMIN`은 `access_level = 100`으로 고정한다.
- 일반 `MEMBER` / `MANAGER`에게 부여 가능한 `access_level` 범위는 `1~99`다.
- 신규 build 완료 Tool은 기본 `tool_grade = 100`으로 생성되어 프로젝트 `ADMIN`만 먼저 검토할 수 있다.
- 응답은 프로젝트 공통 응답 포맷을 사용한다.

## ToolPlan 기준

- PLAN 모드 요청은 Tool 생성 요청이 아니라 Tool PLAN 후보 생성 요청이다.
- 승인 전에는 `tools` row를 생성하지 않는다.
- PLAN 생성/재생성 진행 상태는 `tool_plan_runs.run_id` 기준으로 추적한다.
- Core Server가 유효한 Tool 명세 요청이라고 판단하면 `tool_plans`가 생성된다.
- Core Server가 Tool 명세 대상이 아니라고 판단하면 `SKIPPED`로 종료되고 `tool_plans`, `tools`는 생성되지 않는다.
- 승인 요청 대상은 `toolPlanId`다.
- 실제 Tool은 승인된 ToolPlan을 기반으로 Core Server가 build를 완료한 뒤 생성된다.

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
| Remote Workspace | Remote Workspace 등록 | `POST` | `/api/v1/projects/{projectId}/remote-workspaces` |
| Remote Workspace | Remote Workspace 목록 조회 | `GET` | `/api/v1/projects/{projectId}/remote-workspaces` |
| Remote Workspace | Remote Workspace 상세 조회 | `GET` | `/api/v1/projects/{projectId}/remote-workspaces/{remoteWorkspaceId}` |
| Remote Workspace | Remote Workspace 수정 | `PATCH` | `/api/v1/projects/{projectId}/remote-workspaces/{remoteWorkspaceId}` |
| Remote Workspace | Remote Workspace 삭제 | `PATCH` | `/api/v1/projects/{projectId}/remote-workspaces/{remoteWorkspaceId}/delete` |
| Remote Workspace | Remote Workspace 연결 테스트 | `POST` | `/api/v1/projects/{projectId}/remote-workspaces/{remoteWorkspaceId}/test-connection` |
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
| ToolPlan | PLAN 생성 요청 | `POST` | `/api/v1/projects/{projectId}/sessions/{sessionId}/tool-plans/generate` |
| ToolPlan | PLAN 재생성 요청 | `PATCH` | `/api/v1/projects/{projectId}/sessions/{sessionId}/tool-plans/{toolPlanId}/regenerate` |
| ToolPlan | PLAN 상세 조회 | `GET` | `/api/v1/projects/{projectId}/sessions/{sessionId}/tool-plans/{toolPlanId}` |
| ToolPlanRun | PLAN 진행 SSE 구독 | `GET` | `/api/v1/projects/{projectId}/sessions/{sessionId}/tool-plan-runs/{runId}/events` |
| ToolPlanRun | PLAN 진행 상태 조회 | `GET` | `/api/v1/projects/{projectId}/sessions/{sessionId}/tool-plan-runs/{runId}/state` |
| ToolApproval | ToolPlan 승인 요청 | `POST` | `/api/v1/projects/{projectId}/tool-plans/{toolPlanId}/approval-requests` |
| ToolApproval | 승인 요청 목록 조회 | `GET` | `/api/v1/projects/{projectId}/tool-approvals?approvalStatus=PENDING&page=0&size=20` |
| ToolApproval | 승인 요청 상세 조회 | `GET` | `/api/v1/projects/{projectId}/tool-approvals/{approvalId}` |
| ToolApproval | ToolPlan 승인 | `PATCH` | `/api/v1/projects/{projectId}/tool-approvals/{approvalId}/approve` |
| ToolApproval | ToolPlan 반려 | `PATCH` | `/api/v1/projects/{projectId}/tool-approvals/{approvalId}/reject` |
| Tool | Tool 목록 조회 | `GET` | `/api/v1/projects/{projectId}/tools?scope=accessible&status=ACTIVE&page=0&size=20` |
| Tool | Tool 상세 조회 | `GET` | `/api/v1/projects/{projectId}/tools/{toolId}` |
| Tool | Tool 실행 | `POST` | `/api/v1/projects/{projectId}/tools/{toolId}/execute` |
| Tool | Tool 정보 수정 | `PATCH` | `/api/v1/projects/{projectId}/tools/{toolId}` |
| Tool | Tool 상태 변경 | `PATCH` | `/api/v1/projects/{projectId}/tools/{toolId}/status` |

## Chat Session

- 프로젝트 멤버가 대화 세션을 생성한다.
- 한 세션 안에서 여러 ToolPlanGroup이 진행될 수 있다.
- 세션 상세 조회는 `chat_messages.message_order ASC` 기준으로 메시지를 반환한다.
- 종료된 세션에는 새 메시지와 새 PLAN 요청을 제한한다.

## Chat Message

- `message_order`는 세션 안의 전체 메시지 순서다.
- `(chat_session_id, message_order)`는 유일하다.
- 일반 대화 메시지는 `tool_plan_id = null`, `tool_id = null`로 저장한다.
- PLAN 요청/응답/피드백/승인 요청은 `tool_plan_id` 또는 `tool_plan_run_id`로 연결한다.
- progress/chunk 이벤트는 `chat_messages`에 저장하지 않는다.
- 최종 USER, ASSISTANT, SYSTEM 메시지만 `chat_messages`에 저장한다.

## ToolPlan

- PLAN 생성 요청은 `ToolPlanRun`만 생성하고 `ToolPlan`, `Tool`은 즉시 생성하지 않는다.
- `TOOL_PLAN_COMPLETED` 이벤트를 수신하면 `ToolPlanGroup`과 `ToolPlan`을 생성한다.
- `TOOL_PLAN_SKIPPED` 이벤트를 수신하면 안내 메시지만 저장하고 `ToolPlan`, `Tool`은 생성하지 않는다.
- PLAN 재생성은 기존 `ToolPlan`을 기준으로 새 run을 만들고, completed 이후 같은 group 아래 새 `ToolPlan`을 생성한다.
- `basePlanVersion`과 DB의 `tool_plans.plan_version`이 다르면 재생성을 거부한다.

## ToolApproval

- 승인 요청 대상은 `toolPlanId`다.
- 승인 요청은 `tool_plans.status = REVIEW`인 경우에만 가능하다.
- 승인 완료 시 `ToolPlan`은 `APPROVED`가 되지만 `Tool`은 아직 생성되지 않는다.
- 승인 후 API Server가 `TOOL_BUILD_REQUESTED` Kafka 이벤트를 발행한다.
- `TOOL_BUILD_COMPLETED` 이벤트를 수신하면 `tools` row를 생성한다.

## Tool

- Tool 목록에는 실제 build가 완료된 `tools`만 표시한다.
- 승인 전 PLAN 후보, 승인 대기 PLAN, build 중 PLAN은 Tool 목록에 표시하지 않는다.
- Tool 접근 가능 여부는 `project_members.access_level >= tools.tool_grade`로 판단한다.
- `tool_grade = 100`은 프로젝트 `ADMIN` 전용 Tool이며, `1~99`는 일반 멤버 공개 범위다.

## ToolPlanRun / SSE

- `runId`는 AI/Core 실행 1회를 식별하는 추적 ID다.
- FE SSE 구독과 새로고침 복구 기준은 `projectId/sessionId/runId`다.
- Redis는 `tool:plan:{runId}:state`에 최신 진행 상태를 TTL 기반으로 저장한다.
- SSE 연결 직후 Redis 최신 상태가 있으면 최초 상태 이벤트를 전송한다.
- SSE `completed`, `skipped`, `failed` 이벤트는 DB commit 이후에만 전달한다.
