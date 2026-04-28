# Theseus Session Handover Guide (세션 인수인계 가이드)

**작성자**: Theseus AI Agent
**작성일**: 2026-04-27
**문서 목적**: 다음 개발 세션(또는 다른 에이전트 인스턴스)에서 Theseus 프로젝트를 이어받을 때, 현재까지의 개발 맥락, 발견된 치명적 결함, 그리고 향후 집중해야 할 개선 로드맵을 즉각적으로 파악하기 위한 요약 문서입니다.

---

## 1. 프로젝트 현황 요약 (Project Status)
*   **프로젝트명**: Theseus (B2B AI Agent Platform Core)
*   **기술 스택**: Python 3.11, FastAPI, OpenHarness Engine, ChromaDB (예정)
*   **달성된 핵심 기능 (MVP)**:
    *   3-Mode 상태 머신 기반 에이전트 (Ask, Agent, Plan)
    *   RBAC(Role-Based Access Control)를 통한 권한별 도구 동적 필터링
    *   `ToolCreatorTool`을 이용한 파이썬 도구 동적 생성 및 등록 (메타-툴링)
    *   `ToolValidator`를 통한 AST 기반 18종 위험 모듈(subprocess, os 등) 런타임 진입 차단
    *   Gemini 400 에러 및 스트리밍 버그 수정을 위한 몽키패치(`monkey_patches.py`) 적용

## 2. 🚨 치명적 아키텍처 결함 및 보안 리스크 (Critical Risks)
다음 개발 세션에서는 **새로운 기능 추가를 전면 중단하고, 아래의 3대 리스크를 우선 해결**해야 합니다.

1.  **샌드박스 격리 부재 (가장 심각함)**:
    *   *문제*: 에이전트가 만든 커스텀 툴 코드가 메인 FastAPI 서버와 동일한 메모리 프로세스에서 실행됩니다. AST 검증은 리플렉션 공격을 막을 수 없어, 메인 서버 전체가 탈취되거나 다운될 수 있습니다.
    *   *대책*: OpenHarness 내부의 `sandbox/` 모듈을 활성화하거나, AWS Lambda/DinD 형태의 격리된 Remote Execution 구조로 전면 개편해야 합니다.
2.  **과금 데이터 증발 위험 (Zero-Trust Billing)**:
    *   *문제*: LLM 비용을 FastAPI의 메모리 기반 `BackgroundTasks`로 Spring Boot에 전송하고 있습니다. OOM이나 배포 시 과금 데이터가 영구 유실됩니다.
    *   *대책*: Redis Pub/Sub 또는 Message Queue(RabbitMQ)를 도입하여 비동기 트랜잭션의 신뢰성을 확보해야 합니다.
3.  **다중 워커 상태 동기화 및 몽키패칭 부채**:
    *   *문제*: 로컬 폴더(`custom_tools/`) 기반의 툴 로딩은 다중 워커 환경에서 인스턴스 간 상태 불일치를 유발하며, 엔진 몽키패칭은 라이브러리 업데이트 시 서버를 다운시킵니다.
    *   *대책*: 툴 코드와 메타데이터를 DB(PostgreSQL)에 저장하고, 엔진 래퍼(Adapter) 패턴으로 리팩토링해야 합니다.

## 3. 🔍 OpenHarness 내장 모듈 활용 전략 (Re-use Strategy)
바퀴를 다시 발명하지 마십시오. 엔진 내부에 이미 구현된 다음 모듈들을 적극 활용하여 기술 부채를 낮춰야 합니다.

*   **`openharness/sandbox/`**: 위 1번 리스크(격리 실행) 해결을 위한 최우선 도입 대상.
*   **`openharness/hooks/`**: `tool_before`, `tool_after` 이벤트를 가로채어 커스텀 로깅, 보안 스캔, LangSmith 트레이싱, MQ 기반 과금 전송 로직을 결합(Decoupling)할 때 사용.
*   **`openharness/memory/`**: 세션 간 대화 컨텍스트가 끊기는 현상을 방지하고, 프로젝트 관련 주요 맥락(아키텍처, 툴 이력)을 로컬 마크다운에 스캔/저장하는 경량 RAG 형태로 활용.
*   **`openharness/tasks/`**: SSE 스트리밍이 끊길 수 있는 장기 실행 작업(Long-running tasks)을 백그라운드 워커로 위임할 때 사용.

## 4. 🌐 타 언어(Java/C++)로의 확장 고려사항
만약 백엔드 메인 프레임워크가 Java나 C++로 전환될 경우, "에이전트가 코드를 짜고 즉시 실행한다"는 메타-툴링 기획은 치명적일 수 있습니다.
*   *방향성*: 메인 서버는 컴파일 언어로 단단하게 구축하되, 에이전트가 동적으로 생성하는 도구(Tool)는 **Python, JS, WASM** 스크립트 기반으로 샌드박스에서만 실행되도록 하는 이종(Polyglot) 아키텍처를 도입해야 합니다. 프롬프트 단계에서 빌드 체인과 예외 처리 제약을 매우 엄격하게 강제해야 합니다.

## 5. 다음 세션(Next Session) 시작 시 행동 강령
새 세션이 시작되면, 이 문서를 기반으로 다음 우선순위에 따라 작업을 시작하십시오.

1.  `theseus_session_handover_guide.md` 숙지
2.  `pragmatic_engineering_strategy.md` 의 7번 항목(Wrapping 전략)을 참고하여 기존 하드코딩된 로직 분리 설계
3.  `OpenHarness/src/openharness/sandbox/` 코드를 읽고 Theseus 엔진 런타임에 결합하는 파일럿 코드 작성
