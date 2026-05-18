# Theseus AI Work Roadmap

작성일: 2026-04-29

## 목적

이 문서는 [README.md](/mnt/c/DEV/S14P31A308/backend/theseus-core-server/README.md)를 기준으로, `theseus-core-server`에서 AI 파트가 앞으로 해야 할 작업을 현재 구현 상태에 맞춰 다시 정리한 로드맵이다.

정리 기준은 두 가지다.

- README가 원래 목표로 정의한 AI 기능
- 현재까지 실제로 구현된 서버 기반

현재 기준으로 보면, 스트리밍 엔진 연결, 과금 outbox, Docker 샌드박스, 샌드박스 서비스 진입점까지는 기반 공사가 끝났다. 이제 AI 파트의 핵심은 “메타-툴링과 Plan 파이프라인을 서버형 구조로 완성하고, 생성 코드 실행을 샌드박스로 강제 연결하는 것”이다.

---

## 1. 현재 AI 파트 상태 요약

### 이미 확보된 기반

- `src/routes/stream.py`
  - single-turn Theseus 엔진 스트리밍 경로 확보
- `src/builder/engine.py`
  - 서버용 QueryEngine 조립 계층 확보
- RBAC 기반 read-only tool allowlist 경로 확보
- 과금 outbox + scheduler 기반 확보
- Docker 기반 샌드박스 실행기 확보
- `/api/v1/sandbox/execute` 서비스 레벨 진입점 확보

### 아직 비어 있는 핵심 AI 기능

- Plan 모드 서버형 이관
- Structured Planner 서버 통합
- 메타-툴링(`create_tool`) 서버 이관
- 생성 코드 승인/검증 파이프라인
- 생성 코드 실행 경로의 샌드박스 강제화
- KB 검색 도구의 실제 에이전트 도구 편입
- LangSmith 기반 AI 실행 관측성 강화

---

## 2. AI 파트 우선순위

다음 순서로 가는 것이 가장 합리적이다.

1. Plan 모드 서버 이관
2. `ToolCreatorTool` 서버 이관
3. 생성 코드 실행을 샌드박스로 강제 연결
4. Validator 4종 정리 및 서버 편입
5. KB/RAG 도구를 실제 에이전트 경로에 연결
6. LangSmith 관측성 강화
7. 멀티턴 세션/상태 고도화

---

## 3. 세부 작업 목록

### 3.1 Plan 모드 서버 이관

README의 메타-툴링 목표는 단순 코드 생성이 아니라 `Planning -> Review -> Approved` 흐름이다. 현재 `theseus_engine`에는 관련 상태 머신과 planner가 있지만, `src` 서버 쪽에는 아직 없다.

해야 할 일:

- `theseus_engine/state.py`의 Plan 관련 상태를 `src` 구조로 이관
- `theseus_engine/structured_planner.py`를 `src/builder/` 또는 `src/agent/` 계층으로 이관
- Plan draft 생성 API 또는 스트리밍 이벤트 설계
- Review 전까지 read-only 상태 보장
- Approve/Edit/Abort 흐름을 서버 상태 전이로 정리

완료 기준:

- 클라이언트가 structured plan을 생성, 수정, 승인할 수 있음
- 승인 전에는 코드 실행이 일어나지 않음

### 3.2 ToolCreatorTool 서버 이관

README의 핵심 차별점 중 하나가 자연어 기반 툴 생성이다. 현재는 `theseus_engine/tool_factory.py`에 구현이 집중되어 있고, `src` 서버형 구조에는 아직 정식 편입되지 않았다.

해야 할 일:

- `ToolCreatorTool`를 서버 구조로 분리 이관
- `ToolValidator`와 함께 `src` 계층으로 편입
- 툴 생성 요청과 결과 저장 구조 정의
- 프로젝트 단위 메타데이터 관리 구조 정리

완료 기준:

- 서버 경로에서 메타-툴 생성 요청을 받아 검증/저장 가능
- 런타임 레지스트리 반영 정책이 명확히 정리됨

