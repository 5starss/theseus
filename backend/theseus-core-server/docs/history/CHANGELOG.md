# Changelog

모든 변경 사항은 최신순(역순)으로 기록됩니다.

## [Unreleased]
### 🚀 Session 17 (2026-04-29)
- **Theseus CLI 안정화 및 기능 고도화 (`theseus_cli.py`)**:
    - **비동기 호출 오류 수정**: `maybe_compress` 코루틴 호출 시 `await`를 누락하여 발생하던 런타임 에러를 해결하였습니다.
    - **Gemini 400 에러 해결**: `apply_gemini_patch()` 적용 및 `TheseusLLMClient` 강제 주입을 통해 도구 호출 시 `Name cannot be empty` INVALID_ARGUMENT 에러를 원천 차단하였습니다.
    - **슬래시 명령어 통합 인터셉터 구현**: 명령어를 루프 최상단에서 가로채 처리하는 구조로 개편하여 TUI와의 기능 패리티(Parity)를 맞추고 확장성을 확보하였습니다.
- **로드맵 핵심 명령어 5종 CLI 이식**:
    - **`/validate <tool_name>`**: `ToolValidator`를 연동하여 `custom_tools/` 내 도구의 보안 및 규격을 수동으로 정적 분석할 수 있는 기능을 추가하였습니다.
    - **`/kb <query>`**: 에이전트를 거치지 않고 `RAGService`를 직접 호출하여 지식 베이스의 내용을 즉시 검색하고 원문을 확인할 수 있는 기능을 구현하였습니다.
    - **`/rbac <level>`**: 사용자 권한 레벨을 실시간으로 변경하여 도구 노출 및 실행 권한 테스트가 가능하도록 개선하였습니다.
    - **`/tools`**: 현재 모드와 RBAC 레벨에서 실제 사용 가능한 도구 목록을 시각적으로 확인할 수 있는 기능을 추가하였습니다.
    - **`/ask` / `/plan` / `/agent`**: 에이전트 동작 모드 전환 로직을 CLI 루프에 완벽히 통합하였습니다.
    - **`/approve` / `/reject`**: 향후 비동기 승인 서버 연동을 위한 워크플로우 커맨드 스텁(Stub)을 마련하였습니다.

## [Released]
### 🚀 Session 16 (2026-04-29)
- **Adaptive K — 쿼리 복잡도 기반 동적 슬롯 조정 (`tool_retriever.py`)**:
    - `compute_adaptive_k(query, base_k)` 함수 신규 구현. 정규식으로 다단계 신호(`먼저`, `그런 다음`, `마지막으로` 등)와 복잡도 키워드(`분석`, `리팩터링`, `전체` 등)를 감지하여 k를 동적 조정.
    - 단순 질문 → `base_k // 2` (최소 3), 다단계/복합 요청 → `base_k × 1.5` (최대 16), 일반 → `base_k`.
    - `retrieve_top_k(adaptive=True)` 파라미터 추가. 기본 활성화 상태로 매 쿼리마다 자동 적용.
- **Tool 사용 피드백 루프 (`tool_usage_logger.py`)**:
    - `record_tool_call(query, tool_name)`: 실제 도구 호출 이벤트를 `~/.theseus/tool_usage.jsonl`에 JSONL 형식으로 누적.
    - `merge_feedback_into_examples()`: 누적 로그에서 도구별 쿼리를 집계하여 `TOOL_EXAMPLE_QUERIES`에 자동 병합. `ToolRetriever` 초기화 시 자동 적용되어 사용 패턴이 쌓일수록 검색 정확도가 향상.
    - `get_log_stats()`: 도구별 총 호출 횟수 통계 제공.
    - `theseus_cli.py`: `ToolExecutionStarted` 이벤트에서 `record_tool_call()` 자동 호출.
- **컨텍스트 자동 압축 (`context_compressor.py`)**:
    - `maybe_compress(messages, max_messages=30, keep_recent=10)`: 메시지 수가 임계값 초과 시 오래된 메시지를 요약 1개로 교체, 최근 N개는 원본 유지. 35개 → 11개(요약 1 + 최근 10) 검증 완료.
    - LLM 클라이언트 주입 시 AI 요약, 미주입 시 구조적 압축으로 자동 fallback.
    - `ConversationMessage` 객체 및 `dict` 형식 모두 지원.
    - `theseus_cli.py`: 매 메시지 전송 전 자동 압축 체크 및 적용.
