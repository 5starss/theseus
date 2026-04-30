# Auth API

## 공통 규칙

- 일반 회원가입 API는 제공하지 않는다.
- Super Admin이 사용자 계정을 발급한다.
- 로그인 실패 응답은 사번 존재 여부와 비밀번호 오류를 구분하지 않는다.
- Access Token은 응답 본문으로 전달한다.
- Refresh Token은 HttpOnly Cookie로 전달한다.
- Refresh Token 원문은 DB에 저장하지 않고 SHA-256 해시를 저장한다.
- 사용자당 하나의 Refresh Token만 유지한다.
- 재로그인하면 기존 Refresh Token은 새 값으로 대체된다.
- Access Token blacklist, 다중 기기 세션 정책, Refresh Token rotation 고도화는 제외한다.

## 로그인

```http
POST /api/v1/auth/login
Accept: application/json
Content-Type: application/json
```

### Request Body

```json
{
  "employeeNumber": "A123456",
  "password": "password"
}
```

### Response Body

```json
{
  "success": true,
  "code": 200,
  "message": "로그인에 성공하였습니다.",
  "result": {
    "tokenType": "Bearer",
    "accessToken": "eyJhbGciOiJIUzI1NiJ9...",
    "user": {
      "userId": 1,
      "employeeNumber": "A123456",
      "name": "홍길동",
      "systemRole": "SUPER_ADMIN",
      "isSuperAdmin": true
    }
  }
}
```

### Cookie

```http
Set-Cookie: refreshToken={refreshToken}; HttpOnly; Path=/; Max-Age={seconds}; SameSite=Lax
```

## Access Token 재발급

```http
POST /api/v1/auth/refresh
Accept: application/json
Cookie: refreshToken={refreshToken}
```

### Response Body

```json
{
  "success": true,
  "code": 200,
  "message": "Access Token이 재발급되었습니다.",
  "result": {
    "tokenType": "Bearer",
    "accessToken": "eyJhbGciOiJIUzI1NiJ9..."
  }
}
```

### Failure

| 조건 | 응답 |
| --- | --- |
| Refresh Token Cookie 없음 | `401 INVALID_REFRESH_TOKEN` |
| 저장소에 Refresh Token hash 없음 | `401 INVALID_REFRESH_TOKEN` |
| Refresh Token 만료 | `401 INVALID_REFRESH_TOKEN` |
| Refresh Token 타입 불일치 | `401 INVALID_REFRESH_TOKEN` |

## 로그아웃

```http
POST /api/v1/auth/logout
Accept: application/json
Authorization: Bearer {accessToken}
Cookie: refreshToken={refreshToken}
```

### Response Body

```json
{
  "success": true,
  "code": 200,
  "message": "로그아웃에 성공하였습니다.",
  "result": null
}
```

### Cookie

```http
Set-Cookie: refreshToken=; HttpOnly; Path=/; Max-Age=0; SameSite=Lax
```

## 저장 정책

| 항목 | 저장 위치 | 설명 |
| --- | --- | --- |
| Access Token | 클라이언트 | API 인증 헤더에 사용한다. |
| Refresh Token | HttpOnly Cookie | Access Token 재발급에 사용한다. |
| Refresh Token hash | `refresh_tokens.token_hash` | Refresh Token 원문 대신 저장한다. |
| Refresh Token 만료 시각 | `refresh_tokens.expires_at` | 재발급 가능 여부를 판단한다. |
