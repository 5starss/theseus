# 남은 작업 명세서 (Remaining Tasks)

본 문서는 Theseus 에이전트 시스템 및 플랫폼 인프라 측면에서 앞으로 진행해야 할 주요 과제들을 로드맵 형태로 정리합니다. 아키텍처 리팩토링 및 래핑(Phase 1~3)이 완료됨에 따라, `README.md`의 세부 업무 분장(Developer A/B)을 기준으로 작업을 재분류했습니다.

---

## 1. 👨‍💻 Developer B: AI 에이전트 & 툴링 고도화 (Phase 4)

AI가 스스로 코드를 작성하는 메타-툴링 파이프라인을 안전하고 완벽하게 구축하기 위한 검증기(Validator) 4종 구현 및 관측성 작업입니다. (`theseus_engine/validators/`에 위치)

* **🟢 1.1. Analysis 검증기 (완료)**: `ast` 모듈을 통한 코드 정적 분석. `AnalysisValidator`로 독립 모듈화 완료. `tool_factory.py`에서 위임 호출.
* **🟢 1.2. Execution & Query 검증기 (완료)**: Regex 기반(기본) + LLM 기반(토글) 이중 검증 구현. `TheseusHookExecutor`를 통해 `PRE_TOOL_USE` Hook에 연결. (보안 훅 런타임 오류 및 'bool' object is not callable 에러 해결 완료)
* **🟢 1.3. Suggestion 검증기 (완료)**: LLM 기반 코드 리뷰 Stub 구현. 향후 `TheseusLLMClient` 연동 예정.
* **🟢 1.4. 관측성(Observability) 연동 명세 (완료)**: LangSmith 연동 및 `@theseus_traceable` 데코레이터를 통한 에이전트 궤적 추적 시스템 구축. API 키 미설정 시 자동 bypass(no-op).
  * **[Task 1] 핵심 엔진 트레이싱**: `query.py`의 `run_query`, `_execute_tool_call` 등 핵심 에이전트 루프에 `@traceable` 데코레이터를 적용하여 LLM 호출부터 도구 실행까지의 전체 사이클 추적.
  * **[Task 2] 검증기(Validator) 훅 모니터링**: `TheseusHookExecutor` 및 4종 검증기 실행 결과에 트레이싱을 추가하여, 어떤 쿼리가 왜 차단되었는지(Security Audit) 대시보드에 시각화.
  * **[Task 3] 커스텀 도구(Meta-Tooling) 추적**: `create_tool`로 동적 생성된 도구의 AST 검증 과정과 에러 피드백 루프를 모니터링하여 프롬프트 개선 데이터로 활용.
  * **[Task 4] 환경 및 메타데이터 주입**: LangSmith 트레이스 런(Run)에 사용자의 RBAC 레벨(`user_level`), 현재 세션명, 사용 모델 정보를 태그로 주입하여 엔터프라이즈 레벨의 다차원 필터링 구현.
* **🟢 1.5. 도구 검색 최적화 및 런타임 주입 (완료)**: RAG 기반 도구 선택 알고리즘 고도화 및 다단계 추론 중 도구 가용성 확보.
  * **[Task 1] 동적 재인덱싱**: 레지스트리 도구 개수 변화를 감지하여 재시작 없이 임베딩 인덱스를 갱신하는 기능 구현.
  * **[Task 2] 키워드 리랭킹**: 시맨틱 검색 보완을 위해 사용자 쿼리 키워드 매칭 보너스 점수 시스템 도입.
  * **[Task 3] Runtime Discovery Hook**: `POST_TOOL_USE` 훅을 통해 도구 실행 결과에서 단서를 찾아 연관 도구를 즉시 레지스트리에 주입하는 시스템 구축.
  * **[Task 4] Pydantic 규격 정합성**: `model_rebuild()` 및 `Optional` 임포트 전수 조사를 통한 런타임 스키마 에러 해결.
  * **[Task 5] 동적 기능 토글**: `THESEUS_DYNAMIC_TOOL_RETRIEVAL` 환경 변수 및 `enable_dynamic_tools` 파라미터를 통해 동적 도구 검색/주입 기능을 온오프할 수 있는 제어권 확보.
