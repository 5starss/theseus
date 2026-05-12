# LLM Agent / 백엔드 / DB 분리 관점 분석

---

## 현재 역할 분담

```
Java API Server
  - REST 요청 수신
  - DB 직접 write (Tool, ToolDraft, ChatMessage)
  - Kafka produce / consume
  - Redis 캐시 + SSE 전송

theseus_engine (Core)
  - LLM 호출 + Tool 실행
  - StreamEvent yield
  - DB 접근 없음 ✅

DB Layer
  - MySQL: 영속 데이터
  - Redis: 캐시 / SSE 브로커
```

Core가 DB에 직접 접근하지 않는 구조는 올바르다.

---

## 분리가 무너지는 부분

### 1. 백엔드가 LLM 도메인 로직을 알고 있음

Java 백엔드가 Kafka payload를 직접 조립한다.

```java
KafkaPayload.builder()
    .history(conversationHistory)   // LLM 컨텍스트
    .feedbackItems(feedbackItems)   // LLM 프롬프트 재료
    .baseDraft(previousDraft)       // LLM 참고 문서
    .build();
```

Core의 프롬프트 전략이 바뀌면 Java 코드도 수정해야 한다.

### 2. ToolDraft 상태 머신이 백엔드에 분산

상태 전이 로직이 API Server 곳곳에 흩어져 있다.
`FAILED` 전이는 명세에서 아예 누락되어 있다.

**권장:** ToolDraft 상태 머신을 단일 도메인 서비스로 분리.

### 3. Core 출력 포맷 변경이 Java 파싱 코드 변경을 요구

`rawMarkdown`, `structuredPlanJson`, `draftSnapshot` 구조가 바뀌면
Java 파싱 코드도 함께 바뀐다.

### 4. Redis 역할 혼재

캐시인지 pub/sub 브로커인지 명세에서 불명확하다.
역할이 섞이면 "어느 쪽이 source of truth인가"에 대한 답이 없어진다.

### 5. 스트리밍 중간 결과 비내구성

스트리밍 도중 서버 재시작 시 진행 중인 생성 결과가 완전히 유실된다.
재연결한 클라이언트는 이전 스트림을 복구할 수 없다.

---

## 핵심 권장사항

1. ToolDraft 상태 머신을 단일 도메인 서비스로 분리
2. Kafka payload 조립을 Core 전용 DTO로 추상화 (백엔드는 "무엇"만, Core가 "어떻게" 결정)
3. Redis 역할을 캐시 또는 브로커 하나로 명확히 지정
4. 스트리밍 중간 결과 임시 저장소 또는 재연결 replay 메커니즘 추가
5. APPROVED → 실행 흐름 명세 보완

---

## theseus_engine 범위에서의 결론

Core는 DB 접근 없이 순수 실행 레이어로 유지된다.
Java 팀이 Kafka payload 조립과 상태 관리를 담당한다.
Core에서 해야 할 것은 **StreamEvent 포맷을 안정적으로 유지**하고
**에러 타입을 명확히 분류**하는 것이다 (이미 적용됨).

---

## Hybrid 배포에서의 분리 구조

에이전트를 사용자 PC에서 실행하는 Hybrid 방식에서는 분리 구조가 달라진다.

```
사용자 PC
  theseus_engine (Core)
    - LLM 호출
    - 로컬 파일 Tool 실행
    - StreamEvent yield

  TheseusProjectClient (theseus_engine/client/)
    - 백엔드에서 프로젝트 설정 fetch (read-only)
    - 이력 / 과금 데이터 push (write)
    - THESEUS_SERVER_URL 미설정 시 no-op

Java Spring Boot 백엔드
  - 인증 / 프로젝트 설정 API
  - 이력 저장 (DB)
  - 과금 집계
  - DB에 직접 write ✅ (Core는 DB 접근 안 함)
```

이 방식에서 "분리가 무너지는 부분"의 대부분이 해소된다:
- Kafka payload 조립 불필요 (Core가 직접 로컬 실행)
- ToolDraft 상태 머신 분산 문제 없음 (백엔드에서 완전 관리)
- Redis 역할 혼재 없음 (Core가 Redis에 접근 안 함)
- 스트리밍 비내구성 완화 (로컬 실행이므로 서버 재시작 무관)