### 3.3 생성 코드 실행 경로 샌드박스 강제화

현재 샌드박스 실행기 자체는 구현되어 있지만, `create_tool` 산출물이 이 경로를 반드시 타도록 강제하는 연결은 아직 없다. 이 작업이 완료되어야 README의 “프로덕션에서 툴은 격리 실행” 요구를 만족한다.

해야 할 일:

- 코드 실행 관련 서버/도구 경로를 `DockerExecutor`로 브릿지
- 생성 코드가 호스트 프로세스에서 직접 import/실행되지 않도록 차단
- 샌드박스 입력 계약과 메타-툴 산출물 계약을 일치시킴
- 샌드박스 실패/timeout/보안 에러를 LLM 피드백 루프로 전달

완료 기준:

- 생성 코드 실행은 항상 샌드박스 경유
- 호스트 직접 실행 경로 제거

### 3.3.1 Custom Tool 실패 복구 루프

프로젝트별 custom tool은 생성 후에도 런타임 오류, sandbox 의존성 누락, 잘못된 psutil 속성 접근처럼 실제 사용 중에 실패할 수 있다. 현재는 전용 유지보수 도구(`custom_tool_read_source`, `custom_tool_update_source`)로 source를 읽고 staged update를 검증한 뒤 active artifact를 교체할 수 있는 기반이 마련됐다. 다음 단계는 이 기능을 agent loop에 연결해 “실패 감지 → 원인 분류 → 수정안 생성 → 검증된 교체” 흐름을 자동화하는 것이다.

해야 할 일:

- 툴 실행 실패를 `code_bug`, `dependency_missing`, `sandbox_infra_error`, `permission_denied`, `tool_name_conflict`처럼 재시도 정책이 다른 유형으로 분류
- 실패한 tool의 `project_id`, `tool_name`, `module_name`, sandbox 상태, source path를 history/runtime context에 보존
- 코드 버그로 판단되는 경우 `custom_tool_read_source`로 기존 source를 읽고, 수정안을 생성한 뒤 `custom_tool_update_source`로 staged validation + sandbox gate를 통과할 때만 교체
- sandbox 인프라 오류나 권한 오류는 코드 수정 루프로 진입하지 않고 운영 조치 또는 사용자 승인 필요 상태로 종료
- 같은 실패 구현을 반복하지 않도록 `blockedImplementation`, `retryPolicy`, `suggestedAlternatives`를 다음 PLAN/AGENT 입력에 주입
- nested tool call 기반 report/orchestrator tool은 하위 tool 실패를 parent output에 묻지 말고 repair 후보로 기록

완료 기준:

- 에이전트가 custom tool 런타임 오류를 단순 보고로 끝내지 않고, 수정 가능한 코드 결함인지 먼저 분류함
- 수정 가능한 실패는 기존 active tool을 보존한 채 staged update와 sandbox 검증을 거쳐 교체됨
- 수정 불가능한 실패는 원인, recoverable 여부, 필요한 운영 조치가 사용자에게 명확히 표시됨
- 실패한 artifact 파일이 이름 충돌만 유발하지 않도록 cleanup/audit/debug 기록이 남음

### 3.4 Validator 4종 서버 편입

README는 4가지 도메인 특화 validator를 명시하고 있지만, 현재 서버 구조에는 대부분 비어 있다. `ToolValidator` 수준의 AST 검증만으로는 README가 말한 전체 파이프라인을 충족하지 못한다.

해야 할 일:

- `src/validators/` 구조 실구현
- 최소 4종 역할 정의
  - Execution Validator
  - Query Validator
  - Analysis Validator
  - Suggestion Validator
- 생성 코드 또는 계획서에 대한 단계별 검증 흐름 설계
- validator 결과를 저장/표시하는 응답 스키마 정의

완료 기준:

- 툴 생성 직후 1차 자동 검증이 서버에서 수행됨
- 승인 전 검토 포인트가 구조화되어 반환됨

### 3.5 KB/RAG 도구 실연결

