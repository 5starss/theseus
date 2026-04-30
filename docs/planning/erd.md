# ERD

## Core Tables

| 테이블 | 역할 |
| --- | --- |
| `users` | 사용자 계정, 시스템 권한, 계정 상태를 저장한다. |
| `refresh_tokens` | 사용자별 Refresh Token hash와 만료 시각을 저장한다. |
| `projects` | Tool 생성과 사용이 이루어지는 프로젝트 단위를 저장한다. |
| `project_members` | 프로젝트 내부 역할, 접근 레벨, Tool 작업 권한을 저장한다. |
| `chat_sessions` | 프로젝트 멤버가 진행하는 대화 세션을 저장한다. |
| `tools` | Draft부터 승인, 삭제까지 Tool 본체와 상태를 저장한다. |
| `chat_messages` | 세션 안에서 오간 최종 메시지를 순서대로 저장한다. |
| `tool_approvals` | Tool 승인 요청 이력과 검토 결과를 저장한다. |

## User / Auth

- `users.employee_number`는 로그인 ID로 사용한다.
- `users.password`는 해시된 비밀번호만 저장한다.
- `users.email`은 선택값이지만 값이 있으면 유일해야 한다.
- `refresh_tokens.user_id`는 사용자당 하나의 Refresh Token만 허용한다.
- `refresh_tokens.token_hash`는 Refresh Token 원문이 아니라 SHA-256 hash를 저장한다.
- `refresh_tokens.expires_at`은 Access Token 재발급 가능 여부를 판단한다.

## Project / ProjectMember

프로젝트 생성자와 대표 담당자(PM)는 분리한다.

| 컬럼 | 의미 |
| --- | --- |
| `projects.created_by_user_id` | 프로젝트를 생성한 Super Admin |
| `projects.project_admin_user_id` | 프로젝트 대표 담당자(PM) |
| `project_members.project_role` | 프로젝트 내부 역할과 권한 |

프로젝트 생성 시 Super Admin은 프로젝트명, 설명, 담당자 사번, 담당자 이름을 입력한다. 서버는 담당자 사번과 이름으로 활성 사용자를 조회하고, 조회된 사용자를 `projects.project_admin_user_id`에 저장한다. 같은 사용자는 `project_members`에 `project_role = ADMIN`, `status = 진행중`으로 자동 등록된다.

프로젝트 하나에 `ADMIN` 멤버는 여러 명 존재할 수 있다. 단, Super Admin이 지정하고 수정하는 대표 담당자(PM)는 `projects.project_admin_user_id` 한 명이다. 현재 PM은 활성 사용자이며 해당 프로젝트의 `ADMIN`, `진행중` 멤버여야 한다.

## Chat / Tool Draft

하나의 `chat_sessions` 안에서 여러 Tool을 만들 수 있다. 세션의 전체 대화 순서는 `chat_messages.message_order`로 관리하고, 특정 Tool 생성 또는 수정과 관련된 메시지는 `chat_messages.tool_id`에 해당 Tool을 연결한다.

| 메시지 | 저장 규칙 |
| --- | --- |
| 일반 대화 메시지 | `chat_messages.tool_id = NULL` |
| Tool 생성 요청 | `chat_messages.tool_id = tools.id`, `message_type = TOOL_DRAFT_REQUEST` |
| Tool 계획 또는 명세 제시 | `chat_messages.tool_id = tools.id`, `message_type = TOOL_DRAFT_RESPONSE` |
| Tool 첨삭 요청 | `chat_messages.tool_id = tools.id`, `message_type = TOOL_FEEDBACK` |
| Tool 재제시 | `chat_messages.tool_id = tools.id`, `message_type = TOOL_REGENERATE_RESPONSE` |
| Tool 승인 요청 | `chat_messages.tool_id = tools.id`, `message_type = TOOL_APPROVAL_REQUEST` |

`message_type`은 메시지의 업무 흐름 분류다. `content_type`은 메시지 본문의 렌더링 또는 파싱 형식이다. 숫자, 배열, 객체 같은 구조화된 값은 `content_type = JSON`으로 저장한다.

AI 생성 중 progress/chunk는 `chat_messages`에 저장하지 않는다. Redis에 누적하고 SSE로 전달한다. 최종 USER, ASSISTANT, SYSTEM 메시지만 DB에 저장한다.

## Tool Draft State

```text
DRAFT / PLAN
  -> Assistant가 계획 또는 명세를 작성
DRAFT / REVIEW
  -> 사용자에게 계획 또는 명세를 제시하고 첨삭 또는 승인 대기
DRAFT / PLAN
  -> 사용자가 첨삭하면 다시 계획 수정
DRAFT / REVIEW
  -> 수정된 계획 또는 명세 재제시
PENDING
  -> 사용자가 승인 요청을 제출하면 Tool 승인 대기
APPROVED or REJECTED
  -> 프로젝트 ADMIN 또는 MANAGER가 승인 또는 반려
```

