# Tool Build 완료 후 DB 저장 누락 문제

## 1. 문제 상황

커스텀 Tool Build 요청 이후 Core Server에는 실제 툴 파일이 정상적으로 생성되었지만, API Server의 `tools` 테이블에는 해당 Tool row가 생성되지 않는 문제가 발생했다.

예상 흐름은 다음과 같았다.

1. Core Server가 Tool 파일 생성
2. Core Server가 Kafka `theseus.tool-build.event` completed 이벤트 발행
3. API Server가 completed 이벤트 소비
4. API Server가 `tools` 테이블에 Tool 메타데이터 저장

하지만 실제로는 파일만 생성되고 DB에는 저장되지 않아, 파일 시스템과 DB 상태가 불일치했다.

```text
Core Server
  -> /opt/theseus/custom_tools/{projectId}/xxx.py 파일 생성 성공
  -> Kafka theseus.tool-build.event completed 이벤트 발행

API Server
  -> completed 이벤트 소비
  -> 조건 검증
  -> tools 테이블 INSERT
```

실제 문제 상황은 다음과 같았다.

```text
파일 있음
DB tools row 없음
```

따라서 이 경우 원인은 Core Server의 파일 생성 실패가 아니라 API Server의 이벤트 처리 단계에서 먼저 의심해야 한다.

## 2. 원인 분석

Theseus의 Tool Build 구조에서는 Core Server와 API Server의 책임이 분리되어 있다.

- Core Server: 커스텀 Tool 파일 생성
- API Server: Kafka completed 이벤트 소비 후 DB `tools` row 생성

파일이 존재한다는 것은 Core Server의 파일 생성은 성공했다는 의미이며, DB에 row가 없다는 것은 API Server의 completed 이벤트 수신 또는 처리 단계에서 문제가 발생했을 가능성이 높다.

API Server가 Tool 정보를 저장하기 위해서는 다음 조건을 모두 만족해야 한다.

- `tool_plan_runs.run_id`가 이벤트의 `runId`와 일치해야 함
- `tool_plan_runs.request_type`이 `BUILD_TOOL`이어야 함
- 이벤트의 `projectId`, `chatSessionId`가 run 정보와 일치해야 함
- run 상태가 이미 `COMPLETED`, `FAILED`, `SKIPPED`가 아니어야 함
- `base_tool_plan_id`가 이벤트의 `toolPlanId`와 일치해야 함
- 해당 `tool_plans.status`가 `APPROVED` 상태여야 함
- 같은 project 내에 동일한 `file_name`이 없어야 함

위 조건 중 하나라도 불일치하면 API Server는 Tool 저장을 수행하지 않는다.

## 3. 주요 의심 지점

### 3-1. API Server의 completed 이벤트 처리 실패

API Server가 Kafka completed 이벤트를 수신했지만 처리 중 예외가 발생했을 수 있다.

예상 로그:

```text
ToolBuild event handling failed
ToolBuild completed event skipped
```

### 3-2. Core와 API 간 이벤트 payload 불일치

Core Server가 발행한 이벤트의 `projectId`, `chatSessionId`, `toolPlanId`, `runId`가 API Server의 `tool_plan_runs` 데이터와 일치하지 않으면 API Server는 DB 저장을 수행하지 않는다.

이 경우 파일은 `/opt/theseus/custom_tools/{projectId}`에 생성되었지만, API Server는 해당 이벤트를 유효한 Tool Build 결과로 인정하지 않아 `tools` INSERT를 건너뛴다.

## 4. 해결 방향

DB row를 수동으로 INSERT하는 것은 마지막 수단으로 두고, 먼저 API Server의 `ToolBuildEventService.handleCompleted()` 흐름에서 어떤 조건 때문에 `toolRepository.save()`까지 도달하지 못했는지 확인해야 한다.

필요한 개선 방향은 다음과 같다.

- completed 이벤트 처리 실패 로그를 더 명확히 남기기
- skip 조건별 사유를 구체적으로 로깅하기
- `runId`, `projectId`, `chatSessionId`, `toolPlanId` 불일치 시 어떤 값이 달랐는지 출력하기
- Tool 파일 생성 성공 후 DB 저장 실패 시 보상 처리 또는 재처리 전략 검토하기

## 5. 정리

이 문제는 단순히 "파일 생성 성공"만으로 Tool Build 전체 성공을 판단할 수 없다는 점을 보여준다.

비동기 이벤트 기반 구조에서는 파일 시스템, Kafka 이벤트, DB 상태가 모두 일치해야 최종 성공으로 볼 수 있다.
