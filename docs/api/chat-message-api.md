# Chat Message API

## 공통 규칙

- 인증이 필요한 요청은 `Authorization: Bearer {accessToken}`을 사용한다.
- 로그인한 프로젝트 멤버는 본인이 생성한 ChatSession의 메시지만 조회, 등록할 수 있다.
- 외부 메시지 등록 API는 `senderType = USER` 메시지만 저장한다.
- ASSISTANT 메시지는 AI 완료 후 Kafka Consumer가 내부 저장 로직으로 저장한다.
- 종료된 ChatSession에는 메시지를 등록할 수 없다.
- 메시지 목록은 `messageOrder ASC`로 정렬한다.

## 채팅 메시지 등록

```http
POST /api/v1/projects/{projectId}/sessions/{sessionId}/messages
Accept: application/json
Content-Type: application/json
Authorization: Bearer {accessToken}
```

### Request Body

```json
{
  "content": "CSV 파일을 요약하는 Tool을 만들어줘",
  "messageType": "CHAT",
  "contentType": "TEXT"
}
```

### Response Body

```json
{
  "isSuccess": true,
  "code": "COMMON-201",
  "message": "리소스가 생성되었습니다.",
  "result": {
    "messageId": 1,
    "chatSessionId": 1,
    "toolId": null,
    "messageOrder": 1,
    "senderType": "USER",
    "messageType": "CHAT",
    "contentType": "TEXT",
    "content": "CSV 파일을 요약하는 Tool을 만들어줘",
    "createdAt": "2026-04-29T16:00:00"
  }
}
```

### 규칙

- `messageType`이 없으면 `CHAT`으로 저장한다.
- `contentType`이 없으면 `TEXT`로 저장한다.
- `messageOrder`는 세션 기준으로 자동 증가한다.

## 채팅 메시지 목록 조회

```http
GET /api/v1/projects/{projectId}/sessions/{sessionId}/messages
Accept: application/json
Authorization: Bearer {accessToken}
```

### Response Body

```json
{
  "isSuccess": true,
  "code": "COMMON-200",
  "message": "성공입니다.",
  "result": [
    {
      "messageId": 1,
      "chatSessionId": 1,
      "toolId": null,
      "messageOrder": 1,
      "senderType": "USER",
      "messageType": "CHAT",
      "contentType": "TEXT",
      "content": "CSV 파일을 요약하는 Tool을 만들어줘",
      "createdAt": "2026-04-29T16:00:00"
    }
  ]
}
```
