# Auth API

## POST `/auth/login`

사번 또는 이메일과 비밀번호를 검증하고 Access Token과 Refresh Token을 발급한다.

### Request Body

```json
{
  "loginId": "A001",
  "password": "password"
}
```

### Response Body

```json
{
  "tokenType": "Bearer",
  "accessToken": "eyJhbGciOiJIUzI1NiJ9...",
  "userId": 1,
  "name": "홍길동",
  "systemRole": "SUPER_ADMIN"
}
```

### Cookie

- `refreshToken`: HttpOnly Cookie
- DB에는 Refresh Token 원문을 저장하지 않고 SHA-256 해시를 저장한다.
- MVP에서는 사용자당 하나의 Refresh Token만 유지하며, 재로그인 시 기존 Refresh Token은 새 값으로 대체된다.

## POST `/auth/refresh`

HttpOnly Cookie의 Refresh Token을 검증하고 새 Access Token을 발급한다.

### Request

- Cookie: `refreshToken`

### Response Body

```json
{
  "tokenType": "Bearer",
  "accessToken": "eyJhbGciOiJIUzI1NiJ9..."
}
```

### Failure

- Refresh Token Cookie가 없거나 저장소에 존재하지 않으면 `401`
- Refresh Token이 만료되었거나 토큰 타입이 올바르지 않으면 `401`

## POST `/auth/logout`

저장된 Refresh Token을 삭제하고 Refresh Token Cookie를 만료시킨다.

### Request

- Cookie: `refreshToken`

### Response

- `204 No Content`
- `Set-Cookie`로 `refreshToken`을 만료 처리한다.

## 제외 범위

- Access Token blacklist 처리
- 다중 기기 세션 정책
- Refresh Token rotation 고도화
