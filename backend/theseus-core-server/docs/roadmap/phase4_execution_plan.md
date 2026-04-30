# Phase 4~5 핵심 기능 구현 실행 계획서 (Execution Plan)

**작성일**: 2026-04-28
**목표**: LangGraph 마이그레이션, RAG(PostgreSQL `pgvector`) 지식 베이스 구축, TUI/CLI 사용자 경험 고도화에 대한 우선순위 및 세부 구현 일정 수립

---

## 1. 전반적인 우선순위 및 순서 (Priority & Sequence)

안정적인 기반 위에 기능이 쌓일 수 있도록 데이터 인프라(RAG)를 먼저 확보한 후, 엔진 오케스트레이터(LangGraph)를 교체하고, 마지막으로 사용자 인터페이스(TUI/CLI)를 씌우는 순서가 가장 이상적입니다.

*   **1순위: RAG 지식 베이스 구축 (Data Infra)**
    *   **이유**: 에이전트의 지능을 결정짓는 핵심 데이터 소스입니다. LangGraph 마이그레이션 전에 RAG 도구가 완성되어 있어야, 새로운 워크플로우(`StateGraph`) 내에 RAG 도구를 자연스럽게 노드(Node)로 편입시킬 수 있습니다.
*   **2순위: LangGraph 마이그레이션 (Core Engine Orchestration)**
    *   **이유**: 시스템의 '뇌'와 '심장'을 바꾸는 대공사입니다. UI가 고도화되기 전에 백엔드 상태(State) 머신이 안정적으로 완성되어야 프론트엔드(TUI)에서 예기치 않은 상태 렌더링 에러를 막을 수 있습니다.
*   **3순위: TUI/CLI 고도화 및 커맨드 래핑 (UX/UI)**
    *   **이유**: 기반 엔진(LangGraph)과 툴셋(RAG)이 모두 갖춰진 상태에서, 사용자가 이를 쉽게 조작하고 모니터링할 수 있도록 껍데기를 입히는 마무리 작업입니다.

---

## 2. 세부 구현 로드맵 (Detailed Roadmap)

### 🥇 Step 1: 지식 베이스(KB) 및 RAG 구축 (PostgreSQL + pgvector) [✅ 완료]
**목표**: 사내 문서를 벡터화하여 저장하고, 에이전트가 이를 조회할 수 있는 도구 구축
**예상 소요 기간**: 1~2일

1. **데이터베이스 세팅 및 연결**
   *   `psycopg2`, `pgvector`, `sentence-transformers` 의존성 설치 및 설정.
   *   `.env` 파일에 정의된 `POSTGRES_*` 및 `EMBEDDING_*` 변수를 로드하는 `DatabaseManager` 클래스 작성.
2. **임베딩(Embedding) 파이프라인 구축**
   *   로컬(`all-MiniLM-L6-v2`) 또는 원격(OpenAI) 임베딩 프로바이더 선택 로직 구현.
   *   텍스트를 청킹(Chunking)하여 벡터로 변환 후 `theseus_core` DB에 적재하는 유틸리티 작성.
3. **`search_knowledge_base` 도구 개발**
   *   LLM이 검색어를 넘기면 Vector DB에서 코사인 유사도(Cosine Similarity)를 통해 연관된 상위 `RAG_TOP_K`개의 문서를 반환하는 도구 개발.
   *   RBAC 연동: 특정 부서 문서나 민감 정보에 접근하기 위한 `permission_level` 부여.

### 🥈 Step 2: LangGraph 기반 오케스트레이션 마이그레이션
**목표**: 기존의 절차적 `while` 루프 및 하드코딩된 상태 머신을 LangGraph의 DAG 구조로 전환
**예상 소요 기간**: 2~3일

1. **상태(State) 정의 (`TypedDict`)**
   *   `AgentState`를 선언하여 `messages`, `current_mode`, `plan_status`, `validation_errors` 등 에이전트의 전역 상태를 멱등성 있게 관리.
2. **노드(Node) 및 엣지(Edge) 설계**
   *   **Nodes**: `llm_router`, `tool_execution`, `plan_generator`, `human_review_interrupt`, `rag_suggestion_reviewer`.
   *   **Edges**: 조건부 엣지(Conditional Edges)를 사용하여 "검증 실패 시 → 리뷰어 노드", "승인 필요 시 → 인터럽트 노드" 등으로 흐름 분기.
3. **Human-in-the-loop (HITL) 워크플로우 정교화**
   *   Plan 모드 작동 시 LangGraph의 `interrupt_before` 기능을 사용하여, 플랜 초안이 작성되면 엣지에서 실행을 멈추고 사용자 승인을 대기하는 로직 구현.

### 🥉 Step 3: TUI/CLI UX 고도화 및 슬래시 명령어 래핑
**목표**: OpenHarness 자산을 재활용하여 모니터링 대시보드를 강화하고 관리자 편의성 증대
**예상 소요 기간**: 2일

1. **TUI 아키텍처 재편성 (OpenHarness 상속)**
   *   `tui_main.py`를 `OpenHarnessTerminalApp`을 상속받는 구조로 래핑하여 디자인 안정성 확보.
   *   `PermissionScreen` 등 모달(Modal) 자산을 가져와 권한 승인 시 흐름 단절 없는 자연스러운 UI 제공.
2. **사이드바(Sidebar) 데이터 바인딩**
   *   `RBAC Level`, `토큰 소모량`, 현재 `AgentMode` 및 `PlanPhase`(LangGraph 상태 기반)를 TUI 좌측 패널에 실시간 렌더링.
3. **Theseus 전용 슬래시 명령어(Slash Commands) 구현**
   *   `/tools`: 현재 권한에서 사용 가능한 도구 목록을 `Rich` Table을 활용해 가독성 높게 표출.
   *   `/rbac <level>`: 테스트를 위한 권한 일시 변경 커맨드.
   *   `/validate <tool>`: 생성된 툴에 대해 수동으로 `Analysis`, `Execution` 검증을 강제 실행.
   *   `/kb <query>`: 에이전트를 통하지 않고, 프론트에서 직접 PostgreSQL 벡터 검색 쿼리를 쏘아 결과 열람.
   *   `/approve` / `/reject`: LangGraph의 HITL Interrupt 상태를 해제하여 그래프 실행을 재개(Resume)하는 브릿지 로직.
4. **CLI 자동완성 (`prompt_toolkit`)**
   *   TUI 구동이 불가능할 때 사용하는 CLI에서 위 슬래시 명령어들의 Tab 자동완성 기능 주입.

---

## 3. 결론 및 다음 액션 (Next Action)

이러한 로드맵에 따르면, 가장 먼저 **데이터베이스 연동 및 RAG 도구 구축(Step 1)**을 시작하는 것이 논리적입니다. 

개발 환경에 PostgreSQL 서버가 기동되어 있는지 점검하고, `theseus_engine/tools/basic_tools/` (또는 `rag/`) 디렉토리 하위에 **DB 커넥션 및 임베딩 헬퍼 함수들을 세팅하는 작업**부터 지시해주시면 즉각 구현에 돌입하겠습니다.
