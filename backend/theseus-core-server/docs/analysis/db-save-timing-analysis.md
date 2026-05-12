# DB 저장 시점 분석

> 분석 대상: Java 백엔드 Tool 생성/PLAN 재설계 명세의 DB 저장 흐름

---

## 명세의 저장 흐름

```
1. API Server: Tool + ToolDraft(GENERATING) + ToolGenerationRun + UserMessage DB 저장
2. API Server: Kafka publish (Core로 작업 요청)
3. Core: LLM 실행 → Kafka completed 발행
4. API Server: completed 수신 → ToolDraft=REVIEW + AssistantMessage 저장 → Redis → SSE
```

---

## 잘 설계된 부분

**Kafka 발행 전 DB 선저장 원칙**은 올바르다.
Kafka 실패 시에도 DB에 기록이 남아 재시도·모니터링이 가능하다.

---

## 문제점

### 1. Tool 행 생성 시점 모순

- 섹션 5: "최종 생성 완료 후 Tool 행 INSERT"
- 섹션 6.1 Step 5: Tool 생성 후 Kafka 발행

`tool_draft.tool_id` FK 제약 때문에 Tool이 Kafka 발행 전에 존재해야 한다.
→ 섹션 5 설명이 잘못된 것으로 보임. **명세 수정 필요**.

### 2. Kafka 발행 실패 시 보상 트랜잭션 없음

```
DB: ToolDraft=GENERATING 저장 ✅
Kafka publish 실패 ❌
→ ToolDraft가 GENERATING으로 영구 고착
```

**권장:** Outbox 패턴 또는 발행 실패 시 즉시 FAILED 처리.

### 3. Redis ↔ DB 저장 순서 미정의

DB 업데이트 전 Redis 쓰기 시 클라이언트가 COMPLETED를 받았는데
DB 조회 시 GENERATING이 반환될 수 있다.

**권장:** DB 커밋 완료 후 Redis 쓰기 순서 명시.

### 4. Kafka at-least-once → 중복 completed

같은 completed 이벤트 2회 컨슈밍 시 AssistantMessage 2회 INSERT 가능.

**권장:** `toolDraftId` 기준 idempotency key + DB unique constraint.

### 5. current_draft_id + SUPERSEDED 트랜잭션 경계

```sql
UPDATE tools SET current_draft_id = NEW_DRAFT_ID;
UPDATE tool_drafts SET status = 'SUPERSEDED' WHERE id = OLD_DRAFT_ID;
```

이 두 쿼리가 단일 트랜잭션이어야 한다는 명시 없음.

### 6. Assistant 메시지 유실 가능성

completed consumer 처리 실패 시 AssistantMessage가 영영 저장 안 됨.
UserMessage만 있고 응답이 없는 불완전한 대화 이력이 생긴다.

**권장:** completed consumer에 재시도 + DLQ 구성.

---

## 요약 권장사항

| 문제 | 권장 해결책 |
|------|------------|
| Tool 생성 시점 모순 | 명세 섹션 5 수정 |
| Kafka 발행 실패 | Outbox 패턴 또는 즉시 FAILED 처리 |
| Redis/DB 순서 | DB 커밋 후 Redis 쓰기 명시 |
| 중복 이벤트 | toolDraftId unique constraint |
| 트랜잭션 경계 | current_draft_id + SUPERSEDED 단일 트랜잭션 |
| Assistant 메시지 유실 | DLQ + 재시도 |
