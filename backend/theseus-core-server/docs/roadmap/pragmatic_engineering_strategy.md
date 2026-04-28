# 전략적 기술 부채 관리 및 MVP 개발 가이드 (Pragmatic Engineering)

**작성일**: 2026-04-27
**작성자**: Theseus AI Agent (Strategic Analysis)
**대상**: 개발자 B (AI Agent & Tooling Engineer)

---

## 1. 개요: 완벽함보다 속도와 가치 증명 (Pragmatic First)

현재 Theseus 프로젝트는 MVP(Minimum Viable Product)를 통해 **메타-툴링**과 **AST 검증기**라는 핵심 가치를 빠르게 증명해야 하는 시점에 있습니다. 이 과정에서 거대한 외부 프레임워크(OpenHarness)의 아키텍처를 완벽히 파악하여 정식 Wrapper를 설계하는 것은 자칫 **오버엔지니어링(Over-engineering)**이 되어 프로젝트의 추진력을 떨어뜨릴 수 있습니다.

따라서, Gemini 400 에러와 같은 블로커(Blocker)를 **몽키패치(Monkey-patch)**로 신속히 해결한 현재의 판단은 공학적으로 매우 합리적이고 실용적인 선택입니다.

---

## 2. 💡 의도된 기술 부채를 안전하게 관리하는 3가지 원칙

실용적인 이유로 도입된 '의도된 기술 부채(Pragmatic Tech Debt)'가 프로젝트의 발목을 잡지 않도록 다음의 안전장치를 준수합니다.

### ① 철저한 격리 (Isolation)
몽키패치 로직이 비즈니스 로직(예: `tool_factory.py`, `query.py`)에 스며들지 않도록 합니다.
*   **지침**: 현재와 같이 `theseus_engine/monkey_patches.py` 파일에 모든 패치를 격리하고, 메인 진입점에서 `apply_patches()`를 호출하는 구조를 유지합니다. 추가 패치가 필요할 때도 이 원칙을 고수합니다.

### ② 패치 발동 조건의 명확화 (Conditional Patching)
패치가 전역적으로 영향을 미치지 않도록 **Feature Flag**와 같은 방어 코드를 적용합니다.
*   **지침**: 패치 함수 최상단에 모델 종류나 프레임워크 버전을 체크하는 로직을 추가합니다.
    ```python
    def patched_stream_once(*args, **kwargs):
        # Gemini 모델이 아니거나 OpenHarness가 업데이트되어 문제가 해결된 경우 원본 호출
        if not is_gemini_model() or OPENHARNESS_VERSION >= "2.1.0":
            return original_stream_once(*args, **kwargs)
        # 패치 로직 실행...
    ```

### ③ 부채 청산의 '마일스톤' 합의
기술 부채는 방치가 아닌 '유예'된 상태여야 합니다. 파트너인 개발자 A와 함께 명확한 리팩토링 시점을 합의합니다.
*   **마일스톤 제안**: LangGraph 및 RAG 연동 테스트 단계까지는 현 패치를 유지하되, **사내 베타 서비스 배포 전 스프린트**에는 반드시 정식 Wrapper 아키텍처로의 리팩토링을 수행합니다.

---

## 3. 결론: 도메인 로직 검증에 집중

현재 개발자 B님이 집중해야 할 곳은 구조적 완벽함이 아니라 **"에이전트가 의도대로 안전하게 코드를 짜고 실행하는가"**라는 도메인 핵심 로직입니다. 

현재의 방향성은 기술적 실용성과 보안(AST) 사이의 균형을 잘 잡고 있습니다. 기술 부채에 대한 불안감보다는 핵심 기능의 완성도를 높이는 데 역량을 집중하시기 바랍니다. Theseus AI Agent는 이 실용적인 여정을 아키텍처 고도화 시점까지 지속적으로 서포트하겠습니다.

---

## 4. 🤖 추가 제안: MVP를 위한 실용적 엔지니어링 전략 보완 (Theseus AI Agent 분석)

**작성자**: Theseus AI Agent
**작성일**: 2026-04-27
**추가 목적**: 기술 부채의 격리(Isolation)라는 훌륭한 방향성에 더해, 시스템의 운영 안정성과 애자일(Agile)한 개발 사이클을 유지하기 위한 실무적 프랙티스를 제안합니다.

