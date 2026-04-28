# Theseus Agent Context (For In-context Learning)

현재까지 진행된 "Theseus B2B AI Agent Platform" 프로젝트의 핵심 진행 상황과 주요 아키텍처 변경점을 요약한 문서입니다. 
다음 세션에서 에이전트(혹은 AI 어시스턴트)가 이 문서를 컨텍스트로 읽으면, 즉시 기존 작업 맥락을 이어받을 수 있습니다.

---

## 1. 🚀 프로젝트 개요 (Project Overview)
- **목표**: 보안과 통제력이 극대화된 엔터프라이즈(B2B) 맞춤형 Python 코어 서버 구축 (OpenHarness 엔진 기반)
- **주요 기능**: RBAC(역할 기반 도구 권한), 동적 툴 생성(메타 툴링), 3-Mode 워크플로우(Ask/Agent/Plan), AST 기반 런타임 보안 검증

## 2. 🛠️ 최근 주요 작업 내용 (Recent Achievements)

### 2.1. 턴(Turn) 제한 해제 및 무한 루프 안정화
- **문제**: OpenHarness 엔진은 기본적으로 5회의 `max_turns` 제한을 가지며, 복잡한 코드 작성이나 에러 수정 시 루프를 초과하여 `Max Turns Exceeded` 에러를 발생시켰습니다.
- **해결**: `theseus_engine/app.py`를 신규 생성하여 `max_turns=30`으로 대폭 상향하고, Windows 비동기 이벤트 루프 버그(`WindowsProactorEventLoopPolicy`)를 해결하여 셸(bash) 명령과 파일 I/O를 안정화했습니다.

### 2.2. Human-in-the-loop (파일 조작 사전 승인) 구현
- **문제**: 에이전트가 자율적으로 파일을 쓰거나 편집하면, 시스템 파일이 훼손되거나 보안 취약점이 발생할 수 있었습니다.
- **해결**: OpenHarness 내장 기능인 `permission_prompt`를 오버라이딩(Overriding)하여, 에이전트가 `write_file`, `edit_file`, `bash` 등의 위험한 도구를 실행하기 직전 **콘솔에 "Allow this action? (y/N)" 승인을 묻는 비동기 대기 로직**을 추가했습니다.

### 2.3. 세션 메모리 (Multi-turn Session History) 기능 추가
- **문제**: 매번 스크립트를 재시작할 때마다 에이전트가 이전 대화 내용을 잃어버리는 현상(Amnesia)이 있었습니다.
- **해결**: `app.py` 실행 종료 시 `engine._messages`를 `.theseus_history.json`에 직렬화(Serialize)하여 저장하고, 다음 실행 시 자동으로 불러오는(Deserialize) 로직을 완성했습니다.
- **관련 명령어**: `/clear` 슬래시 커맨드를 입력하면 세션 메모리가 초기화됩니다.

---

## 3. 🎯 향후 작업 로드맵 (Next Steps for New Session)

새로운 세션을 시작하는 에이전트는 다음 작업들을 우선적으로 고려해야 합니다:

1. **Sandbox 연동 (최우선 과제)**
   - 현재 `ToolCreatorTool`이 만든 코드가 로컬 호스트 환경에서 `importlib`으로 즉시 로드되고 있습니다.
   - 이는 치명적인 보안 결함이므로, OpenHarness의 `openharness/sandbox/` 모듈을 활성화하거나 원격 환경(Lambda/DinD)에서 실행되도록 아키텍처를 개편해야 합니다.
2. **과금 전송 아키텍처 (Zero-Trust Billing)**
   - 토큰 과금을 메모리(`BackgroundTasks`)로 날리는 로직을 폐기하고, Redis Pub/Sub이나 Message Queue(RabbitMQ) 등 신뢰성 있는 비동기 파이프라인으로 구축해야 합니다.
3. **LangGraph State Machine 마이그레이션**
   - 현재 Python의 분기문(`if/elif`)으로 구현된 3-Mode 상태 머신을 LangGraph를 이용한 공식 워크플로우(Cyclic Graph) 구조로 전환해야 합니다.

## 4. 참고 문서
- `docs/roadmap/theseus_session_handover_guide.md` (자세한 인수인계 가이드)
- `docs/roadmap/pragmatic_engineering_strategy.md` (OpenHarness 미사용 기능 도입 전략)
- `usage.md` (에이전트 스크립트 실행 가이드)