* **🟢 1.6. 에이전트 복원력 및 자율 복구 (완료)**: 도구 에러 및 엔진 예외 상황에서 스스로 복구하고 실행을 지속하는 자율 루프 구축.
  * **[Task 1] 자율 복구 루프 (Auto-Resume)**: `AGENT`/`PLAN` 모드에서 도구 에러 발생 시 자동으로 다음 턴을 트리거하여 에이전트가 에러를 즉시 수정하도록 개선.
  * **[Task 2] 엔진 예외 메모리 주입**: Pydantic 에러 등 엔진 내부 예외를 에이전트 히스토리에 자동 주입하여 "자가 수정" 유도.
  * **[Task 3] 데이터 타입 자동 보정**: `POST_TOOL_USE` 훅에서 `dict/list` 출력을 JSON 문자열로 자동 변환하여 유효성 검사 에러 원천 차단.
  * **[Task 4] PLAN 모드 형식 엄격화**: 계획 작성 시 순수 JSON 출력을 강제하고, CLI 레벨에서 출력 제약을 리마인드하는 강화 로직 적용.

---

## 2. 👨‍💻 Developer A: 플랫폼 인프라 확장 (Phase 5)

현재 CLI/TUI 기반의 로컬 스크립트를 실제 엔터프라이즈 Web 서비스로 확장하기 위한 백엔드/인프라 작업입니다.

* **2.1. 다이렉트 SSE 스트리밍 서버 (FastAPI)**: 기존 로컬 CLI가 아닌 `FastAPI` 기반으로 `/stream` 엔드포인트 구축 및 클라이언트 브라우저와 직접 SSE 통신을 통한 실시간 로그 전송.
* **2.2. Zero-Trust 과금(Billing) 통신**: 에이전트 스트리밍 종료 직후, `UsageSnapshot`을 바탕으로 Spring Boot 백엔드 내부망에 비용 정보를 직접 전송.
* **2.3. 지식 베이스(KB / RAG)**: PostgreSQL(`pgvector`) 연동을 통해 중앙집중식 도메인 지식 검색 기능(`search_knowledge_base`) 도구 구축 및 연동.
* **2.4. 샌드박스 격리 (DinD / Serverless)**: 사용자가 생성한 커스텀 도구(`.py`)가 호스트 서버에 영향을 주지 못하도록 Docker-in-Docker 또는 별도 서버리스 환경에서 실행되도록 Remote Execution 샌드박스 인프라 적용.

---

## 3. ✨ UX 및 기타 편의성 개선 (Future Plan)

* **3.1. CLI 자동완성(Auto-Completion)**: `prompt-toolkit` 등의 라이브러리를 도입하여 터미널 환경에서도 슬래시 명령어(`/`) 및 파일 경로(`@`) 자동완성 지원.
* **3.2. 세션 관리 영속성 개선**: `sessions.py` 내 로컬 파일 저장 로직을 OpenHarness 공식 Memory 체계 또는 별도의 RDBMS 저장소로 전환.
* **3.3. TUI UI/UX 대대적 개선**:
  - `textual.app.App` 상속 구조를 유지하며, Textual 프레임워크의 2.0 최신 문법 및 디자인 패턴 적용.
  - `Sidebar`에 **Static Headers** 도입: LLM이 Status/Context 패널의 내용을 덮어쓰는 문제를 원천적으로 차단.
  - `Status Panel` 실시간 렌더링: `engine.total_usage` 객체를 직접 참조하여 실시간 Token 수 및 메시지 수를 표시 (메시지 수 증가에 따른 스크롤 불필요).
  - `Cursor` 및 `Active` 스타일 통일: 기존의 진한 노란색 하이라이트를 전면 제거하고, `default` 테마의 보라색(`purple`) 하이라이트로 통일하여 시각적 일관성 확보.
  - 입력창(`Input`)의 테두리 스타일 변경: `solid` -> `double`로 변경하여 시각적 포인트를 강화.
