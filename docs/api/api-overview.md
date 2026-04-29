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
