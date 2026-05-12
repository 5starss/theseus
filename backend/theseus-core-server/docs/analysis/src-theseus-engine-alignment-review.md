# src / theseus_engine 정합성 검토

작성일: 2026-05-12

## 검토 목적

이 문서는 `backend/theseus-core-server/src`와
`backend/theseus-core-server/theseus_engine`의 현재 구현을 기준으로,
두 영역의 역할 분리가 어긋난 부분과 비효율적으로 동작할 수 있는
부분을 기록한다.

검토의 중심 기준은 다음과 같다.

- `src`는 FastAPI 서버 오케스트레이션, 인증, 세션, 과금, DB 연동,
  Spring 서버 연동을 담당한다.
- `theseus_engine`은 QueryEngine, tool runtime, stream event, RBAC,
  memory, skill injection, runner runtime 등 에이전트 실행 코어를
  담당한다.
- 서버 경로는 `theseus_engine`의 런타임 기능을 재사용하되, 서버 전용
  권한 검증과 영속화 경계만 `src`에서 소유하는 방향이 바람직하다.

## 현재 역할 분리

현재 코드 구조는 대체로 `src`와 `theseus_engine`의 역할을 나누고
있지만, 일부 경로는 이행기 구현이 남아 있다.

- `src/routes/stream.py`는 SSE 요청을 받고 세션 검증, 히스토리 로드,
  사용자/어시스턴트 메시지 저장, 과금 outbox 적재를 담당한다.
- `src/builder/engine.py`는 서버용 `QueryEngine`을 직접 조립한다.
- `theseus_engine/core/engine_builder.py`는 로컬/daemon/CLI 계열에서
  사용하는 최신 엔진 조립 흐름을 담고 있으며, scoped memory, dynamic
  tool retrieval, skill injection, 요청 단위 통계와 비용 추적기를 포함한다.
- `src/tool_plan`, `src/tool_build`, `src/tool_generation`은 서버의 tool
  생성 워크플로를 Kafka 기반으로 처리한다.
- `src/knowledge`와 `theseus_engine/rag`는 모두 지식 검색/RAG 영역을
  다루지만, 현재 스키마와 서비스 API가 다르다.

## 주요 발견 사항

### 1. Knowledge/RAG 경로의 스키마와 API가 충돌 가능하다

`src`의 knowledge 경로는 프로젝트 단위 지식 베이스를 전제로 한다.
`KnowledgeDocument`와 `KnowledgeChunk`를 분리하고, 검색 시
`KnowledgeChunk.project_id`를 기준으로 필터링한다.

반면 `theseus_engine.rag`는 같은 `knowledge_documents` 테이블명에
`content`, `metadata`, `embedding`을 직접 저장하는 단일 테이블 DDL을
사용한다. 같은 PostgreSQL schema를 바라보면 `src`의 SQLAlchemy 모델과
`theseus_engine.rag.database`의 직접 DDL이 충돌할 수 있다.

추가로 `theseus_engine.tools.core.knowledge_tools.IngestDocumentTool`은
`rag.ingest(...)`를 호출하지만, 현재 `RAGService`에는 `ingest_text(...)`와
`ingest_file(...)`만 존재한다. RAG 의존성이 설치되어 실제 tool이 실행되면
ingest 경로에서 런타임 오류가 발생할 수 있다.

권장 방향:

- 서버 모드에서는 `search_knowledge_base`, `ingest_document`가
  `src.knowledge`의 프로젝트 스코프 repository/service를 사용하도록
  맞춘다.
- 통합 전까지는 서버 registry에서 engine RAG tool을 제외하거나, 동일한
  테이블명을 사용하지 않도록 명확히 분리한다.
- `theseus_engine.rag`가 계속 필요하다면 DB 스키마명을 별도로 분리하거나,
  `src.knowledge` 스키마를 기준으로 engine RAG 구현을 재작성한다.

### 2. 서버용 엔진 조립이 최신 engine_builder 방향과 분리되어 있다

`src/builder/engine.py`는 `ALL_CORE_TOOLS` 등록, custom tool load,
권한 필터링, hook executor, `QueryEngine` 생성을 직접 수행한다. 이
방식은 서버 전용 guard를 삽입하기 쉽다는 장점이 있지만,
`theseus_engine/core/engine_builder.py`에 추가된 최신 런타임 기능을
자동으로 따라가지 못한다.

현재 서버 SSE 경로에서 빠지거나 약하게 연결된 기능은 다음과 같다.

- `ScopedMemory` 기반 memory context 주입
- `SkillInjectionConfig` 기반 자동 skill prompt injection
- `ToolRetriever` 기반 질의별 top-k tool retrieval
- `project_disabled_tools` 기반 프로젝트 단위 tool visibility
- 요청 단위 `CostTracker`, `SessionStats` metadata
- `cwd`를 서버 프로세스 현재 디렉터리 대신 요청/프로젝트 workspace로
  해석하는 경로

또한 `EngineBuildContext.user_query` 필드는 존재하지만, `src/routes/stream.py`
에서 prompt를 전달하지 않고 `src/builder/engine.py`에서도 dynamic tool
retrieval에 사용하지 않는다. 결과적으로 서버 경로는 모든 active tool을
정적으로 구성하는 쪽에 가깝고, engine builder의 token 절감 방향과 차이가
난다.

권장 방향:

- 서버용 builder를 `theseus_engine.core.engine_builder.setup_engine`의
  조립 흐름에 수렴시킨다.