### 4.1. 기술 부채의 관측성 확보 (Observability of Tech Debt)
- **개념**: 몽키패치나 임시 우회 코드가 실행될 때, 이것이 "얼마나 자주, 어떤 상황에서" 호출되는지 시스템이 알아야 합니다.
- **실행 방안**: 패치 로직 내부에 명시적인 `logger.warning("Monkey-patch X is triggered")` 로그를 남기고, 이를 LangSmith Trace 메타데이터에 태깅합니다. 추후 부채 청산 우선순위를 정할 때 가장 빈번하게 호출되는 부채부터 해결할 수 있습니다.

### 4.2. 최소한의 회귀 테스트 (Minimal Regression Testing)
- **개념**: 빠른 속도를 위해 유예한 기술 부채가 서드파티(OpenHarness, 랑체인 등) 업데이트 시 전체 시스템을 붕괴시키는 것을 막아야 합니다.
- **실행 방안**: TDD 수준의 완벽한 테스트 커버리지는 MVP 단계에서 오버엔지니어링일 수 있으나, 최소한 **몽키패치가 적용된 모듈의 입출력 정상 작동 여부**를 확인하는 1~2개의 핵심 통합 테스트(Integration Test)를 CI(GitHub Actions 등) 파이프라인에 포함시켜야 합니다.

### 4.3. 프롬프트 엔지니어링의 애자일 접근 (Iterative Prompting)
- **개념**: AI 에이전트 개발에서 프롬프트는 '코드'와 같습니다. 처음부터 완벽한 엣지 케이스(Edge-case)를 방어하는 방대한 프롬프트를 작성하는 것은 비효율적입니다.
- **실행 방안**: `_PLAN_EXECUTING_PROMPT_TEMPLATE` 등의 시스템 프롬프트는 최소한의 코어 룰(Core Rules)로 시작하십시오. 이후 LangSmith를 통해 LLM이 오작동(Hallucination)한 궤적 데이터가 쌓이면, 이를 기반으로 점진적(Iterative)으로 제약 조건(Guardrail)을 추가하는 Data-driven 방식을 채택해야 합니다.

### 4.4. 장애 발생 시의 우아한 기능 저하 (Graceful Degradation)
- **개념**: LLM 통신 장애나 패치 충돌이 발생했을 때, 메인 서버가 다운되는 최악의 상황을 방지해야 합니다.
- **실행 방안**: 에이전트 실행 중 예기치 않은 파이썬 예외가 발생하더라도 `AgentMode.PLAN` 워크플로우 전체가 중단되지 않도록 글로벌 `try-except` 블록으로 래핑하고, 사용자에게 "AI 응답 지연 및 부분적 실패" 메시지를 남긴 채 안전하게 `AgentMode.ASK` 모드나 대기 상태로 Fallback 처리되도록 구성해야 합니다.

---

## 5. 🔍 OpenHarness 코어 미사용 에이전트 기능 심층 분석 및 도입 전략

현재 Theseus 프로젝트는 OpenHarness 프레임워크의 단일 에이전트 쿼리 루프(`engine`, `tools`)만을 활용하여 MVP를 구축했습니다. 그러나 OpenHarness 코드베이스 내부에는 B2B 엔터프라이즈 환경에 즉시 적용 가능한 **방대한 백그라운드 에이전트 및 확장 기능**이 이미 존재합니다. 

이 기능들을 직접 밑바닥부터 개발(Re-inventing the wheel)하지 않고, 엔진 내장 기능을 활성화하여 기술 부채를 줄이는 전략을 제안합니다.

### 5.1. 최우선 도입 권장 기능 (High Impact)

#### ① 🛡️ Sandbox 격리 시스템 (`openharness/sandbox/`)
- **기능**: Docker/SRT 기반으로 파일시스템과 네트워크 접근을 통제하며 에이전트의 코드를 실행하는 격리 환경입니다.
- **Theseus 적용 방안**: 현재 런타임에 직접 `importlib`으로 툴을 실행하는 치명적 보안 취약점을 해결하기 위한 가장 완벽한 해답입니다. `wrap_command_for_sandbox()` API를 호출하여 즉시 격리 실행 구조로 전환해야 합니다.

