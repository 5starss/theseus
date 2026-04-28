# Changelog

## [Unreleased] - 2026-04-24

### 🚀 Features (주요 구현 내용)

#### Session 6 (2026-04-27)

- **LLM API 통신 호환성 및 자동 복구(Auto-Recovery) 강화**:
  - **Gemini 3.1 Pro 도구 호출(`thought_signature` 누락) 400 에러 해결**:
    - 최신 Gemini 모델의 Function Calling 과정에서 발생하는 `thought_signature` 누락 현상을 해결하기 위해 `theseus_engine/monkey_patches.py` 신규 작성.
    - OpenHarness 패키지의 내부 코드를 오염시키지 않기 위해 런타임에 동적으로 `_stream_once` 제너레이터와 `_parse_assistant_response`, `_convert_assistant_message`를 가로채는(Monkey-patching) 방식으로 구현.
    - 스트리밍 조각(Chunk)을 수집할 때 무시되던 `extra_content`를 추출하여 보존한 뒤 다음 턴에 다시 전달함으로써 Gemini 환경 완벽 호환.
  - **API `ErrorEvent` 자가 복구 루프 구축**:
    - `test_phase2_3.py` 루프에서 API 통신 단절이나 기타 예외 상황 시 시스템이 종료되는 문제 개선.
    - `Exceeded maximum turn limit` 방어 메커니즘과 동일한 사상으로, API 레벨의 예외(`ErrorEvent`) 발생 시 에러 내용을 LLM에게 다시 피드백(`System Error Encountered...`)하여 자가 치유를 시도하도록 로직 추가.

#### Session 5 (2026-04-27)

- **에이전트 보안 체계(Defense in Depth) 강화 및 UX 개선**:
  - **1차 방어 (Shift-Left / Prompt Guardrail)**: `structured_planner.py`의 `_STRUCTURED_PLAN_SYSTEM_PROMPT`에 `Security Policy` 제약 추가. 파일/폴더 삭제, 악성 모듈(`subprocess`, `shutil`) 사용 요청 시 `Security Policy Violation` 블록만을 반환하도록 플래너 가이드.
  - **불필요한 리뷰(WaitForReview) 스킵 로직**: 1차 방어에 의해 `Security Policy Violation`이 발생한 경우, 사용자에게 승인(Approve) 여부를 묻는 잉여 단계를 생략하고 즉각 경고 출력 후 Agent 모드로 자동 튕겨내도록(Abort) `test_phase2_3.py` 루프 고도화.
  - **2차 방어 (Hard Block / AST 정적 분석)**: `ToolValidator._check_security_violations` 메서드 신규 추가. 파이썬 `ast` 모듈을 이용해 런타임 진입 직전, 시스템 파괴 위험이 있는 모듈(`subprocess`, `shutil`, `socket` 등 8종)과 함수(`os.system`, `eval`, `rmtree` 등 18종) 호출을 원천 차단.

- **Windows 비동기 셸 실행(Subprocess) 버그 수정**:
  - `test_phase2_3.py`에서 `bash` 툴이 `NotImplementedError`를 발생시키던 문제 원인 파악 및 해결.
  - OpenHarness의 `get_platform()`을 적용하여 Windows 환경일 경우, 하위 프로세스를 지원하는 `asyncio.WindowsProactorEventLoopPolicy()`가 동적으로 올바르게 설정되도록 로직 변경.

#### Session 4 (2026-04-27)

- **3대 도구 시스템 문제 전면 해결**:
  - **문제 1 — Agent 모드 `create_tool` 남발 방지**:
    - `_BASE_SYSTEM_PROMPT`에서 `create_tool` 유도 지침을 완전히 분리하여 `_PLAN_EXECUTING_PROMPT_TEMPLATE`로 이전.
    - `_AGENT_PROMPT`에 `"Do NOT create new tools"` 명시적 금지 문구 추가.
    - `build_filtered_registry`에 `exclude_tools` 파라미터 추가, Plan Executing 모드에서만 `create_tool` 노출하도록 코드 레벨 원천 차단.
  - **문제 2 — OpenHarness 빌트인 도구 미인식 해결**:
    - `ToolRegistry()` 수동 생성을 폐기하고 `create_default_tool_registry()`로 전환, 37개 빌트인 도구(`bash`, `read_file`, `write_file`, `edit_file`, `glob`, `grep` 등) 자동 등록.
    - RBAC 권한 맵을 확장하여 빌트인 도구별 권한 레벨 명시 (`bash: 3`, `write_file: 2`, `read_file: 1` 등).
  - **문제 3 — 동적 도구 등록 및 경로/인자 문제 해결**:
    - `ToolCreatorTool.description`에 턴 제약 명시: `"You CANNOT create a tool and call it in the SAME turn"`.
    - `_PLAN_EXECUTING_PROMPT`에 `context.cwd` 기반 절대 경로 사용 규칙 추가.

