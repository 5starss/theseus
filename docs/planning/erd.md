# ERD

## Core Tables

| 테이블 | 역할 |
| --- | --- |
| `users` | 사용자 계정, 시스템 권한, 계정 상태를 저장한다. |
| `projects` | ToolPlan과 Tool 사용이 이루어지는 프로젝트 단위를 저장한다. |
| `project_members` | 프로젝트 내부 역할, 접근 레벨, Tool 작업 권한을 저장한다. |
| `chat_sessions` | 프로젝트 멤버가 진행하는 대화 세션을 저장한다. |
| `chat_messages` | 세션 안에서 오간 최종 메시지를 순서대로 저장한다. |
| `tool_plan_groups` | 하나의 Tool 후보 흐름과 PLAN 버전 묶음을 저장한다. |
| `tool_plans` | 승인 전 Tool 명세 버전을 저장한다. |
| `tool_plan_runs` | Core Server의 PLAN 생성/재생성/build 실행 1회를 추적한다. |
| `tool_approvals` | ToolPlan 승인 요청 이력과 검토 결과를 저장한다. |
| `tools` | 실제 build가 완료되어 사용 가능한 Tool 산출물을 저장한다. |
| `billing_usages` | Core Server가 보고한 토큰 사용량과 원본 usage payload를 저장한다. |

## User / Auth

- `users.employee_number`는 로그인 ID로 사용한다.
- `users.password`는 해시된 비밀번호만 저장한다.
- `users.email`은 선택값이지만 값이 있으면 유일해야 한다.
- Access Token은 응답 body로 전달하고, Refresh Token은 HttpOnly Cookie로 전달한다.

## Project / ProjectMember

프로젝트 생성자와 대표 담당자(PM)는 분리한다.

| 컬럼 | 의미 |
| --- | --- |
| `projects.created_by_user_id` | 프로젝트를 생성한 Super Admin |
| `projects.project_admin_user_id` | 프로젝트 대표 담당자(PM) |
| `project_members.project_role` | 프로젝트 내부 역할과 권한 |

프로젝트 생성 시 Super Admin은 프로젝트명, 설명, 담당자 사번, 담당자 이름을 입력한다. 서버는 담당자 사번과 이름으로 활성 사용자를 조회하고, 조회된 사용자를 `projects.project_admin_user_id`에 저장한다. 같은 사용자는 `project_members`에 `project_role = ADMIN`, `status = 진행중`으로 자동 등록된다.

프로젝트 하나에 `ADMIN` 멤버는 여러 명 존재할 수 있다. 단, Super Admin이 지정하고 수정하는 대표 담당자(PM)는 `projects.project_admin_user_id` 한 명이다.

## ToolPlan / Tool

PLAN 모드 요청은 Tool 생성 요청이 아니라 Tool PLAN 후보 생성 요청이다.

```text
PLAN 요청
-> tool_plan_runs 생성
-> Core Server 판단
-> 유효한 PLAN이면 tool_plan_groups/tool_plans 생성
-> 승인 요청 대상은 tool_plans.id
-> 승인 후 Core build 완료
-> tools row 생성
```

`tools`는 실제 코드, 파일, 모듈, 실행 메타데이터가 준비된 산출물만 저장한다. 승인 전 PLAN 후보와 진행 중 상태는 `tools`에 저장하지 않는다.

### 전환 단계 기준

`S14P31A308-237` 단계에서는 신규 ToolPlan 구조를 추가하되 기존 Tool 생성/승인 API 호환을 유지한다.

```text
tools.source_tool_plan_id nullable
tool_approvals.tool_plan_id nullable
기존 tools draft 컬럼 유지
기존 tools.status enum 유지
```

최종 ToolPlan 전환이 끝난 뒤 별도 이슈에서 legacy Tool draft 컬럼을 제거하고, Tool 상태를 build 산출물 기준 상태로 정리한다.

## ChatMessage 연결

