# 남은 작업 명세서 (Remaining Tasks)

본 문서는 Theseus 에이전트 시스템 및 플랫폼 인프라 측면에서 앞으로 진행해야 할 주요 과제들을 로드맵 형태로 정리합니다. 아키텍처 리팩토링 및 래핑(Phase 1~3)이 완료됨에 따라, `README.md`의 세부 업무 분장(Developer A/B)을 기준으로 작업을 재분류했습니다.

---

## 1. 👨‍💻 Developer B: AI 에이전트 & 툴링 고도화 (Phase 4)

AI가 스스로 코드를 작성하는 메타-툴링 파이프라인을 안전하고 완벽하게 구축하기 위한 검증기(Validator) 4종 구현 및 관측성 작업입니다. (`theseus_engine/validators/`에 위치)

* **🟢 1.1. Analysis 검증기 (완료)**: `ast` 모듈을 통한 코드 정적 분석. `AnalysisValidator`로 독립 모듈화 완료. `tool_factory.py`에서 위임 호출.
* **🟢 1.2. Execution & Query 검증기 (완료)**: Regex 기반(기본) + LLM 기반(토글) 이중 검증 구현. `TheseusHookExecutor`를 통해 `PRE_TOOL_USE` Hook에 연결.
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

* **5.1. 비동기 동시성 제어 (Async Safety)**: 
    * `ToolRetriever` 내 인덱스 재빌드(`_ensure_indexed`) 로직에 `asyncio.Lock`을 도입하여 병렬 도구 실행 시 레이스 컨디션 방지.
* **5.2. 프로세스 자원 관리 고도화**:
    * `BashTool` 등 외부 프로세스 실행 도구에서 코루틴 취소 시 하위 프로세스가 고아(Zombie)가 되지 않도록 `try...finally` 및 프로세스 그룹 정리 로직 보완.
* **5.3. 컨벤션 전수 리팩토링**:
    * 모든 모듈의 docstring을 **Google Style**로 통일 (Args, Returns 블록 누락분 보충).
    * `__init__` 메서드 및 헬퍼 함수의 반환 타입 힌트(`-> None` 등) 전수 조사 및 수정.
* **5.4. 한국어 지역화 준수 (Rule 14 Audit)**:
    * `rbac.py`, `execution_validator.py` 등 핵심 엔진 내에 남아있는 영문 사용자 메시지를 모두 한국어로 전환.
* **5.5. 레지스트리 가변성 안전성 검증**:
    * 런타임 중 도구 주입 시 OpenHarness 엔진 루프에 미칠 수 있는 부작용(순회 중 변경 등)에 대한 정밀 검증 및 필요시 불변성(Immutability) 확보.

---

## 📝 작업 변경 로그 (Changelog)
- CLI 인터페이스 사용성 증대를 위해 핵심 슬래시 명령어 5종(/tools, /rbac, /validate, /approve/reject, /kb)에 대한 CLI 기반 구현을 완료하였습니다.
- 시스템 안정성 및 운영 편의성을 위해 기능별로 검증을 마쳤으며, 향후 비동기 서버 모델로의 확장 가능성을 고려하여 설계되었습니다.