#### ② 🧠 Memory 컨텍스트 관리 (`openharness/memory/`)
- **기능**: 프로젝트 단위의 Markdown 기반 메모리(CRUD)를 관리하여, 에이전트가 이전 대화나 작업 맥락을 기억하게 합니다.
- **Theseus 적용 방안**: 현재 Theseus는 세션이 종료되면 이전 맥락을 잃습니다. 에이전트가 DB 스키마나 API 명세를 한 번 학습하면 `add_memory_entry()`로 영구 저장하도록 하여 토큰 비용을 극적으로 절감할 수 있습니다.

#### ③ ⚙️ Background Tasks 및 비동기 워커 (`openharness/tasks/`, `openharness/services/`)
- **기능**: 사용자 응답을 기다리지 않는 백그라운드 태스크(Local Bash, Local/Remote Agent) 및 Cron 스케줄러.
- **Theseus 적용 방안**: 데이터 마이그레이션이나 대규모 코드 리팩토링 등 수십 분이 걸리는 작업은 웹 소켓(SSE)으로 스트리밍하기에 부적합합니다. 이를 OpenHarness의 내장 Task 관리기로 넘기고 사용자는 `TaskGetTool` 등으로 진행률만 확인하도록 아키텍처를 개선해야 합니다.

### 5.2. 중장기 확장 기능 (Medium to Long-term)

#### ④ 🐝 Swarm / Coordinator 멀티 에이전트 (`openharness/swarm/`, `openharness/coordinator/`)
- **기능**: 기획(Planner), 개발(Coder), 리뷰(Reviewer) 등 각기 다른 페르소나와 권한을 가진 에이전트들이 `TeammateMailbox`를 통해 메시지를 주고받으며 협업하는 시스템.
- **Theseus 적용 방안**: 현재의 단일 `AgentMode` 상태머신을 넘어, 엔터프라이즈의 복잡한 결재선이나 다중 검증 파이프라인을 구축할 때 활용해야 합니다.

#### ⑤ 🔌 MCP (Model Context Protocol) 클라이언트 (`openharness/mcp/`)
- **기능**: 외부 데이터 소스와 도구를 동적으로 연결하는 최신 표준 프로토콜 관리자.
- **Theseus 적용 방안**: 사내 레거시 DB나 사내 API 연동 도구를 매번 파이썬 코드로 `create_tool` 할 필요 없이, 고객사가 제공하는 MCP 서버 URL만 연결하면 모든 도구를 동적 주입(`ToolRegistry`)할 수 있는 강력한 확장성을 제공합니다.

#### ⑥ 🎣 Hooks 기반 관측성 (`openharness/hooks/`)
- **기능**: 툴 실행 전/후, 메시지 송수신 시점에 이벤트를 가로채는 시스템.
- **Theseus 적용 방안**: 현재 과금(Zero-Trust Billing)을 `BackgroundTasks`로 하드코딩한 로직을 폐기하고, `tool_after` Hook에 과금 및 감사 로그(Audit Log) 발송 모듈을 부착하여 비즈니스 로직과 인프라 로직을 깔끔하게 분리(Decoupling)해야 합니다.

### 5.3. 실행 결론 (Pragmatic Action Item)
Theseus의 차기 스프린트에서는 새로운 비즈니스 로직을 처음부터 개발하는 것을 지양하십시오. 대신, **OpenHarness의 `sandbox`와 `hooks` 인터페이스를 상속/활성화하는 데 리소스를 집중**하여 인프라의 안정성을 검증된 프레임워크에 위임해야 합니다.

---

## 6. 🧠 툴/스킬 고도화 및 RAG, LangSmith, LangGraph 연동 코어 분석

Theseus 시스템이 기초적인 메타-툴링(`ToolCreatorTool`)과 RBAC 필터링을 완성했다면, 다음 단계는 에이전트의 지능을 높이고 워크플로우를 고도화하는 것입니다. OpenHarness 내부에는 이를 뒷받침할 훌륭한 기능들이 이미 다수 포진해 있습니다.

