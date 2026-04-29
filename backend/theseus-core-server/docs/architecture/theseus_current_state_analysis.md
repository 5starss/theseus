# Theseus Core 현재 구현 상태 및 마이그레이션 분석

작성일: 2026-04-28

## 1. 요약

현재 `theseus-core-server`는 두 개의 축으로 발전해왔다.

- `theseus_engine/`
  - OpenHarness를 직접 감싼 에이전트 실험축
  - `RBAC`, `3-Mode(Ask/Agent/Plan)`, `StructuredPlanner`, `ToolCreatorTool`, 세션 관리, TUI/CLI 검증이 여기에 집중되어 있다.
- `src/`
  - FastAPI 기반 서버 제품화 축
  - 인증, SSE 엔드포인트, 과금 보고, PostgreSQL+pgvector 기반 지식베이스, 샌드박스 인터페이스 뼈대가 여기에 있다.

핵심 판단은 단순하다.

- 제품의 핵심 행위 모델은 아직 `theseus_engine/` 쪽이 더 완성도가 높다.
- 배포 가능한 서버 형태의 외곽 구조는 `src/`가 더 맞다.
- 따라서 앞으로의 개발은 `src/`를 메인 런타임으로 삼고, `theseus_engine/`의 검증된 기능을 선별 이식하는 방식이 맞다.

## 2. 현재 기준 구현 상태

### 2.1 실제로 살아있는 Theseus 핵심 기능

다음 기능은 `theseus_engine/` 쪽에서 실제 구현 흔적과 실행 경로가 명확하다.

- 상태 머신
  - `theseus_engine/state.py`
  - `AgentMode`, `PlanPhase`, 모드별 시스템 프롬프트 조합 로직 보유
- 구조화 플래너
  - `theseus_engine/structured_planner.py`
  - Pydantic JSON 기반 플랜 생성 및 블록 렌더링 보유
- RBAC 필터링과 권한 판정
  - `theseus_engine/rbac.py`
  - `theseus_engine/tool_factory.py`
- 메타-툴링
  - `theseus_engine/tool_factory.py`
  - `ToolValidator`, `ToolCreatorTool`, `load_custom_tools`, `build_filtered_registry`
- 세션형 CLI 런타임
  - `theseus_engine/app.py`
- TUI 통합 및 명령어 우회 처리
  - `theseus_engine/tui_app.py`
  - `docs/legacy/tui_command_registration_issue.md`
- OpenHarness 호환성 패치
  - `theseus_engine/monkey_patches.py`

### 2.2 현재 서버형 코드에서 구현된 것

다음 기능은 `src/`에 제품화 방향으로 옮겨져 있다.

- FastAPI 앱 진입점
  - `src/main.py`
- 인증 토큰 검증 클라이언트 및 의존성 주입
  - `src/auth/client.py`
  - `src/auth/dependencies.py`
  - `src/auth/schemas.py`
- SSE 라우트 뼈대
  - `src/routes/stream.py`
- PostgreSQL + pgvector 기반 지식 저장소
  - `src/db/models.py`
  - `src/knowledge/repository.py`
  - `src/knowledge/service.py`
  - `src/knowledge/ingest.py`
- 샌드박스 추상화 계층
  - `src/sandbox/base.py`
  - `src/sandbox/docker_executor.py`

### 2.3 아직 비어 있거나 목업 수준인 영역

- 실제 에이전트 엔진 통합
  - `src/routes/stream.py`는 현재 OpenHarness/Theseus 실행 루프를 연결하지 않고 더미 청크를 SSE로 보낸다.
- 실제 샌드박스 실행
  - `src/sandbox/docker_executor.py`는 `asyncio.sleep()` 기반 목업이다.
- 플랜 모드 서버화
  - `src/builder/`, `src/validators/`는 비어 있다.
- 메타-툴 생성 승인 저장 흐름
  - `AgentClient.save_tool_plan()`은 있으나 실제 `src` 런타임에서 호출 경로가 없다.