## Async Run

AI 생성 1회는 `runId`로 식별한다. `runId`는 DB 영구 테이블의 기본키가 아니라 Redis에 TTL 기반으로 저장되는 실행 ID다.

| 구성 요소 | 역할 |
| --- | --- |
| Redis | run 상태, progress/chunk 누적, SSE 재연결 복구 |
| Kafka | USER/ASSISTANT 메시지 저장 이벤트, Tool draft 상태 변경 이벤트 |
| SSE | Redis 이벤트를 FE에 실시간 중계 |

`completed` 이벤트는 AI 생성 완료 시점이 아니라 Kafka Consumer가 최종 ASSISTANT 메시지를 저장하고 Tool을 `REVIEW`로 변경한 뒤 발행한다.

## DDL

```sql
CREATE TABLE users (
    id BIGINT NOT NULL AUTO_INCREMENT,
    employee_number VARCHAR(50) NOT NULL,
    name VARCHAR(100) NOT NULL,
    email VARCHAR(100) NULL,
    password VARCHAR(255) NOT NULL,
    system_role VARCHAR(30) NOT NULL DEFAULT 'USER',
    status VARCHAR(30) NOT NULL DEFAULT 'ACTIVE',
    created_at DATETIME NOT NULL,
    updated_at DATETIME NOT NULL,
    CONSTRAINT pk_users PRIMARY KEY (id),
    CONSTRAINT uk_users_employee_number UNIQUE (employee_number),
    CONSTRAINT uk_users_email UNIQUE (email)
);

CREATE TABLE refresh_tokens (
    id BIGINT NOT NULL AUTO_INCREMENT,
    user_id BIGINT NOT NULL,
    token_hash VARCHAR(64) NOT NULL,
    expires_at DATETIME NOT NULL,
    created_at DATETIME NOT NULL,
    updated_at DATETIME NOT NULL,
    CONSTRAINT pk_refresh_tokens PRIMARY KEY (id),
    CONSTRAINT uk_refresh_tokens_user UNIQUE (user_id),
    CONSTRAINT uk_refresh_tokens_token_hash UNIQUE (token_hash),
    CONSTRAINT fk_refresh_tokens_user
        FOREIGN KEY (user_id) REFERENCES users (id)
);

CREATE TABLE projects (
    id BIGINT NOT NULL AUTO_INCREMENT,
    name VARCHAR(100) NOT NULL,
    description TEXT NULL,
    status VARCHAR(30) NOT NULL DEFAULT 'ACTIVE',
    created_by_user_id BIGINT NOT NULL,
    project_admin_user_id BIGINT NOT NULL,
    created_at DATETIME NOT NULL,
    updated_at DATETIME NOT NULL,
    CONSTRAINT pk_projects PRIMARY KEY (id),
    CONSTRAINT fk_projects_created_by_user
        FOREIGN KEY (created_by_user_id) REFERENCES users (id),
    CONSTRAINT fk_projects_project_admin_user
        FOREIGN KEY (project_admin_user_id) REFERENCES users (id)
);

CREATE TABLE project_members (
    id BIGINT NOT NULL AUTO_INCREMENT,
    project_id BIGINT NOT NULL,
    user_id BIGINT NOT NULL,
    project_role VARCHAR(30) NOT NULL DEFAULT 'MEMBER',
    access_level INT UNSIGNED NOT NULL DEFAULT 1,
    can_create_tool BOOLEAN NOT NULL DEFAULT FALSE,
    can_use_tool BOOLEAN NOT NULL DEFAULT TRUE,
    can_update_tool BOOLEAN NOT NULL DEFAULT FALSE,
    can_delete_tool BOOLEAN NOT NULL DEFAULT FALSE,
    status VARCHAR(30) NOT NULL DEFAULT '진행중',
    created_by_user_id BIGINT NULL,
    created_at DATETIME NOT NULL,
    updated_at DATETIME NOT NULL,
    CONSTRAINT pk_project_members PRIMARY KEY (id),
    CONSTRAINT uk_project_members_project_user UNIQUE (project_id, user_id),
    CONSTRAINT fk_project_members_project
        FOREIGN KEY (project_id) REFERENCES projects (id),
    CONSTRAINT fk_project_members_user
        FOREIGN KEY (user_id) REFERENCES users (id),
    CONSTRAINT fk_project_members_created_by_user
        FOREIGN KEY (created_by_user_id) REFERENCES users (id)
);

CREATE TABLE chat_sessions (
    id BIGINT NOT NULL AUTO_INCREMENT,
    project_id BIGINT NOT NULL,
    project_member_id BIGINT NOT NULL,
    title VARCHAR(150) NULL,
    created_at DATETIME NOT NULL,
    updated_at DATETIME NOT NULL,
    closed_at DATETIME NULL,
    CONSTRAINT pk_chat_sessions PRIMARY KEY (id),
    CONSTRAINT fk_chat_sessions_project
        FOREIGN KEY (project_id) REFERENCES projects (id),
    CONSTRAINT fk_chat_sessions_project_member
        FOREIGN KEY (project_member_id) REFERENCES project_members (id)
);

CREATE TABLE tools (
    id BIGINT NOT NULL AUTO_INCREMENT,
    project_id BIGINT NOT NULL,
    chat_session_id BIGINT NOT NULL,
    created_by_project_member_id BIGINT NOT NULL,
    file_name VARCHAR(120) NOT NULL,
    display_name VARCHAR(30) NULL,
    display_description TEXT NULL,
    status VARCHAR(30) NOT NULL DEFAULT 'DRAFT',
    draft_phase VARCHAR(30) NOT NULL DEFAULT 'PLAN',
    tool_grade INT UNSIGNED NULL,
    raw_markdown LONGTEXT NULL,
    structured_plan_json LONGTEXT NULL,
    draft_snapshot LONGTEXT NULL,
    created_at DATETIME NOT NULL,
    updated_at DATETIME NOT NULL,
    CONSTRAINT pk_tools PRIMARY KEY (id),
    CONSTRAINT uk_tools_project_file_name UNIQUE (project_id, file_name),
    CONSTRAINT fk_tools_project
        FOREIGN KEY (project_id) REFERENCES projects (id),
    CONSTRAINT fk_tools_chat_session
        FOREIGN KEY (chat_session_id) REFERENCES chat_sessions (id),
    CONSTRAINT fk_tools_created_by_project_member
        FOREIGN KEY (created_by_project_member_id) REFERENCES project_members (id)
);

CREATE TABLE chat_messages (
    id BIGINT NOT NULL AUTO_INCREMENT,
    chat_session_id BIGINT NOT NULL,
    tool_id BIGINT NULL,
    message_order INT NOT NULL,
    sender_type VARCHAR(30) NOT NULL,
    message_type VARCHAR(50) NOT NULL DEFAULT 'CHAT',
    content_type VARCHAR(30) NOT NULL DEFAULT 'TEXT',
    content MEDIUMTEXT NOT NULL,
    created_at DATETIME NOT NULL,
    CONSTRAINT pk_chat_messages PRIMARY KEY (id),
    CONSTRAINT uk_chat_messages_session_order UNIQUE (chat_session_id, message_order),
    CONSTRAINT fk_chat_messages_chat_session
        FOREIGN KEY (chat_session_id) REFERENCES chat_sessions (id),
    CONSTRAINT fk_chat_messages_tool
        FOREIGN KEY (tool_id) REFERENCES tools (id)
);

CREATE TABLE tool_approvals (
    id BIGINT NOT NULL AUTO_INCREMENT,
    tool_id BIGINT NOT NULL,
    request_number INT NOT NULL,
    requested_by_project_member_id BIGINT NOT NULL,
    reviewed_by_project_member_id BIGINT NULL,
    approval_status VARCHAR(30) NOT NULL DEFAULT 'PENDING',
    review_feedback TEXT NULL,
    requested_at DATETIME NOT NULL,
    reviewed_at DATETIME NULL,
    CONSTRAINT pk_tool_approvals PRIMARY KEY (id),
    CONSTRAINT uk_tool_approvals_tool_request UNIQUE (tool_id, request_number),
    CONSTRAINT fk_tool_approvals_tool
        FOREIGN KEY (tool_id) REFERENCES tools (id),
    CONSTRAINT fk_tool_approvals_requested_by_project_member
        FOREIGN KEY (requested_by_project_member_id) REFERENCES project_members (id),
    CONSTRAINT fk_tool_approvals_reviewed_by_project_member
        FOREIGN KEY (reviewed_by_project_member_id) REFERENCES project_members (id)
);

CREATE INDEX idx_project_members_user_status
    ON project_members (user_id, status);

CREATE INDEX idx_chat_sessions_project_member
    ON chat_sessions (project_member_id);

CREATE INDEX idx_chat_messages_session_order
    ON chat_messages (chat_session_id, message_order);

CREATE INDEX idx_chat_messages_tool_order
    ON chat_messages (tool_id, message_order);

CREATE INDEX idx_tools_chat_session_status
    ON tools (chat_session_id, status);

CREATE INDEX idx_tools_project_status
    ON tools (project_id, status);

CREATE INDEX idx_tool_approvals_tool_status
    ON tool_approvals (tool_id, approval_status);
```

## Relationship Summary

```text
users 1:1 refresh_tokens
users 1:N projects(created_by_user_id)
users 1:N projects(project_admin_user_id)
users 1:N project_members
projects 1:N project_members
projects 1:N chat_sessions
projects 1:N tools
project_members 1:N chat_sessions
project_members 1:N tools(created_by_project_member_id)
chat_sessions 1:N tools
chat_sessions 1:N chat_messages
tools 1:N chat_messages
tools 1:N tool_approvals
```