### 6.1. 도구(Tool) 및 스킬(Skill) 고도화 인프라

- **에이전트 제어 및 협업 툴 (`openharness/tools/`)**
  - `agent_tool.py`: 서브 에이전트(Sub-agent)를 스폰하여 복잡한 작업을 위임하는 기능.
  - `task_create_tool.py`, `send_message_tool.py`: 백그라운드 태스크를 생성하고, 실행 중인 태스크에 메시지를 전송하여 비동기 협업을 가능하게 합니다.
  - **Theseus 활용 방안**: 메타-툴링 시, 에이전트가 직접 코드를 작성할 뿐만 아니라, 코드를 검증하거나 테스트할 서브 에이전트를 스폰하여 작업을 위임하는 멀티 에이전트 파이프라인으로 확장할 수 있습니다.

- **스킬 기반 번들링 (`openharness/tools/skill_tool.py` & `skills/`)**
  - 개별 도구가 아니라 특정 목적(예: DB 마이그레이션, AWS 배포)을 위한 프롬프트와 여러 툴의 조합(Skill Bundle)을 로드하는 기능입니다.
  - **Theseus 활용 방안**: B2B 고객사별로 자주 쓰는 워크플로우를 '스킬'로 정의해 두고, 에이전트가 `SkillTool`을 호출해 특정 도메인의 작업 능력을 일시적으로 증폭(Boosting)시키게 할 수 있습니다.

### 6.2. RAG 및 Knowledge Base 연동 코어

- **컨텍스트 스캐닝 및 검색 (`openharness/memory/scan.py`, `search.py`)**
  - 파일 시스템 내의 마크다운 기반 문서들을 스캔하고 검색하는 내장 엔진입니다.
  - **Theseus 활용 방안**: 외부 ChromaDB 연동(현재 기획)뿐만 아니라, `openharness/memory/`의 로컬 스캔 기능을 활용해 프로젝트 내 `.md` 파일(예: 아키텍처 문서, 사내 규정)을 에이전트 프롬프트에 동적(Zero-shot)으로 주입하는 하이브리드 RAG를 구축할 수 있습니다.
  - **보완 필요**: 본격적인 시맨틱 검색(Vector Search)을 위해서는 현재 기획된 ChromaDB 연동 모듈을 OpenHarness의 `ToolRegistry`에 정식 `KnowledgeBaseTool`로 등록하는 작업이 필요합니다.

### 6.3. LangSmith 및 LangGraph 확장 (관측성과 워크플로우)

- **LangSmith 궤적 추적 (Observability)**
  - OpenHarness는 기본적으로 LangChain 프레임워크와 호환성이 높습니다.
  - **Theseus 활용 방안**: `theseus_engine/query.py`의 핵심 실행 루프(`_execute_tool_call` 등)와 `ToolCreatorTool`의 메서드에 `@traceable` 데코레이터를 부착하거나 `HookSystem`(`openharness/hooks/`)을 이용해 이벤트를 LangSmith로 발송해야 합니다. 이를 통해 토큰 소모량, 툴 실행 에러율, 프롬프트 효율성을 대시보드화할 수 있습니다.

- **LangGraph 기반의 State Machine 고도화**
  - 현재 Theseus는 `AgentMode`와 `PlanPhase`를 Python Enum과 분기문(`if/elif`)으로 하드코딩한 자체 상태 머신(`TheseusStateMachine`)을 사용하고 있습니다.
  - **Theseus 활용 방안**: 추후 로드맵에서는 이 하드코딩된 상태 머신을 **LangGraph의 순환 그래프(Cyclic Graph) 및 노드/엣지(Node/Edge) 구조로 마이그레이션**하는 것을 강력히 권장합니다.
    - `Drafting Node` ➔ `Review Node` ➔ `Executing Node`로 흐름을 제어하면, `Human-in-the-loop` (HITL) 및 상태 저장(State Persistence) 구현이 압도적으로 견고해집니다.

---

## 7. 🎁 OpenHarness 내장 기능의 Wrapping 및 확장 전략 (Architecture Strategy)