* **3.4. Phase 5 아키텍처 래핑 준비 (Core/TUI 분리)**:
  - 현재 단일 파일(`tui_app.py`)에 섞여있는 OpenHarness 코어 로직과 TUI 위젯/명령어를 논리적 기능 단위로 완벽하게 분리.
  - `tui/`와 `core/` 디렉토리 신설 및 `engine_builder.py`, `command_handler.py` 등 모듈 분리 완료.
  - 향후 `core/` 내의 OpenHarness `TerminalApp` 클래스를 상속받아 테세우스 전용 `TUI App`을 구현하는 구조(Wrapping)로 설계하여 `Engine 래핑 마일스톤`과 완벽한 연동 계획 수립.

---

## 4. 🚀 추가 고도화 작업 (Theseus 전용 슬래시 명령어 추가)

TUI 및 CLI 인터페이스에서 B2B 에이전트 서비스로서의 완성도를 높이기 위해 다음 명령어들을 래핑 및 추가 구현합니다. 추가적으로 TUI뿐만 아니라 CLI에서도 동일한 기능이 동작하도록 구현해야 합니다.

* **🟢 4.1. /tools (또는 /registry)**: 현재 사용자의 RBAC 레벨에서 사용 가능한 도구와 권한 부족으로 차단된 도구를 시각적으로 구분하여 표 형태로 출력 (CLI 구현 완료).
* **🟢 4.2. /rbac <level>**: 관리자용 디버깅/테스트 목적으로 현재 세션의 `user_level`을 일시적으로 변경 (CLI 구현 완료).
* **🟢 4.3. /validate <tool_name>**: `create_tool`로 생성된 도구를 수동으로 보안/문법 검증 (CLI 구현 완료).
* **🟢 4.4. /approve / /reject**: 비동기 서버 전환(Phase 5) 시, 에이전트의 위험도 높은 행동 승인 대기를 처리하는 워크플로우 커맨드 (CLI 스텁 구현 완료).
* **🟢 4.5. /kb <query>**: 에이전트를 거치지 않고 사내 문서/지식 기반(Knowledge Base)을 직접 빠르게 검색 (CLI 구현 완료).
* **4.6. `/export [format]`**: 현재 대화 내역이나 Plan 모드에서 생성한 '구현 계획서'를 Markdown, PDF 등의 형태로 내보내기 (엔터프라이즈 리포팅용).

---

## 5. 🧱 시스템 구조적 개선 및 안정화 (Technical Debt & Stability)

분석을 통해 발견된 잠재적 위험 요소와 구조적 불일치를 해결하여 시스템의 견고함을 확보합니다.

* **🟢 5.0. setup_engine async 전환 후속 버그 수정 — 완료 (Hotfix)**:
    * `agent_tool.py` 서브 에이전트 스크립트 문자열 내 `await setup_engine(...)` 누락 → 크래시 수정.
    * `theseus_hook_executor._discover_and_inject_tools()` 주입 목록 선확정 후 일괄 등록으로 레지스트리 순회 중 변경 방지.
    * `theseus_cli.py` 세션 종료 시 `await CostTracker.get_or_create().save_async()` 호출 추가.

* **🟢 5.1. 비동기 동시성 제어 (Async Safety) — 완료**:
    * `ToolRetriever._ensure_indexed()`에 `asyncio.Lock` + double-checked locking 도입. 병렬 도구 실행 시 임베딩 인덱스 중복 재빌드(레이스 컨디션) 방지.
    * `retrieve_top_k()`를 `async def`로 전환, 임베딩 연산을 `asyncio.to_thread()`로 오프로드.
    * 128-entry 수동 LRU 쿼리 임베딩 캐시 추가, 레지스트리 변경 시 자동 무효화.
    * `setup_engine()`을 `async def`로 전환, 전체 호출부(`theseus_cli.py` 3곳, `cli_main.py`, `tui_main.py`) 일괄 `await` 적용.
    * `sessions.py` 파일 I/O → `asyncio.to_thread()` 래핑(`save_session_history_async` 추가).
    * `cost_tracker.py` → `save_async()` 추가.