- **`ToolCreatorTool` permission_level 주입 안전성 강화**:
  - 기존 `str.replace('name = ', ...)` 방식의 위험한 문자열 치환 로직을 정규표현식(`re.sub`) 기반으로 교체.
  - 클래스 내부의 `name = "..."` 패턴을 정확히 타겟팅하여 주입 실패 시 명확한 에러 반환.

- **Pydantic 입력 모델 네이밍 화이트리스트 검증**:
  - `ToolValidator._check_input_model_naming()` 메서드 신규 추가.
  - 블랙리스트 방식 대신 `<ToolClassName>Input` 패턴만 허용하는 화이트리스트 방식으로 Pydantic 스키마 캐시 충돌을 원천 차단.

#### Session 3 (2026-04-27)

- **Pydantic 기반 구조화된 출력(Structured Output) 파이프라인 완성**:
  - `StructuredPlanner` 클래스 신규 구현.
  - 마크다운 파싱(Regex 등)에 의존하는 기존 방식을 폐기하고, LLM이 JSON을 직접 반환하도록 `response_format={"type": "json_object"}` 강제.
  - `PlanDocument`, `PlanStep`, `PlanBlock` Pydantic 모델을 통한 스키마 검증으로 0% 파싱 에러 달성.

- **플랜 스키마(Schema) 세분화 및 UI 렌더링 개선**:
  - LLM이 긴 문단으로 응답하는 것을 방지하기 위해 스키마에 `sub_tasks`, `overview`, `key_decisions`, `success_criteria`, `output_artifacts` 리스트(`List[str]`) 필드 추가.
  - 개별 항목 수준의 리뷰를 위해 `SubItem` 스키마 모델을 도입하여 각 세부 항목(`sub_items`)에 고유 `item_id`와 번호(`index`)를 부여.
  - `test_phase2_3.py` UI 렌더러(`_print_plan_blocks`)를 고도화하여 세분화된 항목들을 `[sub-a1b2c3d4]` ID와 함께 들여쓰기된 번호형태 리스트로 표시.
  - Windows 터미널의 cp949 인코딩으로 인한 이모지 출력 에러(UnicodeEncodeError)를 방지하기 위해 `sys.stdout.reconfigure(encoding='utf-8')` 추가.

- **서브 아이템(Sub-Item) 수준 수정 인터페이스**:
  - 기존 블록 단위 수정(`edit N <content>`)에 더해, 서브 아이템 단위의 정밀 수정이 가능한 `edit N.M <content>` 문법 지원 추가 (예: `edit 3.2 새로운 내용`).
  - 마크다운 재생성기(`_rebuild_markdown_from_blocks`)도 `sub_items`를 `bullet point` 형태로 렌더링하도록 개선.

- **에이전트 시스템 프롬프트 (Prompt Engineering) 최적화**:
  - `state.py` 및 `structured_planner.py` 내 모든 시스템 프롬프트를 OpenHarness 기준(Claude 스타일)에 맞춰 **순수 영어**로 전면 재작성.
  - 한국어 강제 제약을 제거하고 `Respond in the same language the user used in their request.` 구문으로 대체하여 유연한 로컬라이제이션 지원.

#### Session 2 (2026-04-24 오후)

- **3-Mode 아키텍처 도입 (Cursor/Copilot 스타일)**:
  - `AgentState` 단일 enum → **`AgentMode`**(ASK, AGENT, PLAN) + **`PlanPhase`**(DRAFTING, WAIT_FOR_REVIEW, EXECUTING) 2-레이어 상태 모델로 전면 재설계.
  - **Ask 모드**: 질문/답변 전용. 도구 실행 없이 지식 기반 응답만 제공.
  - **Agent 모드**: 자율 실행 모드. 도구를 자유롭게 사용하여 즉시 작업 수행 (기본 시작 모드).
  - **Plan 모드**: 구조화된 파이프라인 (Drafting → Review → Executing). 복잡한 작업에 적합.
  - 슬래시 명령어(`/ask`, `/agent`, `/plan`, `/mode`) 기반 모드 전환 UX.
  - 입력 프롬프트에 현재 모드 표시: `[Agent] >`, `[Plan/Drafting] >`, `[Ask] >`.
  - Plan 실행 완료 후 Agent 모드 자동 복귀.

- **ToolValidator AST 기반 엄격 검증 로직 3종 추가**:
  - `_check_execute_signature()`: `execute(self, arguments, context)` 시그니처 강제.
  - `_check_tool_result_usage()`: `ToolResult.from_error()` 등 존재하지 않는 API 사전 차단.
  - `_check_context_input_model()`: `context.input_model` 안티패턴 감지.
  - `validate_and_load_module()` 2단계 런타임 검증에서도 `inspect.signature` 교차 검증 추가.

