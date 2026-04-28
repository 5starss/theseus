# Theseus 에이전트 오케스트레이션 고도화 명세서: LangGraph, LangSmith, RAG 통합

> **작성일**: 2026-04-27
> **작성자**: Developer B (AI Agent & Tooling Engineer)
> **대상**: Theseus 엔진 v2.0 아키텍처 개편 로드맵

---

## 1. 개요 (Executive Summary)

현재 Theseus 엔진은 OpenHarness 코어 위에서 동작하며, RBAC 권한 제어, Pydantic 기반의 구조화된 플래닝, 그리고 강력한 AST 기반의 정적 방어망 체계를 갖추는 데 성공했습니다. 
하지만 단순 `while` 루프 기반의 상태 머신과 한정된 컨텍스트 윈도우는, 더 복잡한 엔터프라이즈 워크플로우를 처리하고 지식 기반(Knowledge Base)을 활용하기에 확장성의 한계를 지닙니다.

본 명세서는 현재의 시스템을 **LangGraph 기반의 DAG(방향성 비순환 그래프) 오케스트레이터로 마이그레이션**하고, **LangSmith를 통한 가시성 확보**, 그리고 **RAG 기반 지식 검증 및 도구 주입 체계**를 통합하는 구체적인 아키텍처를 제안합니다.

---

## 2. 아키텍처 마이그레이션 방안

### 2.1 엔진 연동 및 관측성 (LangGraph & LangSmith)

기존 `TheseusStateMachine`과 `OpenHarness QueryEngine`의 제너레이터 루프를 LangGraph의 `StateGraph` 구조로 전면 개편합니다.

#### 1) LangSmith Traceability 주입
* **목표**: 에이전트의 사고 흐름(CoT), 토큰 소모량, 레이턴시, 툴 호출 인자 및 결과를 완벽하게 로깅.
* **구현 방식**:
    * 환경 변수에 `LANGCHAIN_TRACING_V2=true` 및 `LANGCHAIN_API_KEY` 설정.
    * 생성된 도구의 `execute` 메서드와 `ToolValidator` 로직, 메인 루팅 노드에 `@traceable` 데코레이터를 부착하여 중앙 대시보드와 동기화.

#### 2) LangGraph 기반 상태(State) 관리
* **목표**: `state.py`의 전역/싱글톤 상태 관리를 멱등성(Idempotency)이 보장되는 TypedDict 기반 그래프 상태로 전환.
* **구현 방식**:
    ```python
    from langsmith import traceable
    from langgraph.graph import StateGraph, END
    from typing import TypedDict, Annotated, List

    class AgentState(TypedDict):
        messages: Annotated[list, add_messages]
        mode: str # Ask, Agent, Plan
        current_plan: dict
        user_level: int
        validation_errors: List[str]

    @traceable(run_type="tool", name="agent_decision_node")
    def agent_node(state: AgentState):
        # LLM 호출 및 툴 선택 로직 라우팅
        pass

    workflow = StateGraph(AgentState)
    workflow.add_node("agent", agent_node)
    workflow.add_node("tools", tool_execution_node)
    # ... Conditional Edge를 통한 루핑 및 종료
    ```

---

### 2.2 메타-툴링 파이프라인 (Interactive Planning with LangGraph)

기존 파이프라인(Plan -> WaitForReview -> Executing)의 사용자 개입(Human-in-the-loop) 과정을 LangGraph의 **Interrupt** 기능으로 세련되게 제어합니다.

* **Planning Node**: `StructuredPlanner`를 호출하여 Pydantic JSON 기반 플랜 생성.
* **Human Review Node (Interrupt)**: 
    * `interrupt_before=["coding_node"]` 기능을 사용하여 그래프 흐름을 중지하고 프론트엔드로 플랜을 반환.
    * 사용자가 `approve` 또는 부분 수정(`edit`)을 반영하여 상태(State)를 업데이트하면 실행(Resume)됨.
* **Coding & Validation Node**: 승인 시 `ToolCreatorTool`이 실행되고, 즉시 정적 검증기 노드로 제어권이 넘어감. 위반 사항 발생 시 `agent_node`로 오류 메시지와 함께 피드백 사이클 생성.

---

### 2.3 지식 기반 검증기 및 RAG 통합 (RAG + Evaluation Nodes)

AST 검사를 넘어선 논리적/비즈니스적 검증을 위해 RAG 기반의 Suggestion Node를 도입합니다.

* **Analysis 검증기 (현재 구현 완료)**: AST 파싱을 통해 `os`, `shutil`, `subprocess` 등 파괴적 라이브러리 사용을 차단 (Dead-end 라우팅).
* **Suggestion 검증기 (RAG 기반 품질 향상)**:
    * **맥락 주입**: 코드 생성 전, Vector DB(ChromaDB 등)를 조회하여 사내 코딩 컨벤션, 내부 ORM 사용법, 기존 유사 도구 템플릿을 RAG로 가져옵니다.
    * **LLM 리뷰**: 생성된 코드와 RAG 컨텍스트를 비교하여, "사내 DB 커넥터 패턴에 맞지 않음" 등의 지적과 함께 리팩토링된 코드를 제안하는 피드백 루프 노드를 추가합니다.

---

### 2.4 동적 권한 필터링 기반 RAG 도구화 (RBAC Loader)

모든 대화에 RAG를 강제하는 대신, RAG 자체를 **보안이 적용된 도구(Tool)** 로 캡슐화합니다. (Tool Schema Overflow 방지)

* **지식 검색 도구(`search_knowledge_base`)**:
    * Vector Store에 연결된 Retriever Tool을 생성하여 에이전트가 "사내 규정이 궁금할 때"만 능동적으로 호출하도록 설계.
* **RBAC 연동 체계**:
    * RAG 도구에 `permission_level`을 부여 (예: 재무 데이터 RAG는 `level=3`, 일반 문서 RAG는 `level=1`).
    * 현재 구현된 `build_filtered_registry`를 통과해야만 프롬프트 스키마에 RAG 도구가 노출되므로, 권한 없는 사용자의 프롬프트 비용을 절감하고 보안 사고를 차단.

---

## 3. 구현 우선순위 및 로드맵 (Action Plan)

1. **[Phase 1] LangSmith 관측성 통합 (최우선)**
   * `LANGCHAIN_API_KEY` 발급 및 파이프라인 주요 노드에 `@traceable` 부착. 디버깅 및 분석 인프라 확보.
2. **[Phase 2] LangGraph State Machine 마이그레이션**
   * 기존 루프 엔진을 분해하여 `AgentState`와 `StateGraph` 구조로 포팅. 기존 RBAC 도구 레지스트리와 테스트 스위트가 LangGraph에서 동일하게 작동하는지 검증.
3. **[Phase 3] Vector DB 구축 및 RAG 툴 캡슐화**
   * 사내 문서용 경량 Vector Store 세팅. `search_knowledge_base` 도구를 작성하고 `permission_level` 맵에 등록. 에이전트가 자율적으로 도구를 활용하는지 관측.
4. **[Phase 4] RAG 기반 Suggestion 검증기 연동**
   * 메타 툴링(Tool Creator) 과정에 Vector DB 컨텍스트를 주입하여 퀄리티 컨트롤 및 엔터프라이즈 컨벤션 강제.
