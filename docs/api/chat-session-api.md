# Chat Session API

## 공통 규칙

- 인증이 필요한 요청은 `Authorization: Bearer {accessToken}`을 사용한다.
- 프로젝트 `진행중` 멤버만 ChatSession을 생성할 수 있다.
- 로그인한 프로젝트 멤버는 본인이 생성한 ChatSession만 조회, 수정, 종료할 수 있다.
- 종료된 세션은 `closedAt`이 기록된다.
- 종료된 세션에는 새 Tool 생성 요청을 제한한다.

## 채팅 세션 생성

```http
POST /api/v1/projects/{projectId}/sessions
Accept: application/json
Content-Type: application/json
Authorization: Bearer {accessToken}
```

### Request Body

```json
{
  "title": "CSV 요약 Tool 만들기"
}
```

### Response Body

```json
{
  "isSuccess": true,
  "code": "COMMON-201",
  "message": "리소스가 생성되었습니다.",
  "result": {
    "sessionId": 1,
    "projectId": 1,
    "projectMemberId": 3,
    "title": "CSV 요약 Tool 만들기",
    "isClosed": false,
    "closedAt": null,
    "createdAt": "2026-04-29T15:30:00",
    "updatedAt": "2026-04-29T15:30:00"
  }
}
```

## 채팅 세션 목록 조회

```http
GET /api/v1/projects/{projectId}/sessions?page=0&size=20
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
    "content": [],
    "page": 0,
    "size": 20,
    "totalElements": 0,
    "totalPages": 0
  }
}
```

## 채팅 세션 상세 조회

```http
GET /api/v1/projects/{projectId}/sessions/{sessionId}
Accept: application/json
Authorization: Bearer {accessToken}
```

응답에는 세션 정보와 `messageOrder ASC`로 정렬된 메시지 목록을 포함한다.

## 채팅 세션 제목 수정

```http
PATCH /api/v1/projects/{projectId}/sessions/{sessionId}
Accept: application/json
Content-Type: application/json
Authorization: Bearer {accessToken}
```

### Request Body

```json
{
  "title": "수정된 세션 제목"
}
```

### 규칙

- 제목은 150자 이하로 저장한다.

## 채팅 세션 종료

```http
PATCH /api/v1/projects/{projectId}/sessions/{sessionId}/close
Accept: application/json
Authorization: Bearer {accessToken}
```

### 규칙

- 이미 종료된 세션을 다시 종료해도 기존 `closedAt`은 유지한다.
