# ToolPlan Integration Test

## Scope

ToolPlan 기반 Tool 생성 흐름을 FE, API Server, Kafka, Core Server, Redis, SSE, DB 기준으로 검증한다.

검증 대상 흐름:

```text
FE
-> API Server
-> theseus.tool-plan.request
-> Core Server
-> theseus.tool-plan.event
-> API Server
-> Redis / SSE
-> FE
```

승인 이후 Tool build 흐름:

```text
FE
-> API Server
-> theseus.tool-build.request
-> Core Server
-> theseus.tool-build.event
-> API Server
-> Redis / SSE
-> FE
```

## Required Topics

```text
theseus.tool-plan.request
theseus.tool-plan.event
theseus.tool-build.request
theseus.tool-build.event
```

확인 명령:

```bash
docker exec -it theseus-local-kafka kafka-topics \
  --bootstrap-server theseus-local-kafka:29092 \
  --list
```

## Local Runtime

인프라만 Docker로 실행하고 API Server는 IDE에서 실행한다.

```bash
docker compose \
  -f infra/docker/local/docker-compose.infra.yml \
  up -d
```

API Server 환경:

```text
SPRING_DATASOURCE_URL=jdbc:mysql://localhost:13306/theseus
SPRING_KAFKA_BOOTSTRAP_SERVERS=localhost:19092
SPRING_DATA_REDIS_HOST=localhost
SPRING_DATA_REDIS_PORT=16379
```

전체 Docker 통합 검증:

```bash
docker compose \
  -f infra/docker/local/docker-compose.infra.yml \
  -f infra/docker/local/docker-compose.api.yml \
  -f infra/docker/local/docker-compose.core.yml \
  up -d
```

Core Server가 Kafka worker로 동작하려면 다음 값이 활성화되어야 한다.

```text
CORE_KAFKA_CONSUMER_ENABLED=true
CORE_KAFKA_BOOTSTRAP_SERVERS=theseus-local-kafka:29092
```

## Automated Regression

API Server:

```bash
cd backend/theseus-api-server
./gradlew.bat test --tests "*ToolPlan*" --tests "*ToolBuild*" --tests "*ToolApproval*"
```

Core Server:

```bash
cd backend/theseus-core-server
python -m pytest -q tests/test_worker_contracts.py tests/test_tool_plan_worker.py tests/test_tool_build_processor.py
```

Frontend:

```bash
cd frontend
npm run build
```

검증 결과:

| Area | Command | Result |
| --- | --- | --- |
| API Server | `./gradlew.bat test --tests "*ToolPlan*" --tests "*ToolBuild*" --tests "*ToolApproval*"` | PASS |
| Core Server | `python -m pytest -q tests/test_worker_contracts.py tests/test_tool_plan_worker.py tests/test_tool_build_processor.py` | PASS |
| Frontend | `npm run build` | PASS |

## Common Variables

```text
projectId={projectId}
sessionId={sessionId}
accessToken={accessToken}
runId={runId}
toolPlanId={toolPlanId}
approvalId={approvalId}
```

SSE 구독:

```bash
curl -N \
  -H "Authorization: Bearer {accessToken}" \
  http://localhost:8080/api/v1/projects/{projectId}/sessions/{sessionId}/tool-plan-runs/{runId}/events
```

Run 상태 조회:

```bash
curl \
  -H "Authorization: Bearer {accessToken}" \
  http://localhost:8080/api/v1/projects/{projectId}/sessions/{sessionId}/tool-plan-runs/{runId}/state
```

Redis 상태 조회:

```bash
docker exec theseus-local-redis redis-cli GET tool:plan:{runId}:state
```

## Scenario 1. Invalid PLAN Input

요청:

```http
POST /api/v1/projects/{projectId}/sessions/{sessionId}/tool-plans/generate
```

```json
{
  "mode": "PLAN",
  "prompt": "안녕"
}
```

기대 흐름:

```text
API Server
-> ToolPlanRun REQUESTED 생성
-> USER / TOOL_PLAN_REQUEST 메시지 저장
-> Kafka TOOL_PLAN_REQUESTED 발행
-> Core TOOL_PLAN_SKIPPED 발행
-> API Server ToolPlanRun SKIPPED 처리
-> ASSISTANT / CHAT 안내 메시지 저장
-> ToolPlanGroup 미생성
-> ToolPlan 미생성
-> Tool 미생성
-> SSE skipped 전송
```

확인:

```sql
select status from tool_plan_runs where run_id = '{runId}';
select count(*) from tool_plan_groups where chat_session_id = {sessionId};
select count(*) from tool_plans where chat_session_id = {sessionId};
select count(*) from tools where chat_session_id = {sessionId};
```

성공 기준:

```text
tool_plan_runs.status = SKIPPED
tool_plan_groups 증가 없음
tool_plans 증가 없음
tools 증가 없음
FE에 안내 메시지 표시
```

## Scenario 2. PLAN Generation Completed

요청:

```http
POST /api/v1/projects/{projectId}/sessions/{sessionId}/tool-plans/generate
```

```json
{
  "mode": "PLAN",
  "prompt": "최근 장애 로그를 분석하고 복구 가이드를 만드는 Tool 명세를 작성해줘."
}
```

기대 흐름:

```text
API Server
-> ToolPlanRun REQUESTED 생성
-> Kafka TOOL_PLAN_REQUESTED 발행
-> Core TOOL_PLAN_COMPLETED 발행
-> API Server ToolPlanGroup 생성
-> API Server ToolPlan v1 REVIEW 생성
-> ASSISTANT / TOOL_PLAN_RESPONSE 메시지 저장
-> Redis completed 저장
-> SSE completed 전송
-> FE PLAN 카드 표시
```

성공 기준:

```text
tool_plan_runs.status = COMPLETED
tool_plan_groups.status = REVIEW
tool_plans.status = REVIEW
tool_plans.plan_version = 1
tools 증가 없음
FE PLAN 카드 표시
```

## Scenario 3. PLAN Regeneration

요청:

```http
PATCH /api/v1/projects/{projectId}/sessions/{sessionId}/tool-plans/{toolPlanId}/regenerate
```

```json
{
  "mode": "PLAN",
  "basePlanVersion": 1,
  "feedbackItems": [
    {
      "blockId": "analysis-summary",
      "comment": "장애 원인을 더 구체적으로 작성해줘."
    }
  ]
}
```

기대 흐름:

```text
API Server
-> base ToolPlan REVIEW/REJECTED 검증
-> basePlanVersion 검증
-> ToolPlanRun REQUESTED 생성
-> USER / TOOL_FEEDBACK 메시지 저장
-> Kafka TOOL_PLAN_REGENERATION_REQUESTED 발행
-> Core basePlan, feedbackItems, history 기반 전체 PLAN 재생성
-> Core TOOL_PLAN_COMPLETED 발행
-> API Server 같은 ToolPlanGroup 아래 ToolPlan v2 REVIEW 생성
-> 기존 latest plan SUPERSEDED
-> FE v2 PLAN 카드 표시
```

성공 기준:

```text
새 ToolPlan이 같은 plan_group_id를 가진다.
새 ToolPlan.plan_version = basePlanVersion + 1
기존 REVIEW/REJECTED latest plan은 SUPERSEDED가 된다.
같은 의미의 블록은 blockId가 유지된다.
tools 증가 없음
```

## Scenario 4. Approval And Build

승인 요청:

```http
POST /api/v1/projects/{projectId}/tool-plans/{toolPlanId}/approval-requests
```

승인 처리:

```http
PATCH /api/v1/projects/{projectId}/tool-plan-approvals/{approvalId}/approve
```

기대 흐름:

```text
API Server
-> ToolPlan PENDING
-> ToolPlanGroup PENDING
-> 관리자 승인
-> ToolPlan APPROVED
-> ToolPlanGroup APPROVED
-> BUILD_TOOL ToolPlanRun REQUESTED 생성
-> Kafka TOOL_BUILD_REQUESTED 발행
-> Core TOOL_BUILD_COMPLETED 발행
-> API Server tools row 생성
-> ToolPlanGroup BUILT
-> ToolPlanGroup.created_tool_id 설정
-> Redis completed 저장
-> SSE completed 전송
-> FE Tool 목록 반영
```

성공 기준:

```text
승인 완료만으로 tools row가 생성되지 않는다.
TOOL_BUILD_COMPLETED 이후 tools row가 생성된다.
tools.source_tool_plan_id = 승인된 toolPlanId
tool_plan_groups.created_tool_id = 생성된 toolId
Tool 목록에는 build 완료된 Tool만 표시된다.
```

## Scenario 5. Failure And Idempotency

중복 completed:

```text
동일 runId, 동일 terminal event를 2회 발행한다.
```

성공 기준:

```text
ToolPlan 중복 생성 없음
Tool 중복 생성 없음
ASSISTANT 메시지 중복 저장 없음
ToolPlanRun terminal 상태 유지
```

Kafka 발행 실패:

```text
API Server Kafka 발행 실패를 유도한다.
```

성공 기준:

```text
ToolPlanRun.status = FAILED
errorCode/errorMessage 기록
사용자 메시지는 유지
ToolPlan/Tool은 생성되지 않음
```

Core worker 장애:

```text
Core 처리 중 worker를 중단한 뒤 재시작한다.
```

성공 기준:

```text
run lease가 남아 있으면 다른 worker가 중복 처리하지 않는다.
lease 만료 후 checkpoint 기준 재개 가능
pending outbox event 재발행 가능
```

## FE Verification

```text
ASK 모드에서는 ToolPlan 생성 API를 호출하지 않는다.
PLAN 모드에서만 /tool-plans/generate를 호출한다.
PLAN 요청 응답의 sseUrl로 SSE를 연결한다.
completed 이후 ToolPlan 상세 조회로 PLAN 카드를 표시한다.
skipped 이후 일반 assistant 안내 메시지를 표시한다.
regenerate 이후 새 ToolPlan 카드로 교체한다.
승인 전 Tool 목록은 증가하지 않는다.
build completed 이후 Tool 목록이 증가한다.
새로고침 후 /tool-plan-runs/{runId}/state로 진행 상태를 복구한다.
```

## Completion Criteria

```text
무효 PLAN 요청에서 Tool/ToolPlan이 생성되지 않는다.
승인 전 Tool 목록이 늘어나지 않는다.
build 완료 후에만 Tool 목록이 늘어난다.
채팅 메시지와 PLAN 카드가 올바르게 복구된다.
장애와 중복 이벤트가 데이터 불일치를 만들지 않는다.
```