| 메시지 | 저장 규칙 |
| --- | --- |
| 일반 대화 메시지 | `chat_messages.tool_plan_id = NULL`, `chat_messages.tool_id = NULL` |
| PLAN 생성 요청 | `chat_messages.tool_plan_run_id = tool_plan_runs.id`, `message_type = TOOL_PLAN_REQUEST` |
| PLAN 응답 | `chat_messages.tool_plan_id = tool_plans.id`, `message_type = TOOL_PLAN_RESPONSE` |
| PLAN 피드백 | `chat_messages.tool_plan_id = base tool_plans.id`, `message_type = TOOL_FEEDBACK` |
| PLAN 승인 요청 | `chat_messages.tool_plan_id = tool_plans.id`, `message_type = TOOL_APPROVAL_REQUEST` |
| Tool build 완료 안내 | `chat_messages.tool_plan_id = source tool_plans.id`, `chat_messages.tool_id = tools.id` |

AI 생성 중 progress/chunk는 `chat_messages`에 저장하지 않는다. Redis/SSE 상태로만 전달한다.

`tool_plans.plan_snapshot`은 FE 렌더링, 새로고침 복구, 승인 감사에 사용하는 API-facing PLAN 고정본이다. Core Server의 `TheseusStateMachine` checkpoint와 tool-use trace는 API MySQL이 아니라 Core PostgreSQL에 저장한다.

## State

### ToolPlanGroupStatus

```text
PLANNING
REVIEW
PENDING
APPROVED
BUILDING
BUILT
REJECTED
CANCELLED
FAILED
```

### ToolPlanStatus

```text
REVIEW
PENDING
APPROVED
REJECTED
SUPERSEDED
FAILED
```

`tool_plans`에는 `GENERATING` 상태를 두지 않는다. 생성 중 상태는 `tool_plan_runs`가 담당한다.

### ToolPlanRunRequestType

```text
GENERATE_PLAN
REGENERATE_PLAN
BUILD_TOOL
```

### ToolPlanRunStatus

```text
REQUESTED
GENERATING
COMPLETED
FAILED
SKIPPED
```

`SKIPPED`는 PLAN 모드 입력이 Tool 명세 생성 대상이 아니라고 Core Server가 판단한 경우다.

### ToolStatus

전환 단계에서는 기존 API 호환을 위해 `DRAFT`, `PENDING`, `REJECTED`, `APPROVED`, `DELETED`를 유지한다.

최종 build 산출물 중심 전환 후 상태:

```text
ACTIVE
INACTIVE
DELETED
BUILD_FAILED
```

## Async Run

AI/Core 실행 1회는 `runId`로 식별한다. `runId`는 Kafka/Core 이벤트, Redis/SSE, `tool_plan_runs`를 연결하는 실행 ID다.

| 구성 요소 | 역할 |
| --- | --- |
| `tool_plan_runs` | 요청/완료/실패/skipped 상태의 DB 기준 |
| Redis | `tool:plan:{runId}:state` 최신 상태, progress/chunk 최신값, SSE 재연결 복구 |
| Kafka | PLAN 생성/재생성/build 요청과 Core Server 결과 이벤트 전달 |
| SSE | Redis 최신 상태와 Kafka Consumer 수신 이벤트를 FE에 실시간 중계 |

Kafka request 1개는 LLM 호출 1회가 아니라 Core Server의 장기 실행 run 하나를 시작하는 명령이다. Core 내부 `TheseusStateMachine` checkpoint는 Core Server PostgreSQL에 저장한다.

`tool_plan_runs.history_snapshot_json`은 Kafka 요청 시점의 Core 입력용 대화 snapshot이다. Core Server는 API Server 내부 HTTP로 history를 다시 조회하지 않는다.

## Relationship

```text
projects 1 - N chat_sessions
projects 1 - N tool_plan_groups
tool_plan_groups 1 - N tool_plans
tool_plan_groups 0..1 - 1 tools
tool_plan_runs N - 0..1 tool_plan_groups
tool_plan_runs N - 0..1 tool_plans
tool_plans 1 - N tool_approvals
chat_messages N - 0..1 tool_plans
chat_messages N - 0..1 tool_plan_runs
tools N - 1 source tool_plans
```

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
    access_level INT NOT NULL DEFAULT 1,
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

