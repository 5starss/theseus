# 🚀 Theseus Core Server - 개발자 B 마일스톤 가이드 (Core Logic & AI Agent)

본 문서는 Theseus 플랫폼의 코어 AI 에이전트 시스템('뇌'와 '눈')을 설계하고 통제하는 핵심 포지션, **개발자 B**를 위한 구체적인 개발 마일스톤과 실무적 접근법을 안내합니다. 

개발자 A가 FastAPI 통신망과 인프라 뼈대를 잡는 동안, 개발자 B는 철저히 **로컬 환경(CLI 또는 단순 스크립트)**에서 코어 로직의 동작을 먼저 완성하는 것을 목표로 합니다.
특히, 내부 코어 엔진으로 통합될 **OpenHarness**의 구조(`QueryEngine`, `run_query`, `QueryContext`, `ToolRegistry`, `PermissionChecker` 등)를 적극 활용하고 확장해야 합니다.

> [!IMPORTANT]
> **OpenHarness 패키지 의존성 유의사항**
> 현재 참고 및 분석용으로 클론된 `OpenHarness` 폴더는 실제 프로젝트 소스코드 내부에 포함되지 않습니다. 실제 실행 환경에서 OpenHarness는 `pip install` 또는 `requirements.txt`/`uv` 등을 통해 외부에 설치되는 독립된 라이브러리 패키지로만 존재합니다. 따라서 모든 코어 모듈 래핑 및 확장 로직은 소스코드 직접 수정이 아닌 `import openharness...`와 같은 **외부 패키지 임포트 기반의 상속 및 확장 패턴**으로 작성되어야 함을 명심해야 합니다.


---

## 🎯 Phase 1: 관측성 확보 및 엔진 래핑 (가장 먼저 해야 할 일)
에이전트가 어떤 도구를 선택했고 왜 그런 판단을 했는지 추적할 수 없으면, 이후 진행될 프롬프트 엔지니어링과 검증기 개발은 미궁에 빠집니다. 따라서 시스템에 '눈'을 다는 작업을 0순위로 진행해야 합니다.

1. **LangSmith 환경 세팅**
   - 로컬 `.env`에 LangChain 관련 변수를 설정합니다.
   - 시스템 전반(`OpenHarness`의 `run_query` 내부 흐름 포함)에 LangSmith `@traceable` 데코레이터를 주입하여 에이전트 궤적을 완벽히 추적할 수 있도록 만듭니다.
2. **OpenHarness 래핑 테스트 (`QueryEngine` 활용)**
   - FastAPI 엔드포인트와 결합하기 전, `openharness.engine.query_engine.QueryEngine` 초기화 및 `submit_message` 제너레이터가 정상 작동하는지 로컬 스크립트로 테스트합니다.
3. **모의 스트리밍 출력 (`StreamEvent` 핸들링)**
   - 콘솔 상에서 `AssistantTextDelta`, `ToolExecutionStarted` 등 OpenHarness의 StreamEvent가 청크 단위로 잘 분리되어 나오는지 확인합니다.

---

## 🔐 Phase 2: 동적 권한 필터링 로직 (RBAC Loader) 구축 (✅ 완료)
엔진이 정상적으로 작동하고 로그가 찍히기 시작하면, 프롬프트에 주입될 도구(Tool)들을 동적으로 제어하는 모듈을 만듭니다. 이 단계가 완성되어야 컨텍스트 압축이 실현됩니다.

1. **더미 파일 스캔 및 `ToolRegistry` 연동 (✅ 완료)**
   - `custom_tools/` 폴더의 `.py` 파일들을 런타임에 읽어오는 `importlib` 스캐너 로직을 구현합니다.
   - 로드된 툴들을 OpenHarness의 `ToolRegistry`에 동적으로 등록(Register)하는 파이프라인을 작성합니다.
2. **커스텀 `PermissionChecker` 구현 (✅ 완료)**
   - OpenHarness의 기본 `PermissionChecker`를 확장/오버라이드하여 유저의 `user_level`과 툴의 `permission_level`을 런타임에 비교하는 필터링 로직을 완성합니다.
3. **Registry 단위 필터링 적용 (✅ 완료)**
   - 사용자 권한 레벨을 기반으로 `ToolRegistry`를 사전에 필터링하여 권한 밖의 툴은 LLM에 아예 노출되지 않도록(API 스키마에서 제외) 구현합니다.