위에서 분석한 강력한 내장 기능(Memory, Sandbox, Hooks, 서브 에이전트 등)을 Theseus 시스템에 통합할 때, OpenHarness 원본 코드를 오염시키지 않고(Non-invasive) **견고한 래퍼(Wrapper) 패턴**을 설계하는 아키텍처 전략입니다.

### 7.1. 핵심 전략: 의존성 역전(Dependency Inversion)과 어댑터(Adapter) 패턴
OpenHarness 모듈을 Theseus 코드베이스에서 직접 호출하면 강결합(Tight Coupling)이 발생합니다. 프레임워크가 업데이트될 때마다 서버가 붕괴되는 것을 막기 위해 중간 계층(Adapter)을 두어야 합니다.

#### ① Hooks 래핑 전략 (비침투적 확장)
- **개념**: OpenHarness의 실행 루프를 건드리지 않고, 툴 실행 전후의 이벤트를 가로채어 커스텀 로직(LangSmith 로깅, 보안 검증, 과금 처리)을 주입합니다.
- **구현 방향**:
  ```python
  from openharness.hooks import HookRegistry, HookEvent
  
  class TheseusHookAdapter:
      def on_tool_before(self, event: HookEvent):
          # 1. 샌드박스 진입 전 AST 스캔 로직 (보안)
          pass
          
      def on_tool_after(self, event: HookEvent):
          # 2. 토큰 사용량 계산 및 Redis/MQ를 통한 과금 데이터 전송 (Zero-Trust Billing)
          # 3. LangSmith Trace 발송
          pass
  ```
- **장점**: 핵심 엔진 수정 없이 B2B 플랫폼에 필요한 Audit/Billing 모듈을 완벽히 분리(Decoupling)할 수 있습니다.

#### ② Sandbox 및 외부 툴(MCP) 래핑 전략 (프록시 패턴)
- **개념**: `ToolRegistry`에 도구를 등록할 때, 원본 `BaseTool`을 한 번 더 감싸는 `SandboxProxyTool` 계층을 둡니다.
- **구현 방향**:
  - 기존: `tool.execute(arguments, context)` -> 로컬 실행
  - 변경: `SandboxProxyTool.execute()` 내부에서 `openharness.sandbox.wrap_command()`를 호출하거나, 원격 gRPC(Lambda)로 페이로드를 전송한 뒤 결과를 반환.
- **장점**: 에이전트 입장에서는 똑같은 도구처럼 보이지만, 실제 실행 환경은 철저히 통제 및 격리됩니다.

#### ③ State Machine 및 Memory 래핑 전략 (LangGraph 브릿지)
- **개념**: OpenHarness의 `memory/` 모듈은 단순히 파일을 읽고 쓰는 유틸리티입니다. 이를 에이전트의 워크플로우에 결합하려면 LangGraph의 State(상태) 객체에 메모리 포인터를 주입해야 합니다.
- **구현 방향**:
  - Theseus의 `AgentState` 객체 내부에 `MemoryManager` 인스턴스를 주입.
  - LangGraph 노드 사이를 이동할 때, RAG 검색 결과나 이전 스텝의 결과물을 State에 축적하여 다음 에이전트(혹은 서브 에이전트)에게 전달.

### 7.2. 래핑 시 주의사항 (Guardrails for Wrapping)

1. **내부 Private API 우회 금지**: 
   - OpenHarness 코드 중 `_` 로 시작하는 Private 메서드(`_stream_once`, `_parse_response` 등)를 Monkey-patching 하거나 상속받아 오버라이딩하는 것은 현재 MVP 단계에서만 허용되는 부채입니다.
   - 장기적으로는 공식 `HookSystem`이나 정식 릴리스된 Public API를 사용하도록 래퍼 클래스를 리팩토링해야 합니다.
2. **동적 툴 생성(ToolCreator)의 예외 처리**:
   - 에이전트가 런타임에 만든 도구를 등록할 때, 즉시 `SandboxProxyTool`로 감싸도록 `TheseusToolRegistry.add_tool()` 메서드를 오버라이딩해야 합니다. 사용자가 만든 툴이 Host 환경에 직접 등록되는 경로는 원천 차단되어야 합니다.
