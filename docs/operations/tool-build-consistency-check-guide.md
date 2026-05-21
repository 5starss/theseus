# Tool Build 파일-DB 정합성 점검 가이드

## 1. 목적

이 문서는 커스텀 Tool Build 이후 Core Server에는 파일이 생성되었지만 API Server의 `tools` 테이블에는 row가 저장되지 않는 상황을 점검하기 위한 절차를 정리한다.

## 2. 점검 기준

Tool Build 완료 상태는 다음 세 가지가 함께 확인되어야 한다.

- Core Server의 Tool 파일 생성
- Core Server의 Kafka completed 이벤트 발행
- API Server의 completed 이벤트 소비 및 `tools` row 저장

하나라도 누락되면 파일 시스템과 DB 상태가 불일치할 수 있다.

## 3. Core Server 파일 확인

먼저 Core Server가 생성한 Tool 메타데이터 파일을 확인한다.

```bash
cat /opt/theseus/custom_tools/4/cpu_resource_monitor_tool.meta.json
```

여기서 다음 값을 확인한다.

- `projectId`
- `chatSessionId`
- `planId`
- `fileName`
- `moduleName`

## 4. API Server 로그 확인

API Server 로그에서 completed 이벤트 처리 여부를 확인한다.

```bash
docker logs --tail 500 theseus-prod-api-server | grep -i -E "ToolBuild|tool build|cpu_resource|completed event|event handling failed|skipped|duplicate"
```

확인할 로그:

- completed 이벤트 수신 여부
- 이벤트 처리 실패 여부
- skip 처리 여부
- duplicate file name 여부
- `toolRepository.save()` 전후 로그

## 5. Core Server 로그 확인

Core Server 로그에서는 파일 생성 및 Kafka 이벤트 발행 여부를 확인한다.

```bash
docker logs --tail 500 theseus-prod-core-server | grep -i -E "cpu_resource|tool build|completed|publish|kafka"
```

확인할 로그:

- Tool 파일 생성 성공 여부
- `.meta.json` 생성 여부
- `theseus.tool-build.event` completed 이벤트 발행 여부
- Kafka publish 실패 여부

## 6. DB 확인

### 6-1. tools 테이블 확인

```sql
SELECT *
FROM tools
WHERE project_id = 4
  AND file_name = 'cpu_resource_monitor_tool.py';
```

### 6-2. tool_plan_runs 확인

```sql
SELECT
  id,
  run_id,
  project_id,
  chat_session_id,
  request_type,
  status,
  base_tool_plan_id,
  result_tool_plan_id,
  plan_group_id,
  error_code,
  error_message,
  last_event_type,
  last_event_sequence,
  requested_at,
  completed_at
FROM tool_plan_runs
WHERE project_id = 4
ORDER BY id DESC
LIMIT 20;
```

### 6-3. tool_plans 확인

```sql
SELECT
  id,
  plan_group_id,
  project_id,
  chat_session_id,
  status,
  mode,
  created_by_project_member_id,
  created_at,
  updated_at
FROM tool_plans
WHERE id = <planId>;
```

## 7. 판별 방법

### 파일은 있고 tools row가 없는 경우

Core Server의 파일 생성은 성공했지만 API Server의 completed 이벤트 처리 또는 DB 저장 조건 검증에 실패했을 가능성이 높다.

우선순위:

1. API Server completed 이벤트 처리 로그 확인
2. `tool_plan_runs.run_id`와 이벤트 `runId` 일치 여부 확인
3. `projectId`, `chatSessionId`, `toolPlanId` 일치 여부 확인
4. `tool_plans.status = APPROVED` 여부 확인
5. 동일 project 내 `file_name` 중복 여부 확인

### Kafka publish 로그가 없는 경우

Core Server가 파일은 만들었지만 completed 이벤트를 발행하지 못했을 수 있다.

이 경우 Core Server의 Kafka producer 설정, broker 연결, publish 예외 로그를 먼저 확인한다.

### API Server에서 duplicate 로그가 있는 경우

같은 project 내 동일한 `file_name`이 이미 존재해 저장이 skip되었을 가능성이 있다.

## 8. 회고

커스텀 Tool Build 과정에서 Core Server에는 실제 툴 파일이 생성되었지만, API Server의 `tools` 테이블에는 row가 저장되지 않는 문제가 발생했다.

원인은 Core Server가 파일 생성을 담당하고, API Server가 Kafka completed 이벤트를 소비해 DB 저장을 수행하는 비동기 구조였기 때문이다.

즉 파일 생성은 성공했지만, API Server가 completed 이벤트를 수신하지 못했거나 이벤트 payload와 `tool_plan_runs`, `tool_plans`의 상태 조건이 일치하지 않아 DB 저장이 skip된 상황이었다.

이를 해결하기 위해 Core의 meta 파일, API/Core 로그, `tool_plan_runs`, `tool_plans`, `tools` 테이블을 기준으로 이벤트 흐름을 역추적했고, completed 이벤트 처리 조건과 skip 원인을 검증했다.

이 경험을 통해 비동기 이벤트 기반 구조에서는 단순 성공 여부뿐 아니라 파일 시스템, Kafka 이벤트, DB 상태 간 정합성을 함께 검증해야 한다는 점을 확인했다.
