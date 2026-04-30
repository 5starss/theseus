# Theseus 프로젝트 로드맵 종합 분석 보고서

**작성일**: 2026-04-28
**출처 문서**: `docs/roadmap/` 내 8개 제안서 및 가이드 문서 종합

본 문서는 Theseus B2B AI Agent Platform의 기존 로드맵 문서들을 종합하여, **현재 구현된 기능**, **구현 예정인 기능(미구현)**, 그리고 **구현하지 않기로 확정된(지양하는) 아키텍처**를 단일 뷰로 정리한 문서입니다.

---

## 1. 현재 구현 완료된 항목 (Implemented / MVP)

현재 Theseus 코어 시스템은 '우수한 PoC(Proof of Concept)' 수준의 핵심 도메인 로직을 검증한 상태입니다.

*   **상태 머신 기반 에이전트**: Ask, Agent, Plan 3-Mode 아키텍처 구현 완료.
*   **RBAC 동적 툴 필터링**: 사용자의 권한 레벨(`user_level`)에 따라 LLM 프롬프트에 주입되는 툴 레지스트리를 동적으로 필터링.
*   **메타-툴링 (Meta-Tooling)**: `ToolCreatorTool`을 통해 LLM이 직접 파이썬 코드를 작성하고 동적으로 툴을 등록하는 기능.
*   **다중 검증기 파이프라인 (Validators)**:
    *   `ToolValidator`: OpenHarness 규격 준수 여부 검증.
    *   `AnalysisValidator`: AST 정적 분석을 통해 18종 위험 모듈(`os`, `subprocess` 등) 및 파괴적 함수의 런타임 진입 차단.
    *   `ExecutionValidator` & `QueryValidator`: HTTP 상태 변경 및 DDL/DML, 인젝션 패턴 탐지 로직 (기초 구현).
*   **실용적 기술 부채 관리**: Gemini 400 에러 해결을 위한 `monkey_patches.py` 적용 (격리된 형태).
*   **관측성(Observability) 기반 마련**: LangSmith 트레이싱 파이프라인(`tracer.py`) 구축 완료.

---

## 2. 구현되지 않은 항목 (Not Implemented / Planned)

향후 B2B 엔터프라이즈 프로덕션 환경 도입을 위해 반드시 구현해야 할 로드맵 항목들입니다.

### 2.1. 인프라, 보안 및 아키텍처 (최우선 과제)
*   **원격 격리 실행 환경 (Remote Sandbox)**: 현재 로컬 메모리에서 실행되는 커스텀 툴 로직을 Docker-in-Docker(DinD) 또는 Serverless(Lambda) 기반으로 완벽히 격리. (OpenHarness `sandbox/` 활용 예정)
*   **DB 기반 툴 저장소**: 로컬 파일 시스템(`custom_tools/`) 의존을 탈피하고, 다중 워커 상태 동기화를 위해 커스텀 툴 코드와 메타데이터를 PostgreSQL 등에 저장.
*   **Zero-Trust 과금 큐(MQ)**: 현재 `BackgroundTasks`로 처리되는 토큰 과금 로직을 Redis Pub/Sub 또는 RabbitMQ를 도입하여 OOM 발생 시에도 데이터 유실 방지.
*   **어댑터(Adapter) 패턴 리팩토링**: `monkey_patches.py`의 기술 부채를 청산하고 OpenHarness의 `Hooks` 인터페이스를 활용하여 로깅/과금 로직 분리(Decoupling).

### 2.2. 오케스트레이션 및 워크플로우 (LangGraph & RAG)
*   **LangGraph 마이그레이션**: 하드코딩된 3-Mode 분기문을 LangGraph의 `StateGraph`(DAG) 구조로 전환.
*   **Human-in-the-loop (HITL) 고도화**: LangGraph의 Interrupt 기능을 활용하여 Plan 생성 후 사용자의 승인/수정 사이클 정교화.
*   **RAG 통합 및 지식 검증**: PostgreSQL(`pgvector`) 기반의 Vector DB를 구축하고, `search_knowledge_base` 도구를 RBAC 1레벨 툴로 캡슐화. 또한 RAG를 `SuggestionValidator`에 주입하여 사내 코딩 컨벤션 검증 수행.

### 2.3. 표준 툴셋 고도화 (Standard Toolset)
*   **시스템 제어 툴**: `bash` / `powershell` (샌드박스 완성 후 도입), 파일 입출력(`read_file`, `write_file`).
*   **엔터프라이즈 툴**: `query_enterprise_db` (읽기 전용 강제화 포함), `internal_api_call`.
*   **UX/UI 소통 툴**: 모호성 해결을 위한 `ask_user_question`, 비동기 알림을 위한 `send_notification`.
*   **안전망 툴**: 실패 시 복구를 위한 `rollback_state`.

### 2.4. 사용자 인터페이스 (TUI & CLI)
*   **Textual TUI 전환 (Priority 1)**: 단순 `input()` 환경을 OpenHarness의 `OpenHarnessTerminalApp`, `PermissionScreen`, `OutputRenderer` 등을 활용한 풍부한 TUI로 업그레이드 (사이드바, Plan 트리 시각화).
*   **prompt_toolkit CLI (Priority 2)**: TUI 사용이 불가능한 원격 서버 환경을 위한 Tab 자동완성, 명령어 탐색 기능 강화.

---

## 3. 구현하지 않기로 결정된 항목 (Decided Against / Anti-patterns)

프로젝트의 안정성, 보안, 그리고 실용성을 위해 명시적으로 배제되거나 지양된 항목들입니다.

1.  **동적 생성 툴의 로컬 메인 서버 실행 (절대 금지)**
    *   에이전트가 만든 코드를 FastAPI 워커 내에서 `importlib`으로 실행하는 것은 보안에 매우 취약하므로 격리 환경 도입 전까지는 제한적으로만 사용하며, 최종 아키텍처에서는 전면 폐기.
2.  **동적 의존성 패키지 설치 (`pip install`)**
    *   LLM이 생성한 코드 실행을 위해 메인 서버에 런타임으로 서드파티 패키지를 설치하는 행위는 인프라 파괴 행위로 간주하여 구현하지 않음. (사전 빌드된 도커 베이스 이미지로 대체)
3.  **컴파일 언어(Java/C++) 환경에서의 메타-툴링 직접 구현**
    *   Java의 동적 클래스 로딩이나 C++ 동적 라이브러리 링크를 통한 에이전트 툴 로딩은 OOM 및 코어 덤프 위험으로 인해 지양. 메인 서버가 컴파일 언어여도 동적 툴은 Python/WASM 등으로 격리 실행(Polyglot).
4.  **OpenHarness 코어 래퍼(Wrapper) 완벽 구축 (현재 유예)**
    *   MVP 단계에서 너무 거대한 엔진 래퍼를 설계하는 오버엔지니어링은 지양. 실용성을 위해 당분간은 몽키패치를 격리된 상태로 유지하고 코어 도메인 논리에 집중.
5.  **TUI/UI 시스템의 밑바닥부터 자체 개발 (Re-inventing the wheel)**
    *   프론트엔드를 처음부터 짜는 대신 OpenHarness에 내장된 Textual 자산 및 React/Ink 코드를 최대한 재활용하여 리소스를 절감.
6.  **`OpenHarnessTerminalApp`의 무분별한 상속**
    *   해당 클래스가 불필요한 모듈(MCP 등)까지 자동 초기화하는 부작용을 피하기 위해, 당분간은 통째로 상속받기보다는 `OutputRenderer`와 모달(`PermissionScreen`)만 부분 임포트하여 사용하기로 결정.