---

## 🧠 Phase 3: 메타-툴링 상태 머신 및 프롬프트 엔지니어링 (✅ 완료)
가장 고도의 AI 모델링 감각이 필요한 단계입니다. 사용자의 자연어를 코드로 변환하는 과정의 흐름을 제어해야 합니다.

1. **상태 변수 정의 (✅ 완료)**
   - 에이전트의 상태를 `Planning`, `WAIT_FOR_REVIEW`, `Coding`으로 나눌 수 있는 State Machine 구조를 코드로 작성합니다.
2. **Planning 및 페르소나 프롬프트 작성 (✅ 완료)**
   - OpenHarness 패턴(Base + Environment + Persona)을 활용하여 시스템 프롬프트를 동적으로 변경하며 구현 계획서(Markdown 구조화)를 먼저 출력하도록 작성합니다.
3. **Human-in-the-loop(HITL) 및 툴 생성 자동화 (✅ 완료)**
   - 사용자의 피드백을 받아 계획을 승인(Approve)하고, 승인 시 LLM이 스스로 `create_tool`을 호출하여 Python 코드를 작성, 검증, 저장 후 런타임에 즉시 레지스트리에 주입하는 로직을 구현합니다.

---

## 🛡️ Phase 4: 세분화된 자동 검증기 4종 개발
코드가 생성되는 파이프라인이 구축되었다면, 마지막으로 AI가 만든 결과물을 검증하는 가드레일을 세웁니다. `src/validators/` 폴더에 다음 검증기들을 차례대로 구현합니다.

1. **Analysis 검증기 (가장 우선)**
   - `ast` 파싱을 활용하여 금지된 라이브러리(`os`, `subprocess`) 호출을 막고, 취약점을 방어하는 로직을 `PRE_TOOL_USE` 훅에 결합합니다.
2. **Execution & Query 검증기**
   - DB/API 호출 시 상태 변경(INSERT/UPDATE 등) 권한을 안전하게 판별합니다.
3. **Suggestion 검증기**
   - 생성된 코드를 기반으로 성능 개선과 Pythonic한 리팩토링 방안을 제시하는 프롬프트를 작성합니다.

---

## 💡 추가 개선 및 최적화 사항 (OpenHarness 연동 관점)

1. **효율적인 컨텍스트 메모리 관리 (Auto-Compaction)**
   - OpenHarness 엔진은 내부적으로 `AutoCompactState`와 임계값(`auto_compact_threshold_tokens`)을 통해 대화 내역을 자동 압축하는 기능을 지원합니다. 장기 세션에서 토큰 리밋 에러를 방지하기 위해 이 기능을 적극 활성화하고, 요약 프롬프트를 도메인에 맞게 커스텀해야 합니다.
2. **비동기 툴 병렬 실행의 안전성 확보**
   - `run_query` 함수 내부에서는 여러 개의 툴 호출(`tool_uses`)을 `asyncio.gather`를 통해 병렬로 처리합니다. 우리가 구현할 Custom BaseTool들이 I/O 바운드 작업 시 반드시 Non-blocking(`async/await`)으로 동작하도록 설계하여 엔진 전체의 병목을 막아야 합니다.
3. **비용 추적(Cost Tracker)의 연동**
   - `QueryEngine` 내에 포함된 `CostTracker`(`usage_snapshot`) 메타데이터를 LangSmith 또는 자체 로깅 시스템(FastAPI)과 연결하여, API 호출 비용을 실시간으로 추적 및 제한할 수 있는 구조를 마련해야 합니다.
4. **Hook 이벤트 기반의 이벤트 스트리밍 고도화**
   - OpenHarness의 `HookExecutor`를 활용하면 도구 사용 전후(`PRE_TOOL_USE`, `POST_TOOL_USE`)에 이벤트를 가로챌 수 있습니다. 이를 통해 클라이언트에게 실시간 진행 상태나 보안 경고를 전송하는 웹소켓(WebSocket) 이벤트 발송기를 구축하는 것을 추천합니다.

---

## 🤝 협업 포인트
Phase 4까지 로컬 스크립트 수준에서 모두 검증이 끝났다면, 개발자 A가 완성해 둔 FastAPI의 `/stream` 엔드포인트에 개발자 B의 로직(`QueryEngine` 래퍼)을 결합(Merge)하는 통합 테스트를 진행하시면 됩니다.