* **🟢 5.2. 프로세스 자원 관리 고도화 — 완료**:
    * `BashTool`: `except asyncio.CancelledError` 블록 추가 → 취소 시 `_terminate(process, force=True)` 호출 후 re-raise. 좀비 프로세스 방지.

* **5.3. 컨벤션 전수 리팩토링**:
    * 모든 모듈의 docstring을 **Google Style**로 통일 (Args, Returns 블록 누락분 보충).
    * `__init__` 메서드 및 헬퍼 함수의 반환 타입 힌트(`-> None` 등) 전수 조사 및 수정.

* **5.4. 한국어 지역화 준수 (Rule 14 Audit)**:
    * `rbac.py`, `execution_validator.py` 등 핵심 엔진 내에 남아있는 영문 사용자 메시지를 모두 한국어로 전환.

* **5.5. 레지스트리 가변성 안전성 검증**:
    * 런타임 중 도구 주입 시 OpenHarness 엔진 루프에 미칠 수 있는 부작용(순회 중 변경 등)에 대한 정밀 검증 및 필요시 불변성(Immutability) 확보.

---

## 6. 🌐 멀티 에이전트 아키텍처 도입 (LangGraph)

현재 OpenHarness 엔진은 **단일 에이전트가 여러 도구를 사용하는 방식**에 최적화되어 있습니다. 이를 엔터프라이즈급으로 고도화하고 턴 리밋과 컨텍스트 오염을 방지하기 위해 역할을 분리하는 **Multi-Agent 아키텍처(LangGraph)** 도입을 추진합니다.

* **6.1. Router Agent (라우터 / 오케스트레이터)**: 사용자의 의도를 분석하고 태스크를 분배하는 두뇌 역할.
* **6.2. Research Sub-Agent (조사 전용 에이전트)**: 웹 서칭/문서 파싱 전담 (낮은 온도, 긴 컨텍스트 윈도우, 타이트한 루프 리밋 적용).
* **6.3. Coder Sub-Agent (개발 전용 에이전트)**: 리서치 에이전트가 요약해준 정제된 마크다운을 바탕으로 코드를 짜고 검증.
* **6.4. 마이그레이션 전략**: Phase 5 이후 `TheseusHookExecutor` 등에서 에이전트 루프 제어 시, 단순 툴 호출 대신 **"다른 에이전트에게 메시지 전달(Send Message)"** 형태의 툴 노드(LangGraph Node)를 추가하여 점진적 전환.

---

---

## 7. 🔜 남은 작업 (Next Phase — 우선순위 순)

아래는 5.1~5.2 완료 후 바로 진행 가능한 단기 과제들입니다.

### 7.1. 컨벤션 및 코드 품질 (= 5.3 상세화)

| # | 파일 / 범위 | 내용 | 난이도 |
|---|------------|------|--------|
| A | 전체 `theseus_engine/` | Google Style docstring 일괄 보충 (`Args:`, `Returns:`, `Raises:`) | 낮음 |
| B | `tool_retriever.py`, `cost_tracker.py`, `sessions.py` | `__init__`, 헬퍼 함수 반환 타입 힌트(`-> None`, `-> dict` 등) 누락분 추가 | 낮음 |
| C | `rbac.py`, `execution_validator.py`, `query_validator.py` | 남아있는 영문 사용자 메시지 → 한국어 전환 (Rule 14) | 낮음 |

### 7.2. 레지스트리 가변성 안전성 (= 5.5 상세화)

* `TheseusHookExecutor._discover_and_inject_tools()` 에서 `active_registry.register()` 호출 중 OpenHarness 내부 루프가 동일 레지스트리를 순회하는 경우 `RuntimeError: dictionary changed size during iteration` 발생 가능성 검증.
* 검증 결과에 따라 레지스트리 복사본(snapshot) 전달 또는 주입 큐(queue) 방식으로 전환.