- **코드 정리**:
    - `theseus_engine/tools/tools.py`, `theseus_engine/tools/tool_factory.py` 중복 파일 삭제 (이미 `tools/core/`로 이전 완료).
    - `command_handler.py` import 경로 구 경로 → 신 경로로 수정.
    - `knowledge_tools.py`: `psycopg2` 미설치 환경에서도 import 오류 없이 로드되도록 try/except 처리.

### 🚀 Session 15 (2026-04-29)
- **동적 도구 선택 시스템 (Top-K Tool Retrieval) 구현**:
    - **`ToolRetriever` (`theseus_engine/core/tool_retriever.py`)**: 사용자 쿼리를 기반으로 시맨틱 유사도가 높은 상위 K개 도구를 선별하여 에이전트에 제공하는 인메모리 검색 엔진 구현.
    - **인프라 독립**: 기존 RAGService(PostgreSQL + pgvector) 의존을 제거하고, `sentence-transformers` + `numpy` 코사인 유사도 기반 경량 인메모리 검색으로 전환. 외부 DB 없이 즉시 동작.
    - **비대칭 검색 최적화**: `intfloat/multilingual-e5-small` 모델로 전환. `query:`/`passage:` 프리픽스를 활용하여 짧은 사용자 쿼리 ↔ 긴 도구 설명 간의 비대칭 매칭 정확도를 극대화.
    - **Few-shot 쿼리 보강**: 각 도구에 예상 사용자 발화를 추가하여 임베딩 공간에서의 매칭 품질 향상. (Score: 0.26 → 0.83, 약 3배 이상 개선)
    - **필수 도구 보장(Essential Tools)**: `read_file`, `write_file`, `edit_file`, `bash`, `glob`, `grep`, `ask_user`는 검색 결과와 무관하게 항상 포함.
    - **K 슬롯 분리 (Essential ≠ K 소비)**: 필수 도구가 `k` 슬롯을 소비하지 않도록 `similarity_added` 카운터를 별도로 관리. 이전에는 `len(selected) >= k`로 비교하여 필수 도구가 K 슬롯을 차지하는 버그가 있었으며, `k=8`에 필수 7개가 포함되면 유사도 기반 도구가 1개밖에 추가되지 않는 문제 해결.
    - **Ghost Tool Call 방지**: `_extract_history_tool_names()` 메서드로 이전 대화 히스토리에서 사용된 도구 이름을 추출하여 현재 레지스트리에 강제 포함. LLM이 현재 스키마에 없는 도구를 호출하는 Ghost Tool Call 오류 원천 차단. `ConversationMessage` 객체 및 `dict` 형식 모두 지원.
    - **안전 장치**: `engine_builder.py`에 try/except 래핑 및 fallback 로직 추가. 임베딩 모델 로드 실패 시 전체 레지스트리로 자동 복구.
- **P2 도구 이식 완료**:
    - **Git 워크트리 관리 (`worktree_tools.py`)**: `enter_worktree` / `exit_worktree` 도구 구현. `.theseus/worktrees/` 경로에 격리된 실험 환경 제공.
    - **지능형 브리핑 (`brief_tool.py`)**: 긴 텍스트/대화를 구조적으로 압축하는 `brief` 도구 구현. 향후 LLM 연동 확장 구조 내장.

### 🚀 Session 14 (2026-04-29)
- **OpenHarness 코어 Gemini 3.1 Pro 네이티브 지원 통합**:
    - **문제점**: 이전의 몽키패칭이나 래퍼 방식은 OpenHarness의 내부 리프레시 로직에 의해 무력화되거나 의존성 주입이 복잡해지는 한계가 있었음.
    - **해결**: `OpenHarness/src/openharness/api/openai_client.py`를 직접 수정하여 Gemini의 `thought_signature` / `extra_content`를 코어 레벨에서 자동으로 캡처하고 패치하도록 구현. 이제 어떤 실행 환경(CLI, TUI, API)에서도 Gemini 3.1 Pro가 "순정" 상태로 도구 사용 기능을 지원함.
- **TUI 이벤트 버블링 차단 아키텍처 개선 (`TheseusInput` 도입)**:
    - **문제점**: App 레벨에서 이벤트를 가로채려 시도했으나, 부모 클래스(OpenHarness)와의 Race Condition으로 인해 Theseus 전용 슬래시 커맨드가 바이패스되는 현상 발생.
    - **해결**: 위젯 계층의 최하단인 `Input` 위젯을 상속받은 `TheseusInput` 커스텀 위젯을 구현. 이벤트가 상위(App)로 전달되기 전 위젯 레벨에서 `event.stop()`을 호출하여 OpenHarness로의 이벤트 유출을 물리적으로 완벽 차단.
