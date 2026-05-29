# ToolPlan Kafka 플로우의 대화 이력 누락 문제

## 1. 문제 상황

일반 채팅 플로우에서는 이전 대화 이력이 LLM 입력에 포함되지만, Tool 생성 및 재생성 Kafka 플로우에서는 이전 대화 맥락이 반영되지 않는 문제가 있었다.

사용자는 같은 채팅 세션 안에서 다음과 같이 문맥 의존 요청을 할 수 있다.

- "방금 말한 조건도 포함해서 다시 만들어줘"
- "이전 응답에서 보안 부분만 강화해줘"
- "앞에서 말한 서버 환경 기준으로 검증 툴을 다시 설계해줘"

하지만 ToolPlan 생성 결과는 이전 대화 내용을 충분히 반영하지 못했고, 실질적으로 단일 요청 기반 생성처럼 동작했다.

## 2. 원인 분석

일반 채팅 플로우와 달리 Tool 생성 Kafka 플로우는 `chatSessionId`를 포함하고 있음에도, Core Server가 해당 세션의 이전 대화 이력을 조회하지 않았다.

즉, Kafka 메시지는 도착했지만 LLM 입력에는 현재 요청 정보만 포함되었고, 이전 사용자 발화나 AI 응답 맥락은 반영되지 않았다.

이로 인해 Tool 생성/재생성 플로우가 실질적으로는 멀티턴 채팅이 아닌 단일 요청 기반 생성 구조로 동작했다.

## 3. 해결 방향

Kafka payload에 전체 history를 포함하는 방식도 가능하지만, payload 크기 증가와 API/Core 간 책임 분리 측면에서 적합하지 않다고 판단했다.

따라서 Core Server가 Kafka 메시지를 consume하는 시점에 `chatSessionId`를 기준으로 API Server의 history 조회 API를 호출하고, 조회된 대화 이력을 LLM 입력의 `history`에 포함하는 방식으로 개선했다.

## 4. 개선 후 구조

개선 후 Tool 생성/재생성 흐름은 다음과 같다.

1. Frontend가 Tool 생성 또는 재생성 요청을 API Server로 전달
2. API Server가 요청 정보를 저장하고 Kafka 메시지를 발행
3. Core Server가 Kafka 메시지를 consume
4. Core Server가 `chatSessionId`를 기준으로 API Server에서 최근 대화 이력을 조회
5. 조회된 history를 압축 또는 정리한 뒤 LLM 입력에 포함
6. LLM은 이전 대화 맥락을 반영하여 ToolPlan 또는 재생성 결과를 생성
7. Core Server는 결과 이벤트를 Kafka로 발행
8. API Server는 결과를 Redis/SSE를 통해 Frontend에 전달

## 5. 결과

Tool 생성/재생성 Kafka 플로우에서도 이전 대화 맥락을 반영할 수 있게 되었고, 사용자는 문맥 의존 요청을 안정적으로 사용할 수 있게 되었다.

이를 통해 Tool 생성 플로우가 단순 단발성 생성 구조에서 `chatSessionId` 기반 멀티턴 AI 에이전트 구조로 개선되었다.