- Theseus 상태 머신의 서버 편입
  - 현재 `src/`는 `TheseusStateMachine`을 사용하지 않는다.
- RBAC 기반 툴 주입
  - 현재 `src/`에는 `build_filtered_registry()`와 연결된 서버 요청 흐름이 없다.

## 3. 이관 매트릭스

| 영역 | 원본 위치 | 현재 `src` 이관 상태 | 판단 |
| --- | --- | --- | --- |
| FastAPI 앱 외곽 | 문서 설계 기반 | 완료 | `src/main.py` 중심으로 유지 |
| 인증/세션 검증 | 설계 문서 → `src/auth` | 완료 | 계속 확장 |
| SSE 엔드포인트 | `theseus_engine/app.py`의 스트리밍 경험 참고 | 부분 완료 | 실제 엔진 연결 필요 |
| 상태 머신 | `theseus_engine/state.py` | 미이관 | 높은 우선순위 |
| Plan 모드 | `theseus_engine/state.py`, `structured_planner.py`, `test_phase2_3.py` | 미이관 | 높은 우선순위 |
| Structured Planner | `theseus_engine/structured_planner.py` | 미이관 | 높은 우선순위 |
| RBAC 필터링 | `theseus_engine/rbac.py`, `tool_factory.py` | 미이관 | 높은 우선순위 |
| Tool 생성/검증 | `theseus_engine/tool_factory.py` | 미이관 | 높은 우선순위 |
| 커스텀 툴 로딩 | `theseus_engine/tool_factory.py` | 미이관 | 다만 파일 기반은 재설계 필요 |
| 세션 메모리 | `theseus_engine/sessions.py`, `app.py` | 미이관 | 중간 우선순위 |
| OpenHarness 패치 | `theseus_engine/monkey_patches.py` | 미이관 | 필요시 제한적 편입 |
| 지식베이스 저장/검색 | 설계 문서 및 `src/knowledge/*` | 완료에 가까움 | 서버축 유지 |
| 샌드박스 인터페이스 | `src/sandbox/*` | 부분 완료 | 실행기 실구현 필요 |
| 과금 보고 | `src/auth/client.py` + `src/routes/stream.py` | 부분 완료 | 신뢰성 개선 필요 |

## 4. 이관 시 원칙

### 4.1 그대로 옮기면 안 되는 것

- `custom_tools/` 파일 시스템 즉시 로드 구조
  - 단일 프로세스 PoC에는 맞지만 멀티워커 서버에는 불안정하다.
- 무제한적 몽키패치 의존
  - `monkey_patches.py`는 MVP에서는 유효하지만 서버 기본 구조가 되면 위험하다.
- TUI 전용 우회 로직
  - `theseus_engine/tui_app.py`의 명령 처리 오버라이드는 TUI 문맥에서만 유효하다.

### 4.2 우선 재사용해야 하는 것

- `TheseusStateMachine`
  - 서버 모드 전환 규칙의 기준 구현
- `StructuredPlanner`
  - 이미 JSON structured output 전략이 검증되어 있다.
- `TheseusPermissionChecker`
  - 권한 정책 실험이 가장 많이 축적된 구현
- `ToolValidator`
  - 생성 코드 검증의 출발점으로 충분하다.
- `build_filtered_registry()`
  - RBAC 기반 도구 노출 축소의 핵심

## 5. 마이그레이션 우선순위

### 5.1 1단계: 서버에 실제 Theseus 엔진 붙이기

목표:

- `src/routes/stream.py`에서 더미 스트림 제거
- 실제 OpenHarness + Theseus 엔진 이벤트를 SSE로 내보내기

이식 대상:

- `theseus_engine/state.py`
- `theseus_engine/rbac.py`
- `theseus_engine/tool_factory.py` 중 `build_filtered_registry`
- `theseus_engine/monkey_patches.py` 중 꼭 필요한 부분만

완료 기준:

- `/api/v1/stream` 연결 시 실제 사용자 프롬프트를 받아 응답 생성
- 권한 레벨에 따라 LLM에 노출되는 툴이 달라짐