- **OpenHarness 엔진 에러 복구 (Self-Healing) 강화**:
  - `query.py`의 `_execute_tool_call()`에 `try-except` 블록 추가.
  - 툴 실행 중 Python 내부 에러(TypeError 등)가 발생해도 루프가 중단되지 않고, `ToolResult(is_error=True)`로 에이전트에게 피드백.
  - 에이전트가 실패 원인을 인지하고 자가 디버깅할 수 있는 Self-Healing 멀티턴 지원.

- **대화 컨텍스트 유지 (Multi-turn Memory Fix)**:
  - `QueryEngine` 인스턴스를 루프 외부에서 1회만 생성하도록 수정.
  - 매 턴 루프 내에서는 `set_system_prompt()` + `_tool_registry` 동적 갱신으로 상태와 권한만 업데이트.

#### Session 1 (2026-04-24 오전)

- **에이전트 프롬프트 고도화 (Phase 3)**: `TheseusStateMachine`에 OpenHarness 프롬프트 패턴(Base + Environment + Agent Persona)을 적용하여 상태별 명확한 역할 부여 및 7가지 핵심 보안/도구 가이드라인 추가.
- **메타-툴링 시스템 (Tool Factory) 구현**: LLM이 스스로 파이썬 툴 코드를 작성하고 검증(Syntax 및 OpenHarness 규격)하여 저장하는 `ToolCreatorTool` 구축.
- **툴 동적 로딩 및 런타임 등록 지원**: `load_custom_tools`를 통해 서버 시작 시 `custom_tools/` 디렉토리의 툴을 자동 로드하고, `create_tool` 성공 시 현재 세션의 `ToolRegistry`에 즉시 주입하여 다음 턴부터 바로 사용 가능하도록 구현.
- **동적 권한 제어 (RBAC) 및 레지스트리 필터링 (Phase 2)**:
  - `TheseusPermissionChecker`를 통해 사용자 권한 레벨과 툴 요구 레벨(자연수)을 비교.
  - 사용자의 권한 레벨에 따라 접근 가능한 툴만 담은 `build_filtered_registry` 기능을 통해 LLM에게 권한 밖의 툴을 완전히 숨기는(API 스키마에서 제외) 로직 완성.
  - 툴 생성 시 `permission_level` 메타데이터 자동 주입 및 RBAC 맵 동적 등록 기능 추가.

### 🔧 Changes (변경 사항)

- `schemas.py`: `PlanStep` 및 `PlanDocument` 스키마 세분화, `PlanBlock`, `SubItem` UI용 모델 추가.
- `structured_planner.py`: Pydantic 스키마 검증, LLM 호출부, Markdown/Block 변환 로직 구현. 프롬프트 영어화 적용 및 `_make_sub_items()` 추가.
- `state.py` 전면 재작성: `AgentMode` + `PlanPhase` 3-Mode 상태 머신 구조 확립. 프롬프트를 OpenHarness Claude-스타일(영어)로 리팩터링.
- `test_phase2_3.py` 전면 재작성: 3-Mode 슬래시 커맨드 적용, 서브아이템 렌더링 및 `edit N.M` 수정 기능, utf-8 강제 적용 방어 코드 추가.
- `tool_factory.py`: `ToolValidator` 클래스에 `_check_execute_signature`, `_check_tool_result_usage`, `_check_context_input_model` 3개 private 메소드 추가.
- `query.py` (OpenHarness 수정): `_execute_tool_call()` 내 `tool.execute()` 호출을 `try-except`로 래핑.
- `time_weather_tool.py`: `execute` 시그니처를 `(self, arguments, context)` 정규 규격으로 수정, `ToolResult` 사용법 정정.

### 📋 Documentation

- `docs/proposals/openharness_unused_features_proposal.md` 신규 작성: OpenHarness 미사용 핵심 모듈 8종(Memory, Sandbox, Swarm, MCP, Hooks, Skills, Plugin, Services) 분석 및 상용 서비스 대비 부재 기능 7건 정리. Phase 4~6 도입 로드맵 제안.

### ⚠️ Known Issues / Next Steps

- **Phase 4 (즉시)**: Sandbox 도입, AST 보안 검증기 고도화 (os/subprocess 등 위험 모듈 차단)
- **Phase 5 (단기)**: Memory System 통합, Hooks + LangSmith 연동, 세션 저장/복원
- **Phase 6 (중기)**: MCP Client 통합, 멀티 에이전트 (Swarm), Skills & Plugin System