CREATE TABLE tool_plan_groups (
    id BIGINT NOT NULL AUTO_INCREMENT,
    project_id BIGINT NOT NULL,
    chat_session_id BIGINT NOT NULL,
    created_by_project_member_id BIGINT NOT NULL,
    status VARCHAR(30) NOT NULL DEFAULT 'PLANNING',
    latest_tool_plan_id BIGINT NULL,
    approved_tool_plan_id BIGINT NULL,
    created_tool_id BIGINT NULL,
    created_at DATETIME NOT NULL,
    updated_at DATETIME NOT NULL,
    CONSTRAINT pk_tool_plan_groups PRIMARY KEY (id),
    CONSTRAINT fk_tool_plan_groups_project
        FOREIGN KEY (project_id) REFERENCES projects (id),
    CONSTRAINT fk_tool_plan_groups_chat_session
        FOREIGN KEY (chat_session_id) REFERENCES chat_sessions (id),
    CONSTRAINT fk_tool_plan_groups_created_by_project_member
        FOREIGN KEY (created_by_project_member_id) REFERENCES project_members (id)
);

CREATE TABLE tool_plans (
    id BIGINT NOT NULL AUTO_INCREMENT,
    plan_group_id BIGINT NOT NULL,
    project_id BIGINT NOT NULL,
    chat_session_id BIGINT NOT NULL,
    created_by_project_member_id BIGINT NOT NULL,
    base_tool_plan_id BIGINT NULL,
    plan_version BIGINT NOT NULL,
    status VARCHAR(30) NOT NULL DEFAULT 'REVIEW',
    mode VARCHAR(30) NOT NULL DEFAULT 'PLAN',
    requested_prompt LONGTEXT NULL,
    raw_markdown LONGTEXT NOT NULL,
    structured_plan_json LONGTEXT NOT NULL,
    plan_snapshot LONGTEXT NOT NULL,
    created_at DATETIME NOT NULL,
    updated_at DATETIME NOT NULL,
    CONSTRAINT pk_tool_plans PRIMARY KEY (id),
    CONSTRAINT uk_tool_plans_group_version UNIQUE (plan_group_id, plan_version),
    CONSTRAINT fk_tool_plans_group
        FOREIGN KEY (plan_group_id) REFERENCES tool_plan_groups (id),
    CONSTRAINT fk_tool_plans_project
        FOREIGN KEY (project_id) REFERENCES projects (id),
    CONSTRAINT fk_tool_plans_chat_session
        FOREIGN KEY (chat_session_id) REFERENCES chat_sessions (id),
    CONSTRAINT fk_tool_plans_created_by_project_member
        FOREIGN KEY (created_by_project_member_id) REFERENCES project_members (id),
    CONSTRAINT fk_tool_plans_base_tool_plan
        FOREIGN KEY (base_tool_plan_id) REFERENCES tool_plans (id)
);

ALTER TABLE tool_plan_groups
    ADD CONSTRAINT fk_tool_plan_groups_latest_tool_plan
        FOREIGN KEY (latest_tool_plan_id) REFERENCES tool_plans (id),
    ADD CONSTRAINT fk_tool_plan_groups_approved_tool_plan
        FOREIGN KEY (approved_tool_plan_id) REFERENCES tool_plans (id);