### 7.2-b. 파일 수정 Diff 미리보기 — 완료

* `theseus_hook_executor._show_diff_preview()` 구현 완료.
* `write_file` / `edit_file` 실행 전 unified diff를 터미널에 색상 출력 후 기존 HITL 승인 흐름으로 연결.

### 7.3. FastAPI SSE 스트리밍 서버 (= 2.1 상세화)

* `theseus_engine/` 코어를 그대로 재사용하며 FastAPI 레이어만 추가:
    * `POST /v1/chat` — SSE 스트리밍 엔드포인트 (`StreamingResponse`).
    * `setup_engine()` 이 이미 `async`이므로 FastAPI `lifespan`에서 직접 `await` 가능.
    * 인증: `Authorization: Bearer <JWT>` 헤더 검증 → RBAC 레벨 추출.
    * 세션: `session_id` 파라미터로 `load_session_history()` / `save_session_history_async()` 연동.
* Spring Boot 내부망 과금 콜백: 스트림 종료 후 `cost_tracker.save_async()` → HTTP POST to billing endpoint.

### 7.4. 샌드박스 격리 (= 2.4 상세화)

* `create_tool`로 생성된 `.py` 파일 실행을 Docker-in-Docker 또는 AWS Lambda 등 격리 환경으로 이관.
* `BashTool` 실행 경로도 동일한 샌드박스를 거치도록 `execution_validator.py` 연동.

### 7.5. `/export [format]` 슬래시 명령어 (= 4.6)

* `theseus_cli.py` 및 `tui_main.py` 양쪽에 `/export md` / `/export pdf` 명령 추가.
* 대화 히스토리 → Markdown 변환은 `ConversationMessage` 순회로 즉시 구현 가능.
* PDF: `weasyprint` 또는 `pdfkit` 의존성 선택적 추가(미설치 시 Markdown만 지원).

### 7.6. LangGraph 멀티 에이전트 마이그레이션 (= 6.x 전체, 장기)

* 현재 `AgentTool`(서브 에이전트 스폰)을 기반으로 점진적 전환 가능:
    1. Router Node: `TheseusStateMachine.mode` → LangGraph conditional edge로 매핑.
    2. Research / Coder Sub-Agent Node: 각각 별도 `setup_engine()` 인스턴스 + 전용 레지스트리.
    3. `TheseusHookExecutor` 훅 이벤트를 LangGraph interrupt로 전환.
* 선행 조건: FastAPI 서버(7.3) 완료 후 진행 권장.

---

## 📝 작업 변경 로그 (Changelog)
- CLI 인터페이스 사용성 증대를 위해 핵심 슬래시 명령어 5종(/tools, /rbac, /validate, /approve/reject, /kb)에 대한 CLI 기반 구현을 완료하였습니다.
- 시스템 안정성 및 운영 편의성을 위해 기능별로 검증을 마쳤으며, 향후 비동기 서버 모델로의 확장 가능성을 고려하여 설계되었습니다.
- `temp_di` 브랜치에서 코드 품질 개선 일괄 수정 완료 (2026-05-07):
    - Phase 1: 버그 3종 수정 (크로스플랫폼 경로, async 중첩, 동기 I/O 블로킹).
    - Phase 2: 레거시 파일 3종 삭제 및 import 잔재 정리.
    - Phase 3: 성능/안정성 개선 4종 (asyncio.Lock, LRU 캐시, 좀비 프로세스 방지, save_async).
- Hotfix — Phase 3의 `setup_engine` async 전환이 유발한 후속 버그 3종 수정 (2026-05-07):
    - `agent_tool.py` 서브 에이전트 즉시 크래시 (🚨 Critical).
    - `theseus_hook_executor.py` 레지스트리 순회 중 변경 방지 (⚠️ High).
    - `theseus_cli.py` 세션 종료 시 비용 로그 미저장 (📌 Medium).

