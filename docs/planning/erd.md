# ERD

## Project / ProjectMember

프로젝트의 생성자와 대표 담당자(PM)는 분리한다.

- `projects.created_by_user_id`: 프로젝트를 생성한 Super Admin
- `projects.project_admin_user_id`: 프로젝트 대표 담당자(PM)
- `project_members.project_role`: 프로젝트 내부 역할과 권한

프로젝트 생성 시 Super Admin은 프로젝트명, 설명, 담당자 사번, 담당자 이름을 입력한다. 서버는 담당자 사번과 이름으로 `users`를 조회하고, 조회된 사용자를 `projects.project_admin_user_id`에 저장한다. 같은 사용자는 `project_members`에도 `project_role = ADMIN`으로 자동 등록된다.

```sql
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
```