README는 `search_knowledge_base`를 핵심 도구로 정의하지만, 현재는 DB/embedding/service는 있고 실제 에이전트 도구 편입이 비어 있다.

해야 할 일:

- `src/knowledge/*`를 감싸는 실제 도구 구현
- 프로젝트 범위 검색 정책 정의
- 권한별 도구 노출 정책 정리
- 에이전트 레지스트리에 RAG 도구 연결

완료 기준:

- 에이전트가 실제로 KB 검색 도구를 호출할 수 있음
- 벡터 검색 결과가 스트리밍 응답에 반영됨

### 3.6 LangSmith 및 실행 관측성 강화

README는 LangSmith를 MVP 0순위라고 명시하지만, 현재 서버 전반에 정식으로 녹아 있다고 보긴 어렵다.

해야 할 일:

- 스트리밍 엔진 호출 경로에 tracing 추가
- Plan 생성/승인/실행 이벤트 추적
- 툴 생성/검증/샌드박스 실행 추적
- 토큰 사용량, 툴 실패율, validator 실패율 로그 정리

완료 기준:

- 주요 AI 실행 흐름이 LangSmith 또는 동급 trace로 추적 가능
- 운영자가 실패 원인을 역추적할 수 있음

### 3.7 멀티턴 세션/상태 고도화

현재 스트리밍 경로는 single-turn 기준이다. README의 장기 목표와 실제 Tool Maker 흐름을 생각하면 세션 상태와 워크플로우 상태 저장이 필요하다.

해야 할 일:

- multi-turn 세션 저장 전략 정리
- Plan draft/review 상태 저장소 설계
- 승인 대기 중 작업과 일반 대화 세션 분리
- 추후 LangGraph 또는 상태 그래프 기반 전환 검토

완료 기준:

- 서버가 Plan/Agent 상태를 turn 간 유지할 수 있음
- 승인 대기 워크플로우가 재접속 후에도 복원 가능

---

## 4. AI 파트 기준 비목표

다음 작업은 중요하지만 AI 파트의 주도 작업이라기보다 인프라/플랫폼과 공동 작업 성격이 강하다.

- PostgreSQL 운영 구성 최적화
- Docker/DinD 배포 토폴로지
- Spring Boot 내부망 연동 세부 운영 정책
- API Gateway/Ingress/Load Balancer 운영 설정

AI 파트는 이들과 맞물리되, 주도 우선순위는 Plan/Tooling/RAG/Observability 쪽에 둬야 한다.

---

## 5. 권장 브랜치 단위

작업은 다음처럼 브랜치를 끊는 것이 좋다.

1. `plan-mode-server-migration`
- Plan 상태 머신 + structured planner 서버 이관

2. `toolcreator-server-migration`
- `ToolCreatorTool` + `ToolValidator` 서버 이관

3. `sandbox-enforced-tool-execution`
- 생성 코드 실행의 샌드박스 강제 연결

4. `custom-tool-repair-loop`
- custom tool 실패 분류, source read/update, staged sandbox 검증, 실패 context 기반 재계획

5. `validator-pipeline`
- 4종 validator 서버 파이프라인 정리

6. `rag-tool-integration`
- KB 검색 도구를 실제 레지스트리에 편입

7. `ai-observability`
- LangSmith/tracing/운영 로그 정리

8. `multi-turn-state`
- 세션/승인 상태/장기 워크플로우 고도화

---

## 6. 최종 정리

README 기준으로 보면 Theseus의 AI 파트 핵심은 단순 챗봇이 아니라, 다음 세 가지를 묶은 서버형 에이전트 시스템이다.

- 권한별 도구 노출 제어
- 계획 기반 메타-툴링
- 안전한 격리 실행

현재 브랜치까지로 세 번째 축의 기반과 서버 실행 경로는 대부분 준비됐다. 앞으로 AI 파트가 해야 할 본게임은 첫 번째와 두 번째 축, 즉 `Plan + ToolCreator + Validator + RAG`를 `src` 서버형 구조로 완성하는 것이다.