### 5.2 2단계: Plan 모드 서버화

목표:

- 기존 CLI의 `Plan -> Review -> Execute` 흐름을 서버 API/SSE로 이전

이식 대상:

- `theseus_engine/structured_planner.py`
- `theseus_engine/state.py`
- `test_phase2_3.py`의 실행 흐름

권장 설계:

- `src/builder/`에 Planner service 추가
- Plan draft 생성 API 또는 SSE 이벤트 타입 분리
- 승인 전에는 read-only, 승인 후에만 실행

완료 기준:

- 클라이언트가 structured plan을 받고 수정/승인 가능
- 승인 후 Agent 실행 단계로 자연스럽게 전이

### 5.3 3단계: Tool 생성과 검증 서버화

목표:

- `ToolCreatorTool`과 `ToolValidator`를 `src` 기반 런타임에 편입

이식 대상:

- `theseus_engine/tool_factory.py`

주의:

- 파일 저장 후 즉시 import하는 현 구조는 제품 기본형으로 쓰지 않는 편이 낫다.
- 1차 단계에서는 기존 파일 기반을 유지하더라도, 코드 저장과 실행은 분리해 두는 것이 맞다.

완료 기준:

- 생성 코드가 검증을 통과해야만 저장됨
- 승인 이전/이후 상태를 분리 저장할 수 있음

### 5.4 4단계: 샌드박스 실구현

목표:

- 동적 생성 툴을 메인 프로세스 밖에서 실행

현재 기준:

- `src/sandbox/docker_executor.py`는 목업

완료 기준:

- 네트워크 제한, 시간 제한, 자원 제한이 걸린 실행기 확보
- `ToolCreatorTool` 산출물이 샌드박스 경유로만 실행됨

### 5.5 5단계: 과금/세션/RAG 고도화

목표:

- 서버 운영 안정성 강화

대상:

- `BackgroundTasks` 기반 과금 보고 보강
- 세션 기록 저장 전략 통합
- `search_knowledge`를 실제 툴 호출 체계에 연결

## 6. 지금 당장 개발 시작해야 할 핵심 진입점

우선순위는 다음 순서가 맞다.

1. `src/routes/stream.py`를 실제 Theseus 엔진 스트리밍으로 교체
2. `src` 안에 Theseus 런타임 조립 계층을 신설
3. `TheseusStateMachine`과 `build_filtered_registry()`를 서버에 붙임
4. Plan 모드와 StructuredPlanner를 `src/builder/`로 이관
5. Tool 생성/검증/승인 흐름을 `src/validators/`, `src/builder/`, 저장 계층으로 분리
6. 마지막에 샌드박스와 과금 신뢰성을 강화

## 7. 권장 디렉터리 재배치

권장 방향:

- `src/agent/runtime.py`
  - OpenHarness QueryEngine 생성
  - Theseus system prompt, RBAC, tool registry 조립
- `src/agent/state.py`
  - `theseus_engine/state.py` 이관본
- `src/agent/planner.py`
  - `StructuredPlanner` 이관본
- `src/agent/tools/`
  - `ToolCreatorTool`, `ToolValidator`, registry 관련 코드
- `src/agent/streaming.py`
  - OpenHarness 이벤트 → SSE 이벤트 변환

이 구조가 만들어지면 `theseus_engine/`는 점진적으로 축소하거나 레거시로 격리할 수 있다.

## 8. 최종 판단

현재 Theseus는 "서버 외곽은 `src/`, 핵심 두뇌는 `theseus_engine/`" 상태다.

앞으로의 개발은 새 기능을 `theseus_engine/`에 더 쌓는 방식보다, 이미 검증된 핵심을 `src/`의 서버 런타임으로 편입하는 작업이 우선이다. 특히 첫 번째 실질적 마일스톤은 `src/routes/stream.py`가 더미 응답이 아니라 실제 Theseus 엔진을 흘려보내는 시점이다.