- **심플 CLI 에이전트 (`theseus_cli.py`) 구축**:
    - TUI의 시각적 복잡함과 의존성 없이 로직에만 집중할 수 있는 가벼운 CLI 인터페이스 개발. 실시간 스트리밍, 세션 관리, 도구 사용 승인(HITL) 기능을 포함하며 코어에 통합된 Gemini 로직을 직접 활용.
- **주요 버그 수정**:
    - `theseus_client.py`: 디버그 덤프 로직 중 `sys` 모듈 임포트 누락으로 인한 `NameError` 및 묵음 에러 해결.
    - `theseus_cli.py`: `.env` 로드 로직 추가 및 OpenHarness 스트림 이벤트 클래스 명칭 불일치(`ToolUseStart` → `ToolExecutionStarted` 등) 수정.
    - 세션 초기화: `thought_signature`가 누락된 과거 오염된 세션 데이터가 400 에러를 유발하지 않도록 `default.json` 초기화.


### 🚀 Session 13 (2026-04-29)
- **Gemini 400 에러 최종 근본 원인 수정 (`patch_assistant_tool_calls` 버그)**:
  - **원인 분석**: `gemini_compat.py`의 `patch_assistant_tool_calls` 함수에서 `_raw_tool_calls`가 있을 때 (`tc_id in raw_tool_calls`) 해당 dict를 그대로 교체하는데, `extra_content`가 `None`으로 수집된 경우 `rebuild_tool_call_dict`가 `extra_content` 키를 아예 포함하지 않아 Fallback이 우회되는 버그가 있었음. 결과적으로 `_raw_tool_calls`가 존재하지만 `extra_content`가 없는 상태로 API에 전달되어 `INVALID_ARGUMENT` 에러 지속 발생.
  - **수정 (`gemini_compat.py`)**: `raw_tool_calls[tc_id]`에 `extra_content` 키가 없는 경우 Fallback `_FALLBACK_EXTRA_CONTENT`를 주입한 복사본으로 교체하도록 로직 개선. 이제 `_raw_tool_calls`의 유무와 관계없이 모든 tool call에 `extra_content`가 보장됨.
- **커스텀 툴 로딩 경로 버그 수정 (`CUSTOM_TOOLS_DIR`)**:
  - `tool_factory.py`의 `CUSTOM_TOOLS_DIR`이 `theseus_engine/tools/custom_tools/`를 가리키고 있었으나 실제 커스텀 툴은 `theseus_engine/custom_tools/`에 저장되어 있어 툴이 전혀 로드되지 않는 버그 수정. `os.path.join(__file__, "..", "custom_tools")`로 경로 수정.
- **`time_weather_tool_v2.py` 입력 모델 명명 규칙 수정**:
  - `ToolValidator`의 입력 모델 명명 규칙(`<ToolClassName>Input`)에 따라 `TimeWeatherInputV2` → `TimeWeatherToolV2Input`으로 클래스명 수정. 이전 이름으로는 검증 실패로 툴 로드가 스킵되고 있었음.
- **`OPENWEATHERMAP_API_KEY` 미설정 안내**: `time_weather_tool_v2.py`가 사용하는 OpenWeatherMap API 키가 `.env`에 없음. 툴 사용 전 `.env`에 `OPENWEATHERMAP_API_KEY=<키>` 추가 필요.

### 🚀 Session 11 (2026-04-28)
- **RAG 지식 베이스(Knowledge Base) 시스템 구현 (PostgreSQL + pgvector)**:
  - `theseus_engine/rag/config.py` [신규]: `.env` 기반의 PostgreSQL, 임베딩, RAG 설정 로더. `dataclass(frozen=True)` 패턴으로 불변 설정 관리.
  - `theseus_engine/rag/database.py` [신규]: pgvector 확장 자동 설치, `knowledge_documents` 테이블/IVFFlat 인덱스 생성, 벡터 CRUD 및 코사인 유사도 검색(`<=>` 연산자) 구현.
  - `theseus_engine/rag/embeddings.py` [신규]: `BaseEmbeddingProvider` 추상 클래스 및 `LocalEmbeddingProvider`(sentence-transformers), `RemoteEmbeddingProvider`(OpenAI) 구현. Lazy-loading 패턴 적용.
  - `theseus_engine/rag/service.py` [신규]: 문서 청킹(Chunking), 임베딩, 적재(Ingestion), 벡터 검색을 통합하는 RAG 비즈니스 로직. 싱글톤 접근자 `get_rag_service()` 제공.
  - `theseus_engine/tools/knowledge_tool.py` [신규]: `search_knowledge_base` (RBAC Lv.1) 및 `ingest_document` (RBAC Lv.2) 에이전트 도구 구현.
  - `theseus_engine/core/engine_builder.py`: KB 도구 2종을 전역 `ToolRegistry`에 등록.
  - `theseus_engine/tui/tui_main.py`: RBAC 권한 맵에 `search_knowledge_base: 1`, `ingest_document: 2` 추가.
  - `requirements.txt`: `psycopg2-binary`, `numpy` 의존성 추가.
