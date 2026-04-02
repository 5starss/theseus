# 싸피증권 API

## API 카테고리 목차

1. [API 공통 설정](#api-공통-설정)
2. [인증 API](#인증-api)
3. [사용자 API](#사용자-api)
4. [관심종목 API](#관심종목-api)
5. [랭킹 API](#랭킹-api)
6. [계좌·보유종목 API](#계좌보유종목-api)
7. [주문·체결 API](#주문체결-api)
8. [주식 시세 API](#주식-시세-api)
9. [실시간 시세 WebSocket API](#실시간-시세-websocket-api)
10. [알림 API](#알림-api)
11. [AI 자동매매 API](#ai-자동매매-api)
12. [관리자·운영 API](#관리자운영-api)
13. [추가 확인 필요 항목](#추가-확인-필요-항목)

## API 공통 설정

### API URL

| 구분 | 값 | 근거 |
| --- | --- | --- |
| 운영 Gateway Base URL | `https://j14a503.p.ssafy.io` | `frontend/nginx.conf` |
| 로컬 Gateway Base URL | `http://localhost:8080` | `frontend/vite.config.ts`, `backend/api-gateway/src/main/resources/application-local.yml` |
| Core 외부 Prefix | `/api/v1/core` | Gateway route rewrite |
| Market 외부 Prefix | `/api/v1/market` | Gateway route rewrite |
| AI 외부 Prefix | `/api/v1/ai` | Gateway route rewrite (`/v1/*`로 내부 변환) |
| WebSocket 외부 URL | `/ws/v1/stocks` | Gateway direct route |

### 요청 헤더

| 헤더 | 값 | 필수 여부 | 설명 |
| --- | --- | --- | --- |
| `Content-Type` | `application/json` | JSON Body 요청 시 필수 | Core/Market/AI JSON API 공통 |
| `Authorization` | `Bearer {accessToken}` | 인증 필요 API에서 필수 | Gateway JWT 검증용 |
| `Cookie` | `refresh_token={token}` | `POST /api/v1/core/auth/refresh` 필수 | Refresh 토큰은 HttpOnly 쿠키로 관리 |
| `X-User-Id` | 직접 전송하지 않음 | 클라이언트 직접 전송 불필요 | Gateway가 JWT에서 추출해 내부 서비스에 주입 |

### 인증 방식

| 항목 | 구현 기준 |
| --- | --- |
| 인증 방식 | JWT Bearer Access Token |
| Access Token 발급 | `POST /api/v1/core/auth/login`, `POST /api/v1/core/auth/refresh` |
| Refresh Token 저장 | HttpOnly Cookie `refresh_token` |
| Refresh Cookie Path | `/api/v1/core/auth` |
| Access Token 기본 만료 | 3,600,000ms (1시간) |
| Refresh Token 기본 만료 | 1,209,600,000ms (14일) |
| SSE / WebSocket 인증 전달 | 브라우저 제약으로 `token` Query Parameter 허용 |
| Gateway 인증 실패 응답 | `401 Unauthorized`, 본문 없음 |

### 공통 응답 형식

#### 1. Core API / Market API 공통 래퍼

```json
{
  "isSuccess": true,
  "code": "GLOBAL-200",
  "message": "요청 응답에 성공했습니다.",
  "result": {}
}
```

#### 2. AI API 공통 형식

```json
{
  "status": "ok",
  "message": "..."
}
```

- AI API는 `ApiResponse` 래퍼를 사용하지 않는다.
- FastAPI 검증 실패 시 기본적으로 `422 Unprocessable Entity`와 `detail` 배열을 반환한다.
- AI API에서 서버 예외는 주로 `500 Internal Server Error`와 `{"detail":"..."}` 형식으로 반환된다.

#### 3. Gateway 인증 실패

```http
HTTP/1.1 401 Unauthorized
```

본문은 없다.

### 응답 상태 코드

| HTTP 상태 | 코드 | 설명 |
| --- | --- | --- |
| `200 OK` | `GLOBAL-200` 또는 AI `status=ok` | 조회/처리 성공 |
| `201 Created` | `GLOBAL-201` | 생성 성공 |
| `202 Accepted` | `GLOBAL-202` | 취소 요청 접수 등 비동기 처리 시작 |
| `400 Bad Request` | `COMMON001`, `COMMON006`, `ORD008`, `STOCK-400` | 입력값 오류, 요청 조건 불만족, 장 마감 등 |
| `401 Unauthorized` | `AUTH001`, `AUTH007`, Gateway 401 | 토큰 누락/만료/위조, refresh 토큰 오류 |
| `403 Forbidden` | `AUTH-008` | 접근 권한 없음 |
| `404 Not Found` | `USR001`, `ACC001`, `ORD003`, `ORD004`, `STK001`, `WAT002`, `STOCK-404` | 리소스 없음 |
| `409 Conflict` | `AUTH002`, `WAT001` | 중복 리소스 |
| `422 Unprocessable Entity` | FastAPI 기본 검증 오류 | AI API Query/Body 검증 실패 |
| `500 Internal Server Error` | `COMMON002`, `STOCK-500` | 서버 내부 오류 |

### 공통 에러 코드

#### Core API 에러 코드

| 에러 코드 | HTTP 상태 | 메시지 |
| --- | --- | --- |
| `COMMON001` | `400` | 잘못된 입력값입니다. |
| `COMMON002` | `500` | 서버 내부 에러가 발생했습니다. |
| `COMMON003` | `404` | 존재하지 않는 리소스입니다. |
| `COMMON004` | `405` | 지원하지 않는 HTTP 메서드입니다. |
| `COMMON005` | `409` | 이미 존재하는 리소스입니다. |
| `COMMON006` | `400` | 잘못된 요청입니다. |
| `AUTH-008` | `403` | 해당 기능에 접근할 권한이 없습니다. |
| `AUTH001` | `401` | 유효하지 않은 토큰입니다. |
| `AUTH002` | `409` | 이미 가입된 이메일입니다. |
| `AUTH005` | `401` | 이메일 또는 비밀번호가 일치하지 않습니다. |
| `AUTH007` | `401` | 유효하지 않은 리프레시 토큰입니다. |
| `USR001` | `404` | 해당 유저를 찾을 수 없습니다. |
| `STK001` | `404` | 해당 주식 종목을 찾을 수 없습니다. |
| `WAT001` | `409` | 이미 관심종목에 등록된 종목입니다. |
| `WAT002` | `404` | 관심종목 내역을 찾을 수 없습니다. |
| `WAT003` | `400` | 관심종목은 최대 3개까지만 등록할 수 있습니다. |
| `ACC001` | `404` | 해당 유저의 계좌 정보를 찾을 수 없습니다. |
| `POS001` | `400` | 해당 종목의 보유 주식이 없습니다. |
| `ORD001` | `400` | 주문 가능한 잔고가 부족합니다. |
| `ORD002` | `400` | 주문 가능한 보유 주식이 부족합니다. |
| `ORD003` | `404` | 해당 주문을 찾을 수 없습니다. |
| `ORD004` | `404` | 해당 체결 내역을 찾을 수 없습니다. |
| `ORD005` | `400` | 취소할 수 없는 상태의 주문입니다. |
| `ORD006` | `400` | 이미 완료되었거나 취소된 주문입니다. |
| `ORD007` | `500` | 체결 수량이 잔여 수량을 초과했습니다. |
| `ORD008` | `400` | 장외 시간 혹은 휴장일에는 주문이 불가능합니다. |

#### Market API 에러 코드

| 에러 코드 | HTTP 상태 | 메시지 |
| --- | --- | --- |
| `STOCK-400` | `400` | Query / Path 파라미터 오류 |
| `STOCK-404` | `404` | 시세 스냅샷 또는 호가 데이터 없음 |
| `STOCK-500` | `500` | Market 서버 처리 오류 |

#### AI API 오류 형식

| 케이스 | HTTP 상태 | 응답 형식 |
| --- | --- | --- |
| Query / Body 검증 실패 | `422` | `{"detail":[...]}` |
| 서버 예외 | `500` | `{"detail":"..."}` |

## API Reference

## 인증 API

### 1. 회원가입

**설명**  
신규 사용자를 생성하고 USER/AI 계좌를 자동 생성한다. 인증은 필요하지 않다.

**요청 URL**  
`POST /api/v1/core/auth/signup`

**요청 Header**  
`Content-Type: application/json`

**요청 Parameter**  
없음

**요청 Body**

```json
{
  "email": "user@ssafy.com",
  "password": "P@ssw0rd!",
  "nickname": "홍길동",
  "investmentStyle": "GROWTH"
}
```

**성공응답 예시**

```json
{
  "isSuccess": true,
  "code": "GLOBAL-201",
  "message": "생성에 성공했습니다.",
  "result": {
    "userId": 101
  }
}
```

**실패응답 예시**

```json
{
  "isSuccess": false,
  "code": "AUTH002",
  "message": "이미 가입된 이메일입니다.",
  "result": null
}
```

**필드 설명**

| 구분 | 필드 | 타입 | 필수 | 설명 |
| --- | --- | --- | --- | --- |
| Body | `email` | `string` | Y | 로그인 이메일 |
| Body | `password` | `string` | Y | 로그인 비밀번호 |
| Body | `nickname` | `string` | Y | 사용자 닉네임 |
| Body | `investmentStyle` | `BALANCED \| GROWTH \| AGGRESSIVE` | Y | 투자 성향 |
| Result | `userId` | `number` | Y | 생성된 사용자 ID |

**비고**  
회원가입 성공 시 USER 계좌에는 `100000000`, AI 계좌에는 `0`이 초기 입금된다.

### 2. 로그인

**설명**  
이메일/비밀번호로 로그인하고 Access Token을 반환하며 Refresh Token 쿠키를 설정한다.

**요청 URL**  
`POST /api/v1/core/auth/login`

**요청 Header**  
`Content-Type: application/json`

**요청 Parameter**  
없음

**요청 Body**

```json
{
  "email": "user@ssafy.com",
  "password": "P@ssw0rd!"
}
```

**성공응답 예시**

```json
{
  "isSuccess": true,
  "code": "GLOBAL-200",
  "message": "요청 응답에 성공했습니다.",
  "result": {
    "userId": 101,
    "tokenType": "Bearer",
    "accessToken": "eyJhbGciOiJSUzI1NiJ9...",
    "nickname": "홍길동",
    "accessTokenExpiresAt": "2026-04-02T15:30:00"
  }
}
```

**실패응답 예시**

```json
{
  "isSuccess": false,
  "code": "AUTH005",
  "message": "이메일 또는 비밀번호가 일치하지 않습니다.",
  "result": null
}
```

**필드 설명**

| 구분 | 필드 | 타입 | 필수 | 설명 |
| --- | --- | --- | --- | --- |
| Body | `email` | `string` | Y | 로그인 이메일 |
| Body | `password` | `string` | Y | 로그인 비밀번호 |
| Result | `userId` | `number` | Y | 사용자 ID |
| Result | `tokenType` | `string` | Y | 항상 `Bearer` |
| Result | `accessToken` | `string` | Y | JWT Access Token |
| Result | `nickname` | `string` | Y | 사용자 닉네임 |
| Result | `accessTokenExpiresAt` | `string(date-time)` | Y | Access Token 만료 시각 |

**비고**  
응답 헤더 `Set-Cookie`로 HttpOnly `refresh_token` 쿠키가 함께 내려온다.

### 3. Access Token 재발급

**설명**  
Refresh Token 쿠키를 이용해 Access Token을 재발급한다.

**요청 URL**  
`POST /api/v1/core/auth/refresh`

**요청 Header**  
`Cookie: refresh_token={token}`

**요청 Parameter**  
없음

**요청 Body**

```json
{}
```

**성공응답 예시**

```json
{
  "isSuccess": true,
  "code": "GLOBAL-200",
  "message": "요청 응답에 성공했습니다.",
  "result": {
    "userId": 101,
    "tokenType": "Bearer",
    "accessToken": "eyJhbGciOiJSUzI1NiJ9...",
    "nickname": "홍길동",
    "accessTokenExpiresAt": "2026-04-02T16:30:00"
  }
}
```

**실패응답 예시**

```json
{
  "isSuccess": false,
  "code": "AUTH007",
  "message": "유효하지 않은 리프레시 토큰입니다.",
  "result": null
}
```

**필드 설명**

| 구분 | 필드 | 타입 | 필수 | 설명 |
| --- | --- | --- | --- | --- |
| Cookie | `refresh_token` | `string` | Y | Refresh Token |
| Result | `userId` | `number` | Y | 사용자 ID |
| Result | `tokenType` | `string` | Y | 항상 `Bearer` |
| Result | `accessToken` | `string` | Y | 재발급된 Access Token |
| Result | `nickname` | `string` | Y | 사용자 닉네임 |
| Result | `accessTokenExpiresAt` | `string(date-time)` | Y | Access Token 만료 시각 |

**비고**  
응답 시 Refresh Token 쿠키도 함께 재설정된다.

### 4. 로그아웃

**설명**  
Redis에 저장된 Refresh Token을 삭제하고 Refresh Token 쿠키를 만료시킨다.

**요청 URL**  
`POST /api/v1/core/auth/logout`

**요청 Header**  
`Authorization: Bearer {accessToken}`

**요청 Parameter**  
없음

**요청 Body**  
없음

**성공응답 예시**

```json
{
  "isSuccess": true,
  "code": "GLOBAL-200",
  "message": "요청 응답에 성공했습니다.",
  "result": null
}
```

**실패응답 예시**

```http
HTTP/1.1 401 Unauthorized
```

**필드 설명**

| 구분 | 필드 | 타입 | 필수 | 설명 |
| --- | --- | --- | --- | --- |
| Header | `Authorization` | `string` | Y | Bearer Access Token |

**비고**  
CSRF Origin 검사는 설정값이 기본 `false`라 기본 환경에서는 비활성화되어 있다.

## 사용자 API

### 5. 내 프로필 조회

**설명**  
현재 로그인한 사용자의 프로필을 조회한다.

**요청 URL**  
`GET /api/v1/core/users/me`

**요청 Header**  
`Authorization: Bearer {accessToken}`

**요청 Parameter**  
없음

**요청 Body**  
없음

**성공응답 예시**

```json
{
  "isSuccess": true,
  "code": "GLOBAL-200",
  "message": "요청 응답에 성공했습니다.",
  "result": {
    "userId": 101,
    "email": "user@ssafy.com",
    "nickname": "홍길동",
    "investmentStyle": "GROWTH"
  }
}
```

**실패응답 예시**

```json
{
  "isSuccess": false,
  "code": "USR001",
  "message": "해당 유저를 찾을 수 없습니다.",
  "result": null
}
```

**필드 설명**

| 구분 | 필드 | 타입 | 필수 | 설명 |
| --- | --- | --- | --- | --- |
| Result | `userId` | `number` | Y | 사용자 ID |
| Result | `email` | `string` | Y | 이메일 |
| Result | `nickname` | `string` | Y | 닉네임 |
| Result | `investmentStyle` | `BALANCED \| GROWTH \| AGGRESSIVE` | Y | 투자 성향 |

**비고**  
Gateway가 JWT에서 추출한 사용자 ID를 내부 헤더로 전달한다.

### 6. 투자 성향 수정

**설명**  
현재 로그인한 사용자의 투자 성향을 수정한다.

**요청 URL**  
`PATCH /api/v1/core/users/me/investment-style`

**요청 Header**  
`Authorization: Bearer {accessToken}`  
`Content-Type: application/json`

**요청 Parameter**  
없음

**요청 Body**

```json
{
  "investmentStyle": "BALANCED"
}
```

**성공응답 예시**

```json
{
  "isSuccess": true,
  "code": "GLOBAL-200",
  "message": "요청 응답에 성공했습니다.",
  "result": {
    "userId": 101,
    "email": "user@ssafy.com",
    "nickname": "홍길동",
    "investmentStyle": "BALANCED"
  }
}
```

**실패응답 예시**

```json
{
  "isSuccess": false,
  "code": "COMMON001",
  "message": "잘못된 입력값입니다.",
  "result": null
}
```

**필드 설명**

| 구분 | 필드 | 타입 | 필수 | 설명 |
| --- | --- | --- | --- | --- |
| Body | `investmentStyle` | `BALANCED \| GROWTH \| AGGRESSIVE` | Y | 변경할 투자 성향 |
| Result | `userId` | `number` | Y | 사용자 ID |
| Result | `email` | `string` | Y | 이메일 |
| Result | `nickname` | `string` | Y | 닉네임 |
| Result | `investmentStyle` | `BALANCED \| GROWTH \| AGGRESSIVE` | Y | 변경된 투자 성향 |

**비고**  
`investmentStyle` 누락 시 `COMMON001`이 반환된다.

## 관심종목 API

### 7. 관심종목 등록

**설명**  
현재 사용자의 관심종목을 등록한다.

**요청 URL**  
`POST /api/v1/core/watchlists`

**요청 Header**  
`Authorization: Bearer {accessToken}`  
`Content-Type: application/json`

**요청 Parameter**  
없음

**요청 Body**

```json
{
  "ticker": "005930"
}
```

**성공응답 예시**

```json
{
  "isSuccess": true,
  "code": "GLOBAL-201",
  "message": "생성에 성공했습니다.",
  "result": null
}
```

**실패응답 예시**

```json
{
  "isSuccess": false,
  "code": "WAT003",
  "message": "관심종목은 최대 3개까지만 등록할 수 있습니다.",
  "result": null
}
```

**필드 설명**

| 구분 | 필드 | 타입 | 필수 | 설명 |
| --- | --- | --- | --- | --- |
| Body | `ticker` | `string` | Y | 6자리 종목 코드 |

**비고**  
중복 등록 시 `WAT001`, 존재하지 않는 종목이면 `STK001`이 반환된다.

### 8. 관심종목 삭제

**설명**  
등록된 관심종목을 삭제한다.

**요청 URL**  
`DELETE /api/v1/core/watchlists/{ticker}`

**요청 Header**  
`Authorization: Bearer {accessToken}`

**요청 Parameter**

| 이름 | 위치 | 타입 | 필수 | 설명 |
| --- | --- | --- | --- | --- |
| `ticker` | Path | `string` | Y | 삭제할 종목 코드 |

**요청 Body**  
없음

**성공응답 예시**

```json
{
  "isSuccess": true,
  "code": "GLOBAL-200",
  "message": "요청 응답에 성공했습니다.",
  "result": null
}
```

**실패응답 예시**

```json
{
  "isSuccess": false,
  "code": "WAT002",
  "message": "관심종목 내역을 찾을 수 없습니다.",
  "result": null
}
```

**필드 설명**

| 구분 | 필드 | 타입 | 필수 | 설명 |
| --- | --- | --- | --- | --- |
| Path | `ticker` | `string` | Y | 종목 코드 |

**비고**  
Path `ticker`는 trim 후 비교된다.

### 9. 관심종목 목록 조회

**설명**  
현재 사용자의 관심종목 목록과 보유 여부를 조회한다.

**요청 URL**  
`GET /api/v1/core/watchlists`

**요청 Header**  
`Authorization: Bearer {accessToken}`

**요청 Parameter**  
없음

**요청 Body**  
없음

**성공응답 예시**

```json
{
  "isSuccess": true,
  "code": "GLOBAL-200",
  "message": "요청 응답에 성공했습니다.",
  "result": [
    {
      "ticker": "005930",
      "companyName": "삼성전자",
      "marketType": "KOSPI",
      "logoUrl": "/icons/stocks/005930.png",
      "isHeld": true,
      "quantity": 12
    }
  ]
}
```

**실패응답 예시**

```json
{
  "isSuccess": false,
  "code": "USR001",
  "message": "해당 유저를 찾을 수 없습니다.",
  "result": null
}
```

**필드 설명**

| 필드 | 타입 | 설명 |
| --- | --- | --- |
| `ticker` | `string` | 종목 코드 |
| `companyName` | `string` | 종목명 |
| `marketType` | `string \| null` | 시장 구분 |
| `logoUrl` | `string \| null` | 로고 URL |
| `isHeld` | `boolean` | USER 계좌 보유 여부 |
| `quantity` | `number` | USER 계좌 보유 수량 |

**비고**  
보유 여부는 USER 계좌 기준으로 계산된다.

## 랭킹 API

### 10. 랭킹 조회

**설명**  
최신 랭킹 목록을 페이지 단위로 조회한다. JWT가 없어도 호출 가능하며, 로그인한 경우 `myRanking`이 함께 내려온다.

**요청 URL**  
`GET /api/v1/core/rankings`

**요청 Header**  
없음 또는 `Authorization: Bearer {accessToken}`

**요청 Parameter**

| 이름 | 위치 | 타입 | 필수 | 기본값 | 설명 |
| --- | --- | --- | --- | --- | --- |
| `nickname` | Query | `string` | N | - | 닉네임 검색 |
| `page` | Query | `number` | N | `0` | 페이지 번호 |
| `size` | Query | `number` | N | `10` | 페이지 크기 |

**요청 Body**  
없음

**성공응답 예시**

```json
{
  "isSuccess": true,
  "code": "GLOBAL-200",
  "message": "요청 응답에 성공했습니다.",
  "result": {
    "myRanking": {
      "userId": 101,
      "rank": 3,
      "nickname": "홍길동",
      "roi": 4.3210,
      "rankDateTime": "2026-04-02T15:30:00",
      "percentile": 6.0
    },
    "rankings": {
      "content": [
        {
          "userId": 201,
          "rank": 1,
          "nickname": "투자왕",
          "roi": 10.5123,
          "rankDateTime": "2026-04-02T15:30:00",
          "percentile": 2.0
        }
      ],
      "page": 0,
      "size": 10,
      "totalElements": 50,
      "totalPages": 5,
      "last": false
    }
  }
}
```

**실패응답 예시**

```json
{
  "isSuccess": false,
  "code": "COMMON002",
  "message": "서버 내부 에러가 발생했습니다.",
  "result": null
}
```

**필드 설명**

| 필드 | 타입 | 설명 |
| --- | --- | --- |
| `myRanking` | `object \| null` | 로그인 사용자 랭킹. 비로그인 시 `null` |
| `rankings.content[].userId` | `number` | 사용자 ID |
| `rankings.content[].rank` | `number` | 순위 |
| `rankings.content[].nickname` | `string` | 닉네임 |
| `rankings.content[].roi` | `number` | 수익률 |
| `rankings.content[].rankDateTime` | `string(date-time)` | 랭킹 산출 시각 |
| `rankings.content[].percentile` | `number` | 백분위 |

**비고**  
Gateway whitelist에 포함되어 있어 인증 없이 접근 가능하다.

### 11. 랭킹 스냅샷 생성

**설명**  
일일 랭킹 스냅샷을 수동 생성한다. 코드 주석상 관리자/테스트용이지만 현재 Gateway 설정상 무인증 호출이 가능하다.

**요청 URL**  
`POST /api/v1/core/rankings/snapshot`

**요청 Header**  
없음

**요청 Parameter**  
없음

**요청 Body**  
없음

**성공응답 예시**

```json
{
  "isSuccess": true,
  "code": "GLOBAL-200",
  "message": "요청 응답에 성공했습니다.",
  "result": null
}
```

**실패응답 예시**

```json
{
  "isSuccess": false,
  "code": "COMMON002",
  "message": "서버 내부 에러가 발생했습니다.",
  "result": null
}
```

**필드 설명**  
없음

**비고**  
운영용 공개 API로 보기 어려우며 실제 배포 정책 확인이 필요하다.

## 계좌·보유종목 API

### 12. 계좌 잔고 조회

**설명**  
USER 또는 AI 계좌의 현금 잔고를 조회한다.

**요청 URL**  
`GET /api/v1/core/accounts/balance`

**요청 Header**  
`Authorization: Bearer {accessToken}`

**요청 Parameter**

| 이름 | 위치 | 타입 | 필수 | 기본값 | 설명 |
| --- | --- | --- | --- | --- | --- |
| `account_type` | Query | `USER \| AI` | N | `USER` | 조회 계좌 구분 |

**요청 Body**  
없음

**성공응답 예시**

```json
{
  "isSuccess": true,
  "code": "GLOBAL-200",
  "message": "요청 응답에 성공했습니다.",
  "result": {
    "dncaTotAmt": 100000000,
    "lockedAmt": 250000,
    "availableAmt": 99750000
  }
}
```

**실패응답 예시**

```json
{
  "isSuccess": false,
  "code": "ACC001",
  "message": "해당 유저의 계좌 정보를 찾을 수 없습니다.",
  "result": null
}
```

**필드 설명**

| 필드 | 타입 | 설명 |
| --- | --- | --- |
| `dncaTotAmt` | `number` | 총 예수금 |
| `lockedAmt` | `number` | 주문으로 묶인 금액 |
| `availableAmt` | `number` | 주문/출금 가능 금액 |

**비고**  
`account_type` 미전달 시 USER 계좌를 조회한다.

### 13. 계좌 요약 조회

**설명**  
계좌 총자산, 손익, 보유 포지션 요약을 조회한다.

**요청 URL**  
`GET /api/v1/core/accounts/summary`

**요청 Header**  
`Authorization: Bearer {accessToken}`

**요청 Parameter**

| 이름 | 위치 | 타입 | 필수 | 기본값 | 설명 |
| --- | --- | --- | --- | --- | --- |
| `account_type` | Query | `USER \| AI` | N | `USER` | 조회 계좌 구분 |

**요청 Body**  
없음

**성공응답 예시**

```json
{
  "isSuccess": true,
  "code": "GLOBAL-200",
  "message": "요청 응답에 성공했습니다.",
  "result": {
    "accountId": 11,
    "totalAmt": 102400000,
    "availableAmt": 25000000,
    "lockedAmt": 0,
    "totalUnrealizedPnL": 2400000,
    "totalReturnRate": 2.40,
    "priceDataAvailable": true,
    "positions": [
      {
        "ticker": "005930",
        "companyName": "삼성전자",
        "quantity": 12,
        "averagePrice": 70000,
        "currentPrice": 72000,
        "evaluatedAmount": 864000,
        "unrealizedPnL": 24000,
        "returnRate": 2.86
      }
    ]
  }
}
```

**실패응답 예시**

```json
{
  "isSuccess": false,
  "code": "ACC001",
  "message": "해당 유저의 계좌 정보를 찾을 수 없습니다.",
  "result": null
}
```

**필드 설명**

| 필드 | 타입 | 설명 |
| --- | --- | --- |
| `accountId` | `number` | 계좌 ID |
| `totalAmt` | `number` | 총자산 |
| `availableAmt` | `number` | 사용 가능 금액 |
| `lockedAmt` | `number` | 주문으로 묶인 금액 |
| `totalUnrealizedPnL` | `number \| null` | 평가손익 |
| `totalReturnRate` | `number \| null` | 총 수익률(%) |
| `priceDataAvailable` | `boolean` | 실시간 가격 반영 가능 여부 |
| `positions[]` | `array` | 보유 종목 요약 |

**비고**  
실시간 가격을 모두 가져오지 못하면 `priceDataAvailable=false`이며 손익 관련 필드가 `null`일 수 있다.

### 14. 계좌 거래내역 조회

**설명**  
입출금 및 매매로 발생한 계좌 거래내역을 페이지 단위로 조회한다.

**요청 URL**  
`GET /api/v1/core/accounts/history`

**요청 Header**  
`Authorization: Bearer {accessToken}`

**요청 Parameter**

| 이름 | 위치 | 타입 | 필수 | 기본값 | 설명 |
| --- | --- | --- | --- | --- | --- |
| `account_type` | Query | `USER \| AI` | N | `USER` | 조회 계좌 구분 |
| `year` | Query | `number` | N | - | 연도 필터 |
| `month` | Query | `number` | N | - | 월 필터 |
| `page` | Query | `number` | N | `0` | 페이지 번호 |
| `size` | Query | `number` | N | `20` | 페이지 크기 |

**요청 Body**  
없음

**성공응답 예시**

```json
{
  "isSuccess": true,
  "code": "GLOBAL-200",
  "message": "요청 응답에 성공했습니다.",
  "result": {
    "year": 2026,
    "month": 4,
    "histories": {
      "content": [
        {
          "historyId": 1001,
          "transactionType": "BUY",
          "executedAt": "2026-04-02T09:05:00",
          "ticker": "005930",
          "stockName": "삼성전자",
          "quantity": 10,
          "price": 70000,
          "fee": 1050,
          "tax": 0,
          "amount": -701050,
          "balanceAfter": 99298950
        }
      ],
      "page": 0,
      "size": 20,
      "totalElements": 1,
      "totalPages": 1,
      "last": true
    }
  }
}
```

**실패응답 예시**

```json
{
  "isSuccess": false,
  "code": "ACC001",
  "message": "해당 유저의 계좌 정보를 찾을 수 없습니다.",
  "result": null
}
```

**필드 설명**

| 필드 | 타입 | 설명 |
| --- | --- | --- |
| `year` | `number \| null` | 요청한 연도 |
| `month` | `number \| null` | 요청한 월 |
| `histories.content[].historyId` | `number` | 거래내역 ID |
| `histories.content[].transactionType` | `DEPOSIT \| WITHDRAWAL \| BUY \| SELL` | 거래 유형 |
| `histories.content[].executedAt` | `string(date-time)` | 거래 시각 |
| `histories.content[].ticker` | `string \| null` | 종목 코드 |
| `histories.content[].stockName` | `string \| null` | 종목명 |
| `histories.content[].quantity` | `number` | 수량 |
| `histories.content[].price` | `number \| null` | 단가 |
| `histories.content[].fee` | `number \| null` | 수수료 |
| `histories.content[].tax` | `number \| null` | 세금 |
| `histories.content[].amount` | `number` | 거래 금액 |
| `histories.content[].balanceAfter` | `number` | 거래 후 잔액 |

**비고**  
`year`, `month`를 모두 전달한 경우 해당 월 범위만 조회한다.

### 15. 계좌 간 자금 이동

**설명**  
동일 사용자 계좌(USER/AI) 간 자금을 이체한다.

**요청 URL**  
`POST /api/v1/core/accounts/transfer`

**요청 Header**  
`Authorization: Bearer {accessToken}`  
`Content-Type: application/json`

**요청 Parameter**  
없음

**요청 Body**

```json
{
  "from_type": "USER",
  "to_type": "AI",
  "amount": 500000
}
```

**성공응답 예시**

```json
{
  "isSuccess": true,
  "code": "GLOBAL-200",
  "message": "요청 응답에 성공했습니다.",
  "result": null
}
```

**실패응답 예시**

```json
{
  "isSuccess": false,
  "code": "COMMON006",
  "message": "잘못된 요청입니다.",
  "result": null
}
```

**필드 설명**

| 구분 | 필드 | 타입 | 필수 | 설명 |
| --- | --- | --- | --- | --- |
| Body | `from_type` | `USER \| AI` | Y | 출금 계좌 |
| Body | `to_type` | `USER \| AI` | Y | 입금 계좌 |
| Body | `amount` | `number` | Y | 이체 금액. 0보다 커야 함 |

**비고**  
출금 계좌와 입금 계좌가 같으면 `COMMON006`, 잔고 부족이면 `ORD001`이 반환된다.

### 16. 보유 포지션 조회

**설명**  
계좌의 종목별 보유 수량을 조회한다.

**요청 URL**  
`GET /api/v1/core/positions`

**요청 Header**  
`Authorization: Bearer {accessToken}`

**요청 Parameter**

| 이름 | 위치 | 타입 | 필수 | 기본값 | 설명 |
| --- | --- | --- | --- | --- | --- |
| `account_type` | Query | `USER \| AI` | N | `USER` | 조회 계좌 구분 |

**요청 Body**  
없음

**성공응답 예시**

```json
{
  "isSuccess": true,
  "code": "GLOBAL-200",
  "message": "요청 응답에 성공했습니다.",
  "result": [
    {
      "ticker": "005930",
      "quantity": 12,
      "lockedQuantity": 2,
      "availableQuantity": 10,
      "averagePrice": 70000,
      "totalPurchaseAmount": 840000,
      "companyName": "삼성전자"
    }
  ]
}
```

**실패응답 예시**

```json
{
  "isSuccess": false,
  "code": "ACC001",
  "message": "해당 유저의 계좌 정보를 찾을 수 없습니다.",
  "result": null
}
```

**필드 설명**

| 필드 | 타입 | 설명 |
| --- | --- | --- |
| `ticker` | `string` | 종목 코드 |
| `quantity` | `number` | 총 보유 수량 |
| `lockedQuantity` | `number` | 주문으로 묶인 수량 |
| `availableQuantity` | `number` | 매도 가능한 수량 |
| `averagePrice` | `number` | 평균 매수 단가 |
| `totalPurchaseAmount` | `number` | 총 매수 금액 |
| `companyName` | `string` | 종목명 |

**비고**  
`account_type`를 생략하면 USER 계좌를 조회한다.

## 주문·체결 API

### 17. 수수료/세금 정책 조회

**설명**  
매매 수수료와 세금 정책을 조회한다. 인증 없이 접근 가능하다.

**요청 URL**  
`GET /api/v1/core/orders/trade-policy`

**요청 Header**  
없음

**요청 Parameter**  
없음

**요청 Body**  
없음

**성공응답 예시**

```json
{
  "isSuccess": true,
  "code": "GLOBAL-200",
  "message": "요청 응답에 성공했습니다.",
  "result": {
    "feeRate": 0.0015,
    "taxRate": 0.0018
  }
}
```

**실패응답 예시**

```json
{
  "isSuccess": false,
  "code": "COMMON002",
  "message": "서버 내부 에러가 발생했습니다.",
  "result": null
}
```

**필드 설명**

| 필드 | 타입 | 설명 |
| --- | --- | --- |
| `feeRate` | `number` | 거래 수수료율 |
| `taxRate` | `number` | 거래 세율 |

**비고**  
응답 값은 `TradePolicy.FEE_RATE`, `TradePolicy.TAX_RATE` 상수 기준이다.

### 18. 주문 생성

**설명**  
매수 또는 매도 주문을 생성한다. 주문 생성 시 시장 개장 상태를 먼저 검사한다.

**요청 URL**  
`POST /api/v1/core/orders`

**요청 Header**  
`Authorization: Bearer {accessToken}`  
`Content-Type: application/json`

**요청 Parameter**  
없음

**요청 Body**

```json
{
  "ticker": "005930",
  "order_type": "BUY",
  "price_type": "LIMIT",
  "account_type": "USER",
  "price": 70000,
  "quantity": 10
}
```

**성공응답 예시**

```json
{
  "isSuccess": true,
  "code": "GLOBAL-201",
  "message": "생성에 성공했습니다.",
  "result": {
    "orderId": 5001,
    "status": "OPEN",
    "requestedQuantity": 10,
    "executedQuantity": 0,
    "price": 70000,
    "ticker": "005930",
    "orderType": "BUY",
    "createdAt": "2026-04-02T09:01:00"
  }
}
```

**실패응답 예시**

```json
{
  "isSuccess": false,
  "code": "ORD008",
  "message": "장외 시간 혹은 휴장일에는 주문이 불가능합니다.",
  "result": null
}
```

**필드 설명**

| 구분 | 필드 | 타입 | 필수 | 설명 |
| --- | --- | --- | --- | --- |
| Body | `ticker` | `string` | Y | 종목 코드 |
| Body | `order_type` | `BUY \| SELL` | Y | 주문 구분 |
| Body | `price_type` | `LIMIT \| MARKET` | N | 기본값 `LIMIT` |
| Body | `account_type` | `USER \| AI` | N | 기본값 `USER` |
| Body | `price` | `number` | Y | 주문 가격 |
| Body | `quantity` | `number` | Y | 주문 수량 |
| Result | `orderId` | `number` | Y | 주문 ID |
| Result | `status` | `OPEN \| PARTIAL \| FILLED \| PENDING_CANCEL \| CANCELLED` | Y | 주문 상태 |
| Result | `requestedQuantity` | `number` | Y | 요청 수량 |
| Result | `executedQuantity` | `number` | Y | 체결 수량 |
| Result | `price` | `number` | Y | 주문 가격 |
| Result | `ticker` | `string` | Y | 종목 코드 |
| Result | `orderType` | `BUY \| SELL` | Y | 주문 구분 |
| Result | `createdAt` | `string(date-time)` | Y | 주문 생성 시각 |

**비고**  
매수 시 잔고를, 매도 시 보유 수량을 즉시 잠근다.

### 19. 주문 취소 요청

**설명**  
주문 상태가 `OPEN` 또는 `PARTIAL`인 주문에 대해 취소 요청을 접수한다.

**요청 URL**  
`POST /api/v1/core/orders/{orderId}/cancel`

**요청 Header**  
`Authorization: Bearer {accessToken}`

**요청 Parameter**

| 이름 | 위치 | 타입 | 필수 | 설명 |
| --- | --- | --- | --- | --- |
| `orderId` | Path | `number` | Y | 주문 ID |

**요청 Body**  
없음

**성공응답 예시**

```json
{
  "isSuccess": true,
  "code": "GLOBAL-202",
  "message": "요청이 접수되었습니다.",
  "result": null
}
```

**실패응답 예시**

```json
{
  "isSuccess": false,
  "code": "ORD005",
  "message": "취소할 수 없는 상태의 주문입니다.",
  "result": null
}
```

**필드 설명**

| 구분 | 필드 | 타입 | 필수 | 설명 |
| --- | --- | --- | --- | --- |
| Path | `orderId` | `number` | Y | 취소 대상 주문 ID |

**비고**  
성공 시 주문 상태는 우선 `PENDING_CANCEL`로 변경되며 SSE `ORDER_CANCEL` 이벤트가 발행된다.

### 20. 주문/체결 내역 조회

**설명**  
대기 주문과 완료 이력을 한 번에 조회한다.

**요청 URL**  
`GET /api/v1/core/orders`

**요청 Header**  
`Authorization: Bearer {accessToken}`

**요청 Parameter**

| 이름 | 위치 | 타입 | 필수 | 기본값 | 설명 |
| --- | --- | --- | --- | --- | --- |
| `account_type` | Query | `USER \| AI` | N | `USER` | 조회 계좌 구분 |
| `page` | Query | `number` | N | `0` | 페이지 번호 |
| `size` | Query | `number` | N | `20` | 페이지 크기 |
| `status` | Query | `string` | N | `ALL` | 구현상 `PENDING`, `COMPLETED`, `ALL` |
| `ticker` | Query | `string` | N | - | 종목 코드 필터 |
| `yearMonth` | Query | `string` | N | - | `YYYY-MM` 형식 월 필터 |

**요청 Body**  
없음

**성공응답 예시**

```json
{
  "isSuccess": true,
  "code": "GLOBAL-200",
  "message": "요청 응답에 성공했습니다.",
  "result": {
    "pending": {
      "content": [
        {
          "orderId": 5001,
          "ticker": "005930",
          "companyName": "삼성전자",
          "orderType": "BUY",
          "status": "OPEN",
          "totalPrice": 700000,
          "unexecutedQuantity": 10,
          "createdAt": "2026-04-02T09:01:00"
        }
      ],
      "page": 0,
      "size": 20,
      "totalElements": 1,
      "totalPages": 1,
      "last": true
    },
    "completed": {
      "content": [
        {
          "historyId": 9001,
          "orderId": 4900,
          "ticker": "000660",
          "companyName": "SK하이닉스",
          "orderType": "SELL",
          "historyType": "EXECUTION",
          "price": 180000,
          "quantity": 3,
          "totalPrice": 540000,
          "createdAt": "2026-04-01T14:30:00"
        }
      ],
      "page": 0,
      "size": 20,
      "totalElements": 1,
      "totalPages": 1,
      "last": true
    }
  }
}
```

**실패응답 예시**

```json
{
  "isSuccess": false,
  "code": "ACC001",
  "message": "해당 유저의 계좌 정보를 찾을 수 없습니다.",
  "result": null
}
```

**필드 설명**

| 필드 | 타입 | 설명 |
| --- | --- | --- |
| `pending` | `object \| null` | 대기 주문 페이지 |
| `completed` | `object \| null` | 완료 이력 페이지 |
| `pending.content[].orderId` | `number` | 주문 ID |
| `pending.content[].totalPrice` | `number` | 미체결 수량 기준 총 주문 금액 |
| `pending.content[].unexecutedQuantity` | `number` | 미체결 수량 |
| `completed.content[].historyId` | `number` | 이력 ID |
| `completed.content[].historyType` | `EXECUTION \| CANCELLATION \| SYSTEM_CANCELLATION` | 이력 유형 |
| `completed.content[].price` | `number` | 체결가 또는 취소 기준가 |
| `completed.content[].quantity` | `number` | 체결/취소 수량 |

**비고**  
`yearMonth` 형식이 잘못되면 오류 없이 무시된다.

### 21. 대기 주문 상세 조회

**설명**  
주문 상세 정보를 조회한다.

**요청 URL**  
`GET /api/v1/core/orders/pending/{orderId}`

**요청 Header**  
`Authorization: Bearer {accessToken}`

**요청 Parameter**

| 이름 | 위치 | 타입 | 필수 | 설명 |
| --- | --- | --- | --- | --- |
| `orderId` | Path | `number` | Y | 주문 ID |

**요청 Body**  
없음

**성공응답 예시**

```json
{
  "isSuccess": true,
  "code": "GLOBAL-200",
  "message": "요청 응답에 성공했습니다.",
  "result": {
    "orderId": 5001,
    "companyName": "삼성전자",
    "ticker": "005930",
    "orderType": "BUY",
    "status": "OPEN",
    "priceType": "LIMIT",
    "pricePerShare": 70000,
    "orderQuantity": 10,
    "orderAmount": 700000,
    "orderCreatedAt": "2026-04-02T09:01:00"
  }
}
```

**실패응답 예시**

```json
{
  "isSuccess": false,
  "code": "ORD003",
  "message": "해당 주문을 찾을 수 없습니다.",
  "result": null
}
```

**필드 설명**

| 필드 | 타입 | 설명 |
| --- | --- | --- |
| `orderId` | `number` | 주문 ID |
| `companyName` | `string` | 종목명 |
| `ticker` | `string` | 종목 코드 |
| `orderType` | `BUY \| SELL` | 주문 구분 |
| `status` | `OPEN \| PARTIAL \| FILLED \| PENDING_CANCEL \| CANCELLED` | 주문 상태 |
| `priceType` | `LIMIT \| MARKET` | 가격 구분 |
| `pricePerShare` | `number` | 1주당 가격 |
| `orderQuantity` | `number` | 주문 수량 |
| `orderAmount` | `number` | 총 주문 금액 |
| `orderCreatedAt` | `string(date-time)` | 주문 생성 시각 |

**비고**  
경로명은 `pending`이지만 구현상 상태 검증 없이 임의 주문 ID를 조회한다.

### 22. 완료 이력 상세 조회

**설명**  
체결 또는 취소 이력 상세 정보를 조회한다.

**요청 URL**  
`GET /api/v1/core/orders/completed/{historyId}`

**요청 Header**  
`Authorization: Bearer {accessToken}`

**요청 Parameter**

| 이름 | 위치 | 타입 | 필수 | 설명 |
| --- | --- | --- | --- | --- |
| `historyId` | Path | `number` | Y | 주문 이력 ID |

**요청 Body**  
없음

**성공응답 예시**

```json
{
  "isSuccess": true,
  "code": "GLOBAL-200",
  "message": "요청 응답에 성공했습니다.",
  "result": {
    "historyId": 9001,
    "orderId": 4900,
    "companyName": "SK하이닉스",
    "ticker": "000660",
    "orderType": "SELL",
    "priceType": "LIMIT",
    "historyType": "EXECUTION",
    "pricePerShare": 180000,
    "quantity": 3,
    "totalAmount": 540000,
    "orderCreatedAt": "2026-04-01T14:00:00",
    "createdAt": "2026-04-01T14:30:00"
  }
}
```

**실패응답 예시**

```json
{
  "isSuccess": false,
  "code": "ORD004",
  "message": "해당 체결 내역을 찾을 수 없습니다.",
  "result": null
}
```

**필드 설명**

| 필드 | 타입 | 설명 |
| --- | --- | --- |
| `historyId` | `number` | 이력 ID |
| `orderId` | `number` | 원 주문 ID |
| `companyName` | `string` | 종목명 |
| `ticker` | `string` | 종목 코드 |
| `orderType` | `BUY \| SELL` | 주문 구분 |
| `priceType` | `LIMIT \| MARKET` | 가격 구분 |
| `historyType` | `EXECUTION \| CANCELLATION \| SYSTEM_CANCELLATION` | 이력 유형 |
| `pricePerShare` | `number` | 체결 또는 취소 기준 단가 |
| `quantity` | `number` | 수량 |
| `totalAmount` | `number` | 총 금액 |
| `orderCreatedAt` | `string(date-time)` | 원 주문 생성 시각 |
| `createdAt` | `string(date-time)` | 체결/취소 기록 시각 |

**비고**  
취소 이력도 동일 API로 조회한다.

## 주식 시세 API

### 23. 거래량 상위 종목 조회

**설명**  
거래량 기준 상위 종목 목록을 조회한다. 인증 없이 접근 가능하다.

**요청 URL**  
`GET /api/v1/market/stocks`

**요청 Header**  
없음

**요청 Parameter**

| 이름 | 위치 | 타입 | 필수 | 기본값 | 설명 |
| --- | --- | --- | --- | --- | --- |
| `limit` | Query | `number` | N | `100` | 조회 개수. 구현상 `1~100` |
| `rankType` | Query | `string` | N | `VOLUME` | 구현상 `VOLUME`만 지원 |

**요청 Body**  
없음

**성공응답 예시**

```json
{
  "isSuccess": true,
  "code": "GLOBAL-200",
  "message": "요청 응답에 성공했습니다.",
  "result": [
    {
      "ticker": "005930",
      "name": "삼성전자",
      "currentPrice": 72000,
      "changeRate": 1.25,
      "accVolume": 15000000
    }
  ]
}
```

**실패응답 예시**

```json
{
  "isSuccess": false,
  "code": "STOCK-400",
  "message": "limit은 1~100 사이의 정수여야 합니다.",
  "result": null
}
```

**필드 설명**

| 필드 | 타입 | 설명 |
| --- | --- | --- |
| `ticker` | `string` | 종목 코드 |
| `name` | `string` | 종목명 |
| `currentPrice` | `number` | 현재가 |
| `changeRate` | `number` | 등락률 |
| `accVolume` | `number` | 누적 거래량 |

**비고**  
외부 공개 경로는 Gateway 기준 `/api/v1/market/stocks`이다.

### 24. 종목 검색

**설명**  
종목명/코드 기반 자동완성 검색을 수행한다. 인증 없이 접근 가능하다.

**요청 URL**  
`GET /api/v1/market/stocks/search`

**요청 Header**  
없음

**요청 Parameter**

| 이름 | 위치 | 타입 | 필수 | 기본값 | 설명 |
| --- | --- | --- | --- | --- | --- |
| `q` | Query | `string` | Y | - | 검색어 |
| `limit` | Query | `number` | N | `10` | 최대 노출 개수. 구현상 `1~50` |

**요청 Body**  
없음

**성공응답 예시**

```json
{
  "isSuccess": true,
  "code": "GLOBAL-200",
  "message": "요청 응답에 성공했습니다.",
  "result": [
    {
      "ticker": "005930",
      "name": "삼성전자",
      "currentPrice": 72000,
      "changeRate": 1.25,
      "accVolume": 15000000
    }
  ]
}
```

**실패응답 예시**

```json
{
  "isSuccess": false,
  "code": "STOCK-400",
  "message": "검색어(q) 파라미터가 필요합니다.",
  "result": null
}
```

**필드 설명**

| 구분 | 필드 | 타입 | 필수 | 설명 |
| --- | --- | --- | --- | --- |
| Query | `q` | `string` | Y | 검색어 |
| Query | `limit` | `number` | N | 최대 노출 개수 |
| Result | `result[]` | `array` | Y | 종목 목록 |

**비고**  
검색 결과가 없어도 오류가 아니라 빈 배열을 반환한다.

### 25. 종목 시세 스냅샷 조회

**설명**  
특정 종목의 실시간 시세 스냅샷을 조회한다. 인증 없이 접근 가능하다.

**요청 URL**  
`GET /api/v1/market/stocks/{ticker}`

**요청 Header**  
없음

**요청 Parameter**

| 이름 | 위치 | 타입 | 필수 | 설명 |
| --- | --- | --- | --- | --- |
| `ticker` | Path | `string` | Y | 종목 코드 |

**요청 Body**  
없음

**성공응답 예시**

```json
{
  "isSuccess": true,
  "code": "GLOBAL-200",
  "message": "요청 응답에 성공했습니다.",
  "result": {
    "ticker": "005930",
    "name": "삼성전자",
    "currentPrice": 72000,
    "changeRate": 1.25,
    "openPrice": 71000,
    "highPrice": 72500,
    "lowPrice": 70800,
    "tradeVolume": 15000,
    "accVolume": 15000000
  }
}
```

**실패응답 예시**

```json
{
  "isSuccess": false,
  "code": "STOCK-404",
  "message": "해당 종목의 TICK 스냅샷 데이터가 존재하지 않습니다.",
  "result": null
}
```

**필드 설명**

| 필드 | 타입 | 설명 |
| --- | --- | --- |
| `ticker` | `string` | 종목 코드 |
| `name` | `string` | 종목명 |
| `currentPrice` | `number` | 현재가 |
| `changeRate` | `number` | 등락률 |
| `openPrice` | `number` | 시가 |
| `highPrice` | `number` | 고가 |
| `lowPrice` | `number` | 저가 |
| `tradeVolume` | `number` | 체결량 |
| `accVolume` | `number` | 누적 거래량 |

**비고**  
이 REST 응답 필드명은 WebSocket `TICK` 메시지 필드명과 다르다.

### 26. 캔들 조회

**설명**  
특정 종목의 캔들 데이터를 조회한다. 인증 없이 접근 가능하다.

**요청 URL**  
`GET /api/v1/market/stocks/{ticker}/candles`

**요청 Header**  
없음

**요청 Parameter**

| 이름 | 위치 | 타입 | 필수 | 기본값 | 설명 |
| --- | --- | --- | --- | --- | --- |
| `ticker` | Path | `string` | Y | 종목 코드 |
| `interval` | Query | `string` | N | `D` | 구현상 `D`,`d`,`day`,`1d`,`1`,`1M`,`1m`,`min` 처리 |
| `limit` | Query | `number` | N | `50` | 구현상 1 이상 |
| `endTime` | Query | `string` | N | - | 과거 데이터 커서 |

**요청 Body**  
없음

**성공응답 예시**

```json
{
  "isSuccess": true,
  "code": "GLOBAL-200",
  "message": "요청 응답에 성공했습니다.",
  "result": [
    {
      "timestamp": "2026-04-02",
      "open": 71000,
      "high": 72500,
      "low": 70800,
      "close": 72000,
      "volume": 15000000
    }
  ]
}
```

**실패응답 예시**

```json
{
  "isSuccess": false,
  "code": "STOCK-400",
  "message": "limit은 1 이상의 정수여야 합니다.",
  "result": null
}
```

**필드 설명**

| 구분 | 필드 | 타입 | 필수 | 설명 |
| --- | --- | --- | --- | --- |
| Path | `ticker` | `string` | Y | 종목 코드 |
| Query | `interval` | `string` | N | 캔들 간격 |
| Query | `limit` | `number` | N | 조회 개수 |
| Query | `endTime` | `string` | N | 과거 시점 커서 |
| Result | `timestamp` | `string` | Y | 캔들 시각 또는 일자 |
| Result | `open` | `number` | Y | 시가 |
| Result | `high` | `number` | Y | 고가 |
| Result | `low` | `number` | Y | 저가 |
| Result | `close` | `number` | Y | 종가 |
| Result | `volume` | `number` | Y | 거래량 |

**비고**  
주석상 주/월봉이 언급되지만 구현상 일봉과 분봉만 의미 있게 처리된다.

### 27. 호가창 조회

**설명**  
특정 종목의 호가창 스냅샷을 조회한다. Gateway whitelist에 포함되지 않아 인증이 필요하다.

**요청 URL**  
`GET /api/v1/market/stocks/{ticker}/orderbook`

**요청 Header**  
`Authorization: Bearer {accessToken}`

**요청 Parameter**

| 이름 | 위치 | 타입 | 필수 | 설명 |
| --- | --- | --- | --- | --- |
| `ticker` | Path | `string` | Y | 종목 코드 |

**요청 Body**  
없음

**성공응답 예시**

```json
{
  "isSuccess": true,
  "code": "GLOBAL-200",
  "message": "요청 응답에 성공했습니다.",
  "result": {
    "ticker": "005930",
    "name": "삼성전자",
    "currentPrice": 72000,
    "changeRate": 1.25,
    "askPrice1": 72100,
    "askVolume1": 3200,
    "bidPrice1": 72000,
    "bidVolume1": 5100
  }
}
```

**실패응답 예시**

```http
HTTP/1.1 401 Unauthorized
```

**필드 설명**

| 필드 | 타입 | 설명 |
| --- | --- | --- |
| `ticker` | `string` | 종목 코드 |
| `name` | `string` | 종목명 |
| `currentPrice` | `number` | 현재가 |
| `changeRate` | `number` | 등락률 |
| `askPrice1` | `number` | 매도 1호가 |
| `askVolume1` | `number` | 매도 1호가 잔량 |
| `bidPrice1` | `number` | 매수 1호가 |
| `bidVolume1` | `number` | 매수 1호가 잔량 |

**비고**  
REST 호가 응답에는 `currentPrice`, `changeRate`가 포함되지만 WebSocket `ORDERBOOK` 메시지에는 포함되지 않는다.

## 실시간 시세 WebSocket API

### 28. WebSocket 연결

**설명**  
실시간 시세 수신을 위한 WebSocket 연결을 생성한다. 연결 자체는 비회원도 가능하다.

**요청 URL**  
`GET /ws/v1/stocks`

**요청 Header**  
없음

**요청 Parameter**

| 이름 | 위치 | 타입 | 필수 | 설명 |
| --- | --- | --- | --- | --- |
| `token` | Query | `string` | N | JWT. 인증 사용자 구독 시 사용 |

**요청 Body**  
없음

**성공응답 예시**

```text
101 Switching Protocols
```

**실패응답 예시**

```text
WebSocket upgrade failed
```

**필드 설명**

| 필드 | 타입 | 설명 |
| --- | --- | --- |
| `token` | `string` | JWT Access Token. Gateway가 검증 후 `X-USER-ID` 주입 |

**비고**  
브라우저 WebSocket API 제약 때문에 인증은 Query Parameter `token`으로 전달한다.

### 29. HOME_40 구독

**설명**  
거래량 상위 종목 목록을 실시간 스트림으로 구독한다. 비회원도 가능하다.

**요청 URL**  
`WebSocket /ws/v1/stocks`

**요청 Header**  
없음

**요청 Parameter**  
연결 단계의 `token` Query Parameter 사용 가능

**요청 Body**

```json
{
  "action": "SUBSCRIBE",
  "topic": "HOME_40"
}
```

**성공응답 예시**

```json
{
  "topic": "HOME_40",
  "data": [
    {
      "ticker": "005930",
      "name": "삼성전자",
      "currentPrice": 72000,
      "changeRate": 1.25,
      "accVolume": 15000000
    }
  ]
}
```

**실패응답 예시**  
별도 실패 메시지 정의 없음

**필드 설명**

| 구분 | 필드 | 타입 | 필수 | 설명 |
| --- | --- | --- | --- | --- |
| Client | `action` | `SUBSCRIBE \| UNSUBSCRIBE` | Y | 구독/해지 |
| Client | `topic` | `string` | Y | `HOME_40` |
| Server | `topic` | `string` | Y | `HOME_40` |
| Server | `data[]` | `array` | Y | 거래량 상위 종목 목록 |

**비고**  
서버는 약 0.5초 주기로 `HOME_40` 데이터를 브로드캐스트한다.

### 30. TICK 구독

**설명**  
특정 종목의 실시간 체결 정보를 구독한다. 비회원도 가능하다.

**요청 URL**  
`WebSocket /ws/v1/stocks`

**요청 Header**  
없음

**요청 Parameter**  
연결 단계의 `token` Query Parameter 사용 가능

**요청 Body**

```json
{
  "action": "SUBSCRIBE",
  "topic": "TICK",
  "ticker": "005930"
}
```

**성공응답 예시**

```json
{
  "topic": "TICK",
  "data": {
    "ticker": "005930",
    "name": "삼성전자",
    "price": 72000,
    "open": 71000,
    "high": 72500,
    "low": 70800,
    "change_rate": 1.25,
    "trade_vol": 15000,
    "acc_vol": 15000000
  }
}
```

**실패응답 예시**  
별도 실패 메시지 정의 없음

**필드 설명**

| 구분 | 필드 | 타입 | 필수 | 설명 |
| --- | --- | --- | --- | --- |
| Client | `action` | `SUBSCRIBE \| UNSUBSCRIBE` | Y | 구독/해지 |
| Client | `topic` | `string` | Y | `TICK` |
| Client | `ticker` | `string` | Y | 종목 코드 |
| Server | `data.price` | `number` | Y | 현재가 |
| Server | `data.open` | `number` | Y | 시가 |
| Server | `data.high` | `number` | Y | 고가 |
| Server | `data.low` | `number` | Y | 저가 |
| Server | `data.change_rate` | `number` | Y | 등락률 |
| Server | `data.trade_vol` | `number` | Y | 체결량 |
| Server | `data.acc_vol` | `number` | Y | 누적 거래량 |

**비고**  
REST 스냅샷 API와 달리 WebSocket `TICK` 메시지는 snake_case 기반 필드가 포함된다.

### 31. ORDERBOOK 구독

**설명**  
특정 종목의 실시간 호가 정보를 구독한다. 로그인 사용자만 가능하다.

**요청 URL**  
`WebSocket /ws/v1/stocks`

**요청 Header**  
없음

**요청 Parameter**

| 이름 | 위치 | 타입 | 필수 | 설명 |
| --- | --- | --- | --- | --- |
| `token` | Query | `string` | Y | JWT Access Token |

**요청 Body**

```json
{
  "action": "SUBSCRIBE",
  "topic": "ORDERBOOK",
  "ticker": "005930"
}
```

**성공응답 예시**

```json
{
  "topic": "ORDERBOOK",
  "data": {
    "ticker": "005930",
    "name": "삼성전자",
    "askPrice1": 72100,
    "askVolume1": 3200,
    "bidPrice1": 72000,
    "bidVolume1": 5100
  }
}
```

**실패응답 예시**

```json
{
  "topic": "ERROR",
  "data": "호가창은 로그인이 필요한 서비스입니다."
}
```

**필드 설명**

| 구분 | 필드 | 타입 | 필수 | 설명 |
| --- | --- | --- | --- | --- |
| Client | `action` | `SUBSCRIBE \| UNSUBSCRIBE` | Y | 구독/해지 |
| Client | `topic` | `string` | Y | `ORDERBOOK` |
| Client | `ticker` | `string` | Y | 종목 코드 |
| Server | `data.askPrice1` | `number` | Y | 매도 1호가 |
| Server | `data.askVolume1` | `number` | Y | 매도 1호가 잔량 |
| Server | `data.bidPrice1` | `number` | Y | 매수 1호가 |
| Server | `data.bidVolume1` | `number` | Y | 매수 1호가 잔량 |

**비고**  
연결은 비회원도 가능하지만 `ORDERBOOK` 구독은 인증된 소켓에서만 허용된다.

## 알림 API

### 32. 실시간 주문 알림 구독

**설명**  
SSE로 주문 체결/취소 관련 이벤트를 구독한다.

**요청 URL**  
`GET /api/v1/core/notifications/subscribe`

**요청 Header**  
없음

**요청 Parameter**

| 이름 | 위치 | 타입 | 필수 | 설명 |
| --- | --- | --- | --- | --- |
| `token` | Query | `string` | Y | JWT Access Token |

**요청 Body**  
없음

**성공응답 예시**

```text
event: connect
data: Connected to Real-time Notification Server
```

이후 주문 알림 이벤트:

```text
event: order_notification
data: {"eventType":"MATCHED","orderType":"BUY","ticker":"005930","stockName":"삼성전자","matchPrice":72000,"matchQuantity":10,"executedAt":"2026-04-02T09:02:00"}
```

**실패응답 예시**

```http
HTTP/1.1 401 Unauthorized
```

**필드 설명**

| 필드 | 타입 | 설명 |
| --- | --- | --- |
| `eventType` | `MATCHED \| CANCELLED \| ORDER_CANCEL \| CANCEL_REJECTED` | 이벤트 유형 |
| `orderType` | `BUY \| SELL` | 주문 구분 |
| `ticker` | `string` | 종목 코드 |
| `stockName` | `string` | 종목명 |
| `matchPrice` | `number` | 체결 또는 취소 기준 가격 |
| `matchQuantity` | `number` | 수량 |
| `executedAt` | `string(date-time)` | 이벤트 시각 |

**비고**  
브라우저 `EventSource` 제약 때문에 인증은 Query Parameter `token`으로 전달한다.