- `src`에는 인증, session context, project permission, plan guard,
  billing/history persistence만 남긴다.
- `EngineBuildContext`에는 prompt 기반 `user_query`, project disabled
  tools, workspace `cwd`, actor role을 명시적으로 채운다.
- 서버 전용 plan guard는 hook wrapper 또는 permission provider callback
  형태로 주입한다.

### 3. Kafka tool 생성 흐름에 legacy와 신규 consumer가 병존한다

`src/main.py`는 Kafka consumer 활성화 시 legacy `tool_generation`,
신규 `tool_plan`, `tool_build` consumer를 모두 시작하는 구조다.
`src/tool_generation/processor.py`는 legacy
`TOOL_GENERATION_*` 메시지를 내부적으로 `ToolPlanPlanner`에 위임하는
호환 adapter 역할을 한다.

현재 `CORE_KAFKA_CONSUMER_ENABLED` 기본값이 `False`라 기본 실행에서는
즉시 문제가 되지 않는다. 다만 운영 환경에서 consumer를 켜고, API 서버가
legacy 이벤트와 신규 이벤트를 동시에 발행하면 같은 tool draft에 대해
계획 생성이 중복될 수 있다.

권장 방향:

- legacy consumer는 명확한 migration flag로 분리하고 운영 기본값을
  신규 pipeline 중심으로 정리한다.
- API 서버 이벤트 계약이 신규 `tool_plan`/`tool_build`로 완전히 이동한
  뒤에는 `tool_generation` 경로를 제거하거나 문서상 legacy로 고정한다.
- 중복 소비 방지를 위해 event id, tool draft id, plan id 기준 idempotency
  검증을 명시한다.

### 4. Tool 생성/검증 책임이 일부 중복된다

`src.tooling.service`는 서버용 tool 생성 pipeline을 소유한다. 여기에는
plan guard, sandbox gate, artifact persistence, activation, project scoped
tool loading이 포함된다. 이 책임은 서버 경계에 남는 것이 타당하다.

다만 `normalize_tool_name`, `inject_permission_level`, validation 호출,
custom tool path/metadata 처리 일부는 `theseus_engine.tools.core.tool_factory`
및 `tool_validator`와 유사한 책임을 가진다. 실제로 engine의
`CreateToolTool`도 서버 context가 있으면 `src.tooling.create_tool_for_server`
로 위임하고, context가 없으면 standalone 경로를 직접 수행한다.

권장 방향:

- plan guard, DB/API 연동, sandbox gate, activation은 `src.tooling`에 둔다.
- tool naming, permission injection, module validation, metadata normalization
  같은 순수 런타임 유틸은 `theseus_engine.tools.core`로 모은다.
- 서버와 standalone이 같은 validator 결과를 공유하도록 반환 구조를
  정리한다.

### 5. 권한 provider 추상화가 서버 builder에 충분히 반영되지 않았다

`theseus_engine.models.permission_provider`에는 standalone/server 공통
권한 provider 인터페이스가 있다. 주석상 server provider는 `src/auth`를
직접 import하지 않고 callback으로 권한 정보를 받는 방향이다.

하지만 현재 `src/builder/engine.py`는 provider를 사용하기보다
`project_tool_permissions`를 직접 받아 registry filtering에 넘긴다. 동작은
가능하지만, engine 쪽에서 의도한 provider 추상화와 서버 builder가 아직
완전히 맞물려 있지는 않다.

권장 방향:

- `src.auth`에서 가져온 project permissions와 disabled tools를
  `ServerPermissionProvider` callback으로 감싼다.
- `setup_engine` 또는 그에 준하는 공통 builder가 provider를 통해 권한,
  disabled tools, sync 동작을 얻도록 정리한다.
- `theseus_engine`이 `src`를 직접 import하지 않는 방향은 유지한다.

## 권장 정리 순서

1. Knowledge/RAG 경로를 먼저 정리한다.
   현재는 같은 테이블명을 서로 다른 스키마로 해석할 수 있어, 실제 운영
   DB와 연결될 때 가장 큰 충돌 위험이 있다.

2. 서버용 engine assembly를 `theseus_engine.core.engine_builder` 흐름으로
   수렴시킨다.
   이 작업을 통해 scoped memory, skill injection, dynamic tool retrieval,
   request scoped stats/cost tracking을 서버 SSE 경로에서도 동일하게 쓸 수
   있다.

3. Kafka tool 생성 pipeline의 legacy 경계를 명확히 한다.
   신규 `tool_plan`/`tool_build` 흐름을 기준으로 중복 소비 가능성을 줄이고,
   legacy `tool_generation`은 호환 기간에만 유지한다.

4. tool 생성/검증 유틸을 공통화한다.
   서버 전용 정책과 순수 tool validation 유틸을 분리하면 standalone과
   server mode의 생성 결과가 덜 어긋난다.

## 검토 범위와 한계

- 이 문서는 정적 코드 검토 결과를 기록한 것이다.
- 테스트, 서버 실행, Kafka consumer 실행, DB migration 검증은 수행하지
  않았다.
- 문서 작성 시점의 기준 파일은 다음과 같다.
  - `src/builder/engine.py`
  - `src/routes/stream.py`
  - `src/tool_generation/processor.py`
  - `src/tool_plan/planner.py`
  - `src/tool_build/builder.py`
  - `src/tooling/service.py`
  - `src/knowledge`
  - `theseus_engine/core/engine_builder.py`
  - `theseus_engine/engine/query_engine.py`
  - `theseus_engine/rag`
  - `theseus_engine/tools/core`