- **API 클라이언트 안정성 및 Gemini 호환성 강화 (thought_signature 파싱 버그 해결)**:
  - `theseus_engine/wrappers/llm_clients/gemini_compat.py` [신규]: Gemini 3.1 Pro의 비표준 `thought_signature` / `extra_content` 필드를 추출하고 재주입하며, 과거 세션 복구 시 Fallback을 제공하는 전용 호환성 모듈 신설.
  - `theseus_engine/wrappers/llm_clients/theseus_client.py`: 라우팅/스트리밍 역할만 남기고 Gemini 종속적 로직 분리 (리팩토링). 모든 API 클라이언트 초기화 시 타임아웃 기본값을 `120.0`초로 상향하여 긴 응답 시간으로 인한 `Request timed out` 에러 원천 차단.
  - **🚨 Gemini 400 Bad Request 에러 최종 수정 (Session 12)**: `gemini_compat.py`의 `_FALLBACK_EXTRA_CONTENT`에 사용하던 더미 서명 `"Executing tool call"`이 Google API의 Base64 Protobuf 디코딩 검증을 통과하지 못해 `Corrupted thought signature` 에러를 유발하는 것으로 최종 확인. Google 공식 문서(https://ai.google.dev/gemini-api/docs/gemini-3)에 명시된 공식 더미 문자열 `"context_engineering_is_the_way to_go"`로 교체하여 해결. 아울러 디버깅 목적으로 임시 삽입했던 `theseus_client.py`의 `debug_openai_messages.json` 덤프 코드도 제거하여 코드 정리 완료.

### 🚀 Session 10 (2026-04-28)
- **전체 코드베이스 한글 → 영어 국제화 (i18n)**:
  - `theseus_engine/tools/tools.py`: `DummyTool`, `SystemRebootTool`의 description, Field description, 출력 메시지 영어로 전환.
  - `theseus_engine/tools/tool_factory.py`: `ToolCreatorInput` Field descriptions, `ToolValidator` 전체 에러 메시지(16건), `ToolCreatorTool` 결과 메시지 영어로 전환.
  - `theseus_engine/models/rbac.py`: RBAC 거부/승인/보안정책 메시지 3건 영어로 전환.
  - `theseus_engine/validators/execution_validator.py`: 검증 경고/통과 메시지 영어로 전환.
  - `theseus_engine/validators/query_validator.py`: SQL DDL/DML/Injection 탐지 메시지 영어로 전환.
  - `theseus_engine/validators/analysis_validator.py`: AST 보안 분석 에러 메시지(금지 모듈/함수/던더) 영어로 전환.
- **프롬프트 아키텍처 문서 신규 작성**:
  - `docs/prompt/prompt_architecture_map.md` [신규]: Theseus 전용 프롬프트 파일 위치, 역할, 간단한 설명을 Mermaid 아키텍처 다이어그램과 함께 정리.

### 🐛 Bug Fixes (2026-04-28)
- **TUI 모드 전환 크래시 버그 수정**: `tui_main.py` 파일 내에서 `/agent`, `/plan`, `/ask` 등의 커맨드 실행 시 `build_filtered_registry`를 호출하지만 모듈 상단에 import 되지 않아 발생하던 `NameError` 크래시 버그 수정.

### 🚀 Session 9 (2026-04-28)
- **Phase 4: 관측성(Observability) 연동 — LangSmith 트레이싱 구현**:
  - `theseus_engine/observability/tracer.py` [신규]: Bypass 가능한 중앙 트레이싱 유틸리티 구현.
  - `theseus_engine/wrappers/hooks/theseus_hook_executor.py`: `execute()` 메서드에 `@theseus_traceable` 적용.
  - `theseus_engine/validators/*`: 각 Validator의 `validate()` 메서드에 트레이싱 적용.
  - `theseus_engine/core/engine_builder.py`: `get_tracing_tags()` / `get_tracing_metadata()` 추가.
  - `theseus_engine/tui/tui_main.py`: `submit_message()` 호출 래핑.
  - `requirements.txt`: `langsmith>=0.1.0` 의존성 추가.
- **TUI 사이드바 표시 수정**:
  - `permissions` 필드: `RBAC (Lv.5)` 형태로 표시.
  - `tokens` 필드: API에서 0으로 집계될 경우 `N/A`로 안전하게 표시.

### 🚀 아키텍처 확장 및 리팩토링 (2026-04-28)
- **검증기(Validators) 4종 분리 및 신규 구현**:
  - `AnalysisValidator`: AST 기반 보안 정적 분석기. 기존 `_check_security_violations` 대체.
  - `ExecutionValidator`: HTTP 상태 변경 및 파일 시스템 파괴 작업 감지.
  - `QueryValidator`: SQL DDL/DML 및 인젝션 의심 패턴 감지.
  - `SuggestionValidator`: LLM 기반 코드 품질 리뷰 Stub 구현.
- **Hooks 통합 및 래퍼 구현**:
  - `TheseusHookExecutor` 래퍼 구현: OpenHarness 공식 `HookExecutor` 상속. `PRE_TOOL_USE` 이벤트 시 Validator 연쇄 실행.
  - 중복 구현된 커스텀 훅(`file_hook.py` 등) 완전히 제거.
  - 선택적 에이전트 훅(`THESEUS_ENABLE_AGENT_HOOK`) 동적 등록 로직 추가.
- **LLM 클라이언트 구조 개편 (Monkey Patch 제거)**:
  - `gemini_patch.py` 삭제 및 몽키패치 청산.
  - `TheseusLLMClient` 라우터 신설: `OPENHARNESS_MODEL` 접두사에 따라 `AnthropicApiClient`, `TheseusGeminiClient`, `OpenAICompatibleClient` 등 동적 매핑.
  - `engine_builder.py`, `tui_main.py` 초기화 로직 단순화.

### 🚀 Session 8 (2026-04-28)
- **Theseus 에이전트 프롬프트 종합 리팩토링 (Prompt Engineering v2)**:
  - `state.py`: OpenHarness 원본 + Claude Code 에이전트 프롬프트 비교 분석 후 종합 적용.
  - "읽지 않은 코드를 수정하지 마라", 컨텍스트 자동 압축, RBAC 동적 필터링 인지 등 가드레일 대폭 추가.
  - `tool_factory.py`, `tools.py` 내 도구 설명(description) 고도화.
- **Theseus 엔진 모듈화 및 아키텍처 리팩토링 (Architecture Modularization)**:
  - 거대한 `tui_app.py`, `app.py`를 논리적 단위(`core/`, `tui/`, `models/`, `tools/`, `wrappers/`)로 완벽 분할.
  - 엔트리포인트를 `cli_main.py`와 `tui_main.py`로 명확히 분리.

### 🚀 Session 7 (2026-04-28)
- **TUI 명령어 및 시스템 프롬프트 덮어쓰기 문제 완벽 해결**:
  - Python MRO 기반 `_process_line` 오버라이드 구현.
  - 기존의 위험한 몽키패칭 및 런타임 우회 코드 제거.
  - 디버깅 리포트 `tui_command_registration_issue.md` 작성.

### 🚀 Session 6 (2026-04-27)
- **LLM API 통신 호환성 및 자동 복구(Auto-Recovery) 강화**:
  - Gemini 3.1 Pro 도구 호출(`thought_signature` 누락) 400 에러 해결 (초기 몽키패치 방식).
  - API `ErrorEvent` 발생 시 LLM에게 피드백하여 자가 치유를 시도하는 복구 루프 구축.

### 🚀 Session 5 (2026-04-27)
- **에이전트 보안 체계(Defense in Depth) 강화 및 UX 개선**:
  - 1차 방어: `StructuredPlanner` 시스템 프롬프트 제약 추가. 불필요한 리뷰 스킵 로직.
  - 2차 방어: `ToolValidator._check_security_violations` (AST 분석) 신규 추가.
- **Windows 비동기 셸 실행 버그 수정**:
  - `asyncio.WindowsProactorEventLoopPolicy()` 동적 설정 추가.

### 🚀 Session 4 (2026-04-27)
- **3대 도구 시스템 문제 전면 해결**:
  - Agent 모드 `create_tool` 남발 원천 차단 (Plan Executing 모드 전용으로 제한).
  - OpenHarness 빌트인 37개 도구 자동 등록 및 RBAC 레벨 매핑.
  - 동적 도구 등록 제약(`SAME turn` 금지) 및 절대 경로 사용 규칙 추가.
- **`ToolCreatorTool` permission_level 주입 로직 정규표현식으로 강화**.
- **Pydantic 입력 모델 네이밍 화이트리스트 검증 추가**.

### 🚀 Session 3 (2026-04-27)
- **Pydantic 기반 구조화된 출력(Structured Output) 파이프라인 완성**:
  - `StructuredPlanner` 구현 및 `response_format={"type": "json_object"}` 강제.
- **플랜 스키마 세분화 및 UI 렌더링 개선**:
  - `sub_tasks`, `key_decisions` 등 필드 추가. `[sub-a1b2c3d4]` ID 기반 렌더링.
  - 서브 아이템 단위 수정 인터페이스 (`edit N.M`) 지원.
- **에이전트 시스템 프롬프트 전면 영어화 및 최적화**.
- **기타 변경 사항**:
  - `schemas.py`, `structured_planner.py`, `state.py`, `test_phase2_3.py`, `tool_factory.py`, `query.py`, `time_weather_tool.py` 등 리팩토링 및 에러 래핑 적용.

### 📋 Documentation (2026-04-27)
- `docs/proposals/openharness_unused_features_proposal.md` 신규 작성 (미사용 핵심 모듈 8종 분석 및 로드맵 제안).

### 🚀 Session 2 (2026-04-24)
- **3-Mode 아키텍처 도입**: Ask, Agent, Plan(Drafting, Review, Executing) 다중 레이어 상태 모델.
- **ToolValidator AST 기반 엄격 검증 로직 3종 추가**.
- **OpenHarness 엔진 에러 복구 (Self-Healing) 강화**: `query.py` 툴 실행 에러 래핑.
- **대화 컨텍스트 유지 (Multi-turn Memory Fix)**.

### 🚀 Session 1 (2026-04-24)
- **에이전트 프롬프트 고도화**: 상태별 명확한 역할 부여 및 7가지 가이드라인 추가.
- **메타-툴링 시스템 (Tool Factory)**: `ToolCreatorTool` 및 동적 로딩 구현.
- **동적 권한 제어 (RBAC) 및 레지스트리 필터링**: `TheseusPermissionChecker` 및 `build_filtered_registry` 구현.

## [2026-04-29] Session 18: 동적 도구 검색 최적화 및 런타임 주입 시스템 구현

### 🚀 주요 변경 사항
*   **런타임 도구 수혈(Runtime Tool Injection) 시스템 구현**:
    *   `POST_TOOL_USE` 훅을 활용하여 도구 실행 결과(`tool_output`)를 실시간 분석하는 로직 추가.
    *   새로운 맥락이 발견되면 `ToolRetriever`를 통해 연관 도구를 찾아 현재 에이전트 레지스트리에 즉시 주입(Inject)함으로써 다단계 작업 중 도구 가용성 문제 해결.
*   **도구 검색 파이프라인(Tool Retriever) 고도화**:
    *   **동적 재인덱싱**: 레지스트리의 도구 변경을 감지하여 재시작 없이도 자동으로 임베딩 인덱스를 갱신하도록 개선.
    *   **키워드 기반 리랭킹**: 쿼리에 포함된 핵심 단어(예: "만들어", "수정", "search")에 가중치를 부여하여 시맨틱 검색의 한계를 보완하는 간이 리랭킹 알고리즘 적용.
*   **시스템 안정성 및 Pydantic 호환성 수정**:
    *   `worktree_tools.py` 등에서 발생하던 `class not fully defined` 에러 해결을 위해 `Optional` 임포트 누락 수정 및 `model_rebuild()` 일괄 적용.
    *   `ToolRetriever` 싱글톤 패턴에서의 레지스트리 참조 동기화 문제 해결.

---


## ⚠️ Known Issues / Next Steps
- **Phase 5 (단기)**: Sandbox 도입, Memory System 통합, Hooks + LangSmith 연동 고도화, 세션 저장/복원
- **Phase 6 (중기)**: MCP Client 통합, 멀티 에이전트 (Swarm), Skills & Plugin System