CREATE TABLE tool_plan_runs (
    id BIGINT NOT NULL AUTO_INCREMENT,
    run_id VARCHAR(64) NOT NULL,
    project_id BIGINT NOT NULL,
    chat_session_id BIGINT NOT NULL,
    request_type VARCHAR(30) NOT NULL,
    mode VARCHAR(30) NOT NULL DEFAULT 'PLAN',
    status VARCHAR(30) NOT NULL DEFAULT 'REQUESTED',
    requested_by_project_member_id BIGINT NOT NULL,
    base_tool_plan_id BIGINT NULL,
    result_tool_plan_id BIGINT NULL,
    plan_group_id BIGINT NULL,
    user_message_id BIGINT NULL,
    request_payload_json LONGTEXT NULL,
    history_snapshot_json LONGTEXT NULL,
    last_event_type VARCHAR(80) NULL,
    last_event_sequence BIGINT NULL,
    error_code VARCHAR(120) NULL,
    error_message TEXT NULL,
    requested_at DATETIME NOT NULL,
    completed_at DATETIME NULL,
    created_at DATETIME NOT NULL,
    updated_at DATETIME NOT NULL,
    CONSTRAINT pk_tool_plan_runs PRIMARY KEY (id),
    CONSTRAINT uk_tool_plan_runs_run_id UNIQUE (run_id),
    CONSTRAINT fk_tool_plan_runs_project
        FOREIGN KEY (project_id) REFERENCES projects (id),
    CONSTRAINT fk_tool_plan_runs_chat_session
        FOREIGN KEY (chat_session_id) REFERENCES chat_sessions (id),
    CONSTRAINT fk_tool_plan_runs_requested_by_project_member
        FOREIGN KEY (requested_by_project_member_id) REFERENCES project_members (id),
    CONSTRAINT fk_tool_plan_runs_base_tool_plan
        FOREIGN KEY (base_tool_plan_id) REFERENCES tool_plans (id),
    CONSTRAINT fk_tool_plan_runs_result_tool_plan
        FOREIGN KEY (result_tool_plan_id) REFERENCES tool_plans (id),
    CONSTRAINT fk_tool_plan_runs_group
        FOREIGN KEY (plan_group_id) REFERENCES tool_plan_groups (id)
);

CREATE TABLE tools (
    id BIGINT NOT NULL AUTO_INCREMENT,
    project_id BIGINT NOT NULL,
    chat_session_id BIGINT NOT NULL,
    created_by_project_member_id BIGINT NOT NULL,
    source_tool_plan_id BIGINT NULL,
    file_name VARCHAR(120) NOT NULL,
    display_name VARCHAR(30) NULL,
    display_description TEXT NULL,
    module_name VARCHAR(160) NULL,
    artifact_path VARCHAR(500) NULL,
    code_snapshot LONGTEXT NULL,
    metadata_json LONGTEXT NULL,
    status VARCHAR(30) NOT NULL DEFAULT 'DRAFT',
    draft_phase VARCHAR(30) NOT NULL DEFAULT 'PLAN',
    draft_version BIGINT NOT NULL DEFAULT 0,
    raw_markdown LONGTEXT NULL,
    structured_plan_json LONGTEXT NULL,
    draft_snapshot LONGTEXT NULL,
    tool_grade INT UNSIGNED NULL,
    created_at DATETIME NOT NULL,
    updated_at DATETIME NOT NULL,
    CONSTRAINT pk_tools PRIMARY KEY (id),
    CONSTRAINT uk_tools_source_tool_plan UNIQUE (source_tool_plan_id),
    CONSTRAINT uk_tools_project_file_name UNIQUE (project_id, file_name),
    CONSTRAINT fk_tools_project
        FOREIGN KEY (project_id) REFERENCES projects (id),
    CONSTRAINT fk_tools_chat_session
        FOREIGN KEY (chat_session_id) REFERENCES chat_sessions (id),
    CONSTRAINT fk_tools_created_by_project_member
        FOREIGN KEY (created_by_project_member_id) REFERENCES project_members (id),
    CONSTRAINT fk_tools_source_tool_plan
        FOREIGN KEY (source_tool_plan_id) REFERENCES tool_plans (id)
);

ALTER TABLE tool_plan_groups
    ADD CONSTRAINT fk_tool_plan_groups_created_tool
        FOREIGN KEY (created_tool_id) REFERENCES tools (id);

CREATE TABLE chat_messages (
    id BIGINT NOT NULL AUTO_INCREMENT,
    chat_session_id BIGINT NOT NULL,
    project_id BIGINT NOT NULL,
    project_member_id BIGINT NULL,
    tool_plan_id BIGINT NULL,
    tool_plan_run_id BIGINT NULL,
    tool_id BIGINT NULL,
    sender_type VARCHAR(30) NOT NULL,
    message_type VARCHAR(50) NOT NULL,
    content_type VARCHAR(30) NOT NULL,
    content MEDIUMTEXT NOT NULL,
    message_order BIGINT NOT NULL,
    idempotency_key VARCHAR(255) NULL,
    created_at DATETIME NOT NULL,
    CONSTRAINT pk_chat_messages PRIMARY KEY (id),
    CONSTRAINT uk_chat_messages_session_order UNIQUE (chat_session_id, message_order),
    CONSTRAINT uk_chat_messages_idempotency_key UNIQUE (idempotency_key),
    CONSTRAINT fk_chat_messages_chat_session
        FOREIGN KEY (chat_session_id) REFERENCES chat_sessions (id),
    CONSTRAINT fk_chat_messages_project
        FOREIGN KEY (project_id) REFERENCES projects (id),
    CONSTRAINT fk_chat_messages_project_member
        FOREIGN KEY (project_member_id) REFERENCES project_members (id),
    CONSTRAINT fk_chat_messages_tool_plan
        FOREIGN KEY (tool_plan_id) REFERENCES tool_plans (id),
    CONSTRAINT fk_chat_messages_tool_plan_run
        FOREIGN KEY (tool_plan_run_id) REFERENCES tool_plan_runs (id),
    CONSTRAINT fk_chat_messages_tool
        FOREIGN KEY (tool_id) REFERENCES tools (id)
);

CREATE TABLE tool_approvals (
    id BIGINT NOT NULL AUTO_INCREMENT,
    tool_plan_id BIGINT NULL,
    tool_id BIGINT NOT NULL,
    request_number BIGINT NOT NULL,
    approval_status VARCHAR(30) NOT NULL DEFAULT 'PENDING',
    requested_by_project_member_id BIGINT NOT NULL,
    reviewed_by_project_member_id BIGINT NULL,
    review_feedback TEXT NULL,
    requested_at DATETIME NOT NULL,
    reviewed_at DATETIME NULL,
    CONSTRAINT pk_tool_approvals PRIMARY KEY (id),
    CONSTRAINT uk_tool_approvals_tool_request UNIQUE (tool_id, request_number),
    CONSTRAINT uk_tool_approvals_plan_request UNIQUE (tool_plan_id, request_number),
    CONSTRAINT fk_tool_approvals_tool_plan
        FOREIGN KEY (tool_plan_id) REFERENCES tool_plans (id),
    CONSTRAINT fk_tool_approvals_tool
        FOREIGN KEY (tool_id) REFERENCES tools (id),
    CONSTRAINT fk_tool_approvals_requested_by_project_member
        FOREIGN KEY (requested_by_project_member_id) REFERENCES project_members (id),
    CONSTRAINT fk_tool_approvals_reviewed_by_project_member
        FOREIGN KEY (reviewed_by_project_member_id) REFERENCES project_members (id)
);

CREATE TABLE billing_usages (
    id BIGINT NOT NULL AUTO_INCREMENT,
    user_id BIGINT NOT NULL,
    project_id BIGINT NOT NULL,
    prompt_tokens BIGINT NOT NULL,
    completion_tokens BIGINT NOT NULL,
    total_tokens BIGINT NOT NULL,
    model_name VARCHAR(120) NOT NULL,
    reported_at DATETIME NOT NULL,
    idempotency_key VARCHAR(255) NULL,
    usage_payload_json LONGTEXT NOT NULL,
    created_at DATETIME NOT NULL,
    CONSTRAINT pk_billing_usages PRIMARY KEY (id),
    CONSTRAINT uk_billing_usages_idempotency_key UNIQUE (idempotency_key),
    CONSTRAINT fk_billing_usages_user
        FOREIGN KEY (user_id) REFERENCES users (id),
    CONSTRAINT fk_billing_usages_project
        FOREIGN KEY (project_id) REFERENCES projects (id)
);

CREATE INDEX idx_tool_plan_groups_project_session
    ON tool_plan_groups (project_id, chat_session_id);

CREATE INDEX idx_tool_plans_group_status
    ON tool_plans (plan_group_id, status);

CREATE INDEX idx_tool_plan_runs_project_session_status
    ON tool_plan_runs (project_id, chat_session_id, status);

CREATE INDEX idx_tools_project_status
    ON tools (project_id, status);

CREATE INDEX idx_chat_messages_session_created
    ON chat_messages (chat_session_id, created_at);
```
