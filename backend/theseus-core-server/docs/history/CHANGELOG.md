# Changelog

모든 변경 사항은 최신순(역순)으로 기록됩니다.

## [Unreleased]
### 🚀 Session 25 (2026-05-04)
- **파일 생성·수정 실패 근본 원인 수정 및 마크다운 링크 오염 방어**:
    - **이중 권한 프롬프트 제거 (`engine_builder.py`)**: CLI 모드에서 `write_file`·`edit_file`·`bash` 호출 시 `TheseusHookExecutor._check_hitl()`과 `TheseusPermissionChecker.evaluate()`가 각각 사용자 확인을 요청하는 이중 프롬프트 문제 해결. `require_human_confirm=False`로 고정하여 HITL 훅이 단독으로 사람 확인을 담당하고 권한 체커는 RBAC 레벨 체크만 수행하도록 역할 분리.
    - **코드 파일 마크다운 링크 자동 제거 (`file_write_tool.py`, `file_edit_tool.py`)**: LLM이 `from [openharness.tools](http://openharness.tools).base import ...` 같은 마크다운 링크 문법을 Python 코드에 삽입하는 문제 방어. `.py`·`.ts`·`.js`·`.tsx`·`.jsx`·`.sh` 확장자 파일에 한해 `_strip_markdown_links()`를 content·old_str·new_str에 자동 적용하여 잘못된 import 구문 없이 파일이 생성되도록 수정.
    - **시스템 프롬프트 마크다운 링크 금지 규칙 추가 (`state.py`)**: 베이스 프롬프트 및 PLAN EXECUTING 섹션 양쪽에 "파일명·경로·코드에 마크다운 링크 문법(`[label](url)`) 절대 사용 금지" CRITICAL 규칙 추가. 예시(`[sorter.py](http://sorter.py)` → `sorter.py`, `[x.is](http://x.is)_integer()` → `x.is_integer()`) 포함.

### 🚀 Session 24 (2026-05-04)
- **툴 호출 파이프라인 안정화 및 'bool' object is not callable 오류 해결**:
    - **OpenHarness QueryEngine 연동 최적화**: `engine_builder.py`에서 `QueryEngine` 초기화 시 `permission_prompt_func`가 호출 가능한(callable) 객체인지 사전에 검증하여, 불리언 값이 전달될 경우 발생하던 런타임 에러를 방지하였습니다.
    - **HITL 승인 로직 강화 (`theseus_hook_executor.py`)**: `TheseusHookExecutor._check_hitl` 메서드가 `permission_prompt` 콜백에 `tool_name`과 `prompt_msg` 두 개의 인자를 정상적으로 전달하도록 수정하여 `theseus_cli.py`의 `ask_permission` 인터페이스와의 정합성을 맞췄습니다.
    - **유연한 응답 처리**: 승인 콜백이 불리언(`bool`) 값을 반환할 경우(OpenHarness 표준)와 문자열(`str`)을 반환할 경우(TUI/CLI input)를 모두 지원하도록 개선하여 다양한 인터페이스 환경에서의 호환성을 확보하였습니다.
    - **방어적 프로그래밍 적용**: 모든 콜백 호출부에 `callable()` 체크 및 `try...except` 예외 처리를 추가하여 보안 훅 실행 중 에러가 발생하더라도 전체 시스템이 크래시되지 않고 안전하게 차단(Safe-fail)되도록 개선하였습니다.
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

## [2026-05-04] Session 23: 'bool' object is not callable 오류 해결 및 네이버 웹툰 도구 배포

### 🚀 주요 변경 사항
*   **'bool' object is not callable 런타임 오류 해결**:
    *   `engine_builder.py`에서 `permission_prompt_func`가 `None`일 때 불리언 값이 할당되어 `QueryEngine`에서 호출 시 에러가 발생하던 문제를 수정하였습니다.
    *   `TheseusHookExecutor`가 `permission_prompt` 콜백을 주입받아 보안 훅 실행 시 올바르게 사용자 승인을 요청할 수 있도록 구조를 개선하였습니다.
*   **네이버 웹툰 검색 도구(`naver_webtoon_search`) 배포**:
    *   네이버 웹툰 내부 JSON API(`comic.naver.com/api/search/all`)를 직접 호출하는 방식의 신규 도구를 구현하였습니다.
    *   기존 HTML 크롤링 방식 대비 속도와 안정성을 대폭 향상시켰으며, 별점, 연재 상태, 작품 링크 등 상세 정보를 제공합니다.
*   **vLLM 도구 호출 호환성 확보**:
    *   `--enable-auto-tool-choice` 및 `--tool-call-parser gemma4` 설정을 통해 vLLM 환경에서의 안정적인 도구 사용을 지원합니다.
*   **관측성 및 보안 훅 안정화**:
    *   `THESEUS_ENABLE_AGENT_HOOK=true` 설정 시 파일 시스템 작업에 대한 보안 감사(Security Audit)가 정상적으로 작동함을 확인하였습니다.

---

## [2026-05-04] Session 19: 동적 도구 기능 제어 토글 구현

### 🚀 주요 변경 사항
*   **동적 도구 검색 및 주입 토글(Toggle) 시스템 구현**:
    *   `THESEUS_DYNAMIC_TOOL_RETRIEVAL` 환경 변수를 통해 엔진의 동적 도구 검색 및 런타임 주입 기능을 전역적으로 온오프할 수 있도록 구현하였습니다.
    *   `setup_engine` 메서드에 `enable_dynamic_tools` 파라미터를 추가하여 프로그래밍 방식으로도 제어가 가능하게 개선하였습니다.
*   **Hook 파이프라인 연동 최적화**:
    *   `TheseusHookExecutor`가 생성 시점에 동적 도구 활성화 여부를 주입받아, `POST_TOOL_USE` 단계에서의 자동 도구 발견(`_discover_and_inject_tools`)을 조건부로 실행하도록 수정하였습니다.
    *   동적 도구 기능 비활성화 시 불필요한 `ToolRetriever` 초기화 및 임베딩 모델 로드를 방지하여 리소스 사용 효율을 높였습니다.

---

## [2026-05-04] Session 22: CLI 슬래시 명령어 확장 — /cost · /stats · /coordinator · /help

### 변경 파일: `theseus_cli.py`

**배경**: Session 21에서 구현한 CostTracker, SessionStats, Coordinator 모드가 TUI에만 연동되어 있었고, CLI(`theseus_cli.py`)에서는 `/cost`, `/stats`, `/coordinator` 명령어가 슬래시 인터셉터에 등록되지 않아 LLM에게 쿼리로 전달되는 문제 발생.

**추가된 슬래시 명령어**:

| 명령어 | 동작 |
|--------|------|
| `/coordinator` | `AgentMode.COORDINATOR`로 전환. Decompose 단계 프롬프트 활성화 |
| `/cost` | `CostTracker.get_or_create().format_report()` 출력. 모델별 입력/출력 토큰 및 USD 비용 집계 테이블 |
| `/stats` | `SessionStats.get().format_report()` 출력. 툴별 p50/p95 실행 시간, 호출/에러 횟수, RAG 검색 시간 |
| `/help` | `_print_help()` 호출로 전체 명령어 목록 재출력 |

**`_print_help()` 함수 분리**:
- 기존에 `run_cli()` 내부에 `print()` 나열로 작성되어 있던 도움말을 독립 함수로 추출.
- 카테고리 4개로 구조화: `[모드 전환]`, `[도구 및 권한]`, `[지식 베이스]`, `[세션 관리]`, `[기타]`.
- 시작 시 자동 출력(`_print_help()` 단일 호출) 및 `/help` 명령어로 언제든 재확인 가능.

**인코딩 안전 처리**:
- `/cost`, `/stats` 출력 시 `UnicodeEncodeError` 발생 가능성을 고려해 try/except 래핑.
- Windows cp949 터미널 환경에서도 `errors="replace"` 방식으로 깨짐 없이 출력.
- `stats.py`의 `format_report()` 헤더에서 이모지(`📊`, `─`) 제거 → ASCII 문자(`[Stats]`, `-`)로 교체.

**import 추가**: `CoordinatorPhase`, `CostTracker`, `SessionStats` 3종 추가.

---

## [2026-05-04] Session 21: Claude Code 참조 고도화 — Stats · CostTracker · Memory 3-Scope · AgentTool · Coordinator

> **참조 출처**: Claude Code (codeaashu/claude-code) 소스 분석 결과를 Theseus 아키텍처에 맞게 재설계하여 구현. 5개 Feature를 구현 우선순위(Stats → CostTracker → Memory → AgentTool → Coordinator) 순으로 진행.

---

### Feature 5: 인메모리 Stats 히스토그램 [`theseus_engine/observability/stats.py`] [신규]

**목적**: LangSmith 없이도 세션 단위 성능 지표(툴 실행 시간, RAG 검색 시간, LLM 토큰 분포)를 실시간으로 측정.

**핵심 설계 — Reservoir Sampling (Algorithm R)**:
- 512개 샘플 상한으로 메모리 무제한 증가 없이 p50/p95/p99 퍼센타일 계산.
- N번째 관측값이 들어올 때 확률 512/N로 기존 샘플을 교체 → 균등 분포 보장.
- `sorted(reservoir)[int(len*p/100)]` 방식의 경량 퍼센타일 연산.

**신규 클래스**:
- `Histogram`: 단일 메트릭 Reservoir 샘플링 히스토그램. `observe(value)`, `percentile(p)`, `avg/count/min_val/max_val` 프로퍼티.
- `HistogramReport` (dataclass): count, avg, min, max, p50, p95, p99 스냅샷.
- `StatsReport` (dataclass): 툴별 duration/call/error 집계 + RAG/LLM/HITL 지표 포함.
- `SessionStats` (싱글톤): `get()` / `reset()` 클래스 메서드로 접근. `observe(metric, ms)`, `increment(metric, delta)`, `set_gauge(metric, value)` 기본 API.

**툴 타이머 API**:
- `tool_start(tool_name)`: `_tool_timers[name] = time.monotonic()` 저장.
- `tool_end(tool_name, is_error)`: `(monotonic() - start) * 1000` 으로 ms 계산 → `tool.<name>.duration_ms` 히스토그램에 기록. `tool.<name>.call_count` / `error_count` 카운터도 자동 증가.

**연동**:
- `TheseusHookExecutor.execute()`: PRE_TOOL_USE에서 `stats.tool_start()`, POST_TOOL_USE에서 `stats.tool_end(is_error=payload["is_error"])` 호출.
- `TheseusHookExecutor._check_hitl()`: `hitl.prompt_count`, `hitl.always_allow_count`, `hitl.blocked_count` 카운터 연동.
- `ToolRetriever.retrieve_top_k()`: `time.monotonic()` 기준 RAG 검색 전후 계측 → `rag.retrieval_ms` 기록.
- `engine_builder.setup_engine()`: 세션 시작 시 `SessionStats.reset()` 자동 호출.

**보고서**: `format_report()` → CLI `/stats` 명령 출력용 56자 구분선 테이블. 툴별 p50/p95, 호출/에러 횟수, RAG/LLM/HITL 섹션 포함.

---

### Feature 1: 비용/토큰 추적기 [`theseus_engine/engine/cost_tracker.py`] [신규]

**목적**: 멀티모델 환경(OpenAI·Anthropic·Google)에서 세션 단위 토큰 소비량과 USD 비용을 LangSmith 없이 즉시 집계.

**기본 단가표 (`_DEFAULT_PRICING`)** — USD / 1M tokens:

| 모델 | input | output | cache_read | cache_write |
|------|-------|--------|------------|-------------|
| gpt-4o | 2.50 | 10.00 | 1.25 | - |
| gpt-4o-mini | 0.15 | 0.60 | 0.075 | - |
| gpt-4-turbo | 10.00 | 30.00 | - | - |
| o1 | 15.00 | 60.00 | 7.50 | - |
| claude-opus-4 / 4-5 | 15.00 | 75.00 | 1.50 | 3.75 |
| claude-sonnet-4 / 4-6 | 3.00 | 15.00 | 0.30 | 3.75 |
| claude-haiku-4 | 0.80 | 4.00 | 0.08 | 1.00 |
| gemini-2.5-pro | 1.25 | 10.00 | - | - |
| gemini-2.5-flash | 0.075 | 0.30 | - | - |
| gemini-2.0-flash | 0.10 | 0.40 | - | - |

- `THESEUS_PRICING_TABLE` 환경변수에 JSON으로 단가 오버라이드 가능. 파싱 실패 시 경고 로그만 출력, 기본 단가 유지.

**신규 클래스**:
- `ModelUsage` (dataclass): 모델 한 종류의 input/output/cache_read/cache_creation 토큰 + cost_usd + call_count 누적.
- `SessionCost` (dataclass): 세션 전체 집계 (session_id, started_at, total_cost_usd, total_input/output/cache 토큰, total_tool_calls, model_usage 딕셔너리).
- `CostTracker` (싱글톤): `get_or_create(session_id)` / `reset()` 클래스 메서드.

**핵심 메서드**:
- `record(event)`: dict 또는 OpenHarness `UsageEvent` 객체 모두 처리. 내부에서 `record_usage()` 호출.
- `record_usage(model, input_tokens, output_tokens, cache_read, cache_creation)`: `_canonical_model()`로 모델명 정규화 → `_calculate_cost()` → 모델별/세션 전체 집계 누적. 발생 비용(USD) 반환.
- `_canonical_model(model)`: 모델명 소문자화 후 단가표 키 순회하여 부분 매칭으로 정규화 (예: `"claude-sonnet-4-6-20251015"` → `"claude-sonnet-4-6"`).
- `_calculate_cost()`: `(tokens * rate / 1_000_000)` 4항목 합산, `round(..., 8)` 처리.
- `increment_tool_calls(count)`: `total_tool_calls` 증가.
- `format_report()`: CLI `/cost` 명령용 60자 구분선 테이블. 모델별 입력/출력/캐시/비용, 합계 행, 툴 호출 횟수 출력.
- `save()`: `~/.theseus/cost_log.jsonl`에 JSONL 한 줄 추가. OSError 발생 시 경고 로그만 출력.

**엔진 연동**:
- `TheseusLLMClient.stream_message()`: 스트림 이벤트 중 `ApiMessageCompleteEvent` 감지 → `CostTracker.get_or_create().record_usage(model, input_tokens, output_tokens)` 자동 호출. try/except로 래핑하여 추적 실패가 스트림을 중단하지 않음.
- `engine_builder.setup_engine()`: `tracker = CostTracker.reset()` 초기화 → `tool_metadata["cost_tracker"]` 에 노출.
- **설계 결정**: OpenHarness `QueryEngine`이 자체 내부 `CostTracker`를 보유하나 외부 콜백을 제공하지 않아, LLM Client 스트림 인터셉트 방식을 채택. cache 토큰은 Anthropic Claude 응답에서만 제공되므로 현재는 0으로 집계됨.

---

### Feature 4: Agent Memory 3단계 스코핑 [`theseus_engine/memory/`] [신규]

**목적**: Claude Code의 `~/.claude/memory/`, `.claude/memory/`, `.claude/memory-local/` 3계층 메모리 구조를 Theseus에 이식. 에이전트가 프로젝트·사용자·로컬 컨텍스트를 지속적으로 기억하도록 지원.

**스코프 설계**:

| 스코프 | 경로 | 공유 범위 | git 추적 |
|--------|------|-----------|----------|
| `user` | `~/.theseus/memory/` | 모든 프로젝트 공통 | 아니오 |
| `project` | `.theseus/memory/` | 프로젝트 팀 전체 | 예 |
| `local` | `.theseus/memory-local/` | 로컬 개인 전용 | 아니오 (gitignore) |

**신규 파일: `theseus_engine/memory/scoped_memory.py`**:
- `MemoryScope` (str Enum): `USER`, `PROJECT`, `LOCAL`.
- `ScopedMemory`: `cwd` 파라미터로 프로젝트 루트 지정 (기본값 `Path.cwd()`). 사용자 홈 디렉터리는 `THESEUS_DATA_DIR` 환경변수 오버라이드 가능.
- `write(scope, filename, content)`: 해당 스코프 디렉터리에 `.md` 파일 저장. `.md` 확장자 자동 추가.
- `read(scope, filename)`: 파일 존재 시 UTF-8 텍스트 반환, 없으면 `None`.
- `delete(scope, filename)`: 파일 삭제, 성공 여부 bool 반환.
- `list_files(scope)`: 스코프 디렉터리의 `*.md` 파일명 목록 반환 (정렬).
- `read_context()`: user → project → local 순으로 모든 스코프를 순회하여 `# Agent Memory` 섹션으로 합산. 시스템 프롬프트 직접 주입용. 파일 없으면 빈 문자열 반환.
- `ensure_gitignore()`: 프로젝트 `.gitignore`에 `.theseus/memory-local/` 미존재 시 자동 추가.

**신규 파일: `theseus_engine/tools/core/memory_tools.py`**:
- `MemoryWriteTool` (`memory_write`): scope/filename/content 입력 → 지정 스코프에 파일 저장. `is_read_only=False`, `is_destructive=False`, `permission_level=1`.
- `MemoryReadTool` (`memory_read`): scope/filename 입력 → 파일 내용 반환.
- `MemoryListTool` (`memory_list`): scope 입력 (`all` 포함) → 스코프별 파일 목록 반환.
- 3종 모두 `ALL_CORE_TOOLS` 및 `theseus_engine/tools/core/__init__.py`에 등록.

**엔진 연동 (`engine_builder.py`)**:
- `ScopedMemory` import 추가.
- `setup_engine()` 초기화 시:
  1. `scoped_memory = ScopedMemory(cwd=Path.cwd())` 생성.
  2. `scoped_memory.ensure_gitignore()` 호출 (최초 1회 `.gitignore` 자동 설정).
  3. `memory_context = scoped_memory.read_context()` 로드.
  4. `sm.get_system_prompt() + "\n\n" + memory_context` 로 시스템 프롬프트에 주입.
  5. `tool_metadata["scoped_memory"]` 로 도구에서 접근 가능하도록 노출.

---

### Feature 2: AgentTool 컨텍스트 전달 개선 [`theseus_engine/tools/core/agent_tool.py`] [수정]

**목적**: 서브 에이전트 스폰 시 부모 RBAC 레벨·모드·환경 컨텍스트가 무단 권한 상승 없이 안전하게 전달되도록 보장.

**`AgentInput` 신규 필드**:
- `max_rbac_level: Optional[int]`: 서브 에이전트에 허용할 최대 RBAC 레벨 (1~5). 미지정 시 부모 레벨 상속.
- `inherit_context: bool` (기본 `False`): True이면 부모의 `agent_mode` 환경변수를 서브 에이전트에 전달.
- `timeout_seconds: Optional[int]` (기본 `300`): 서브 에이전트 실행 타임아웃 (향후 TaskManager 타임아웃 연동용).

**RBAC 상속 로직**:
```
parent_rbac = context.metadata.get("user_rbac_level", 3)
sub_rbac = min(arguments.max_rbac_level ?? parent_rbac, parent_rbac)
```
- 서브 에이전트 RBAC는 부모 레벨을 초과할 수 없음. 권한 상승(privilege escalation) 차단.

**환경 변수 전파**:
- `THESEUS_SUBAGENT=1`: 서브 에이전트 실행 컨텍스트임을 표시. 향후 로깅/비용 집계 분리에 활용.
- `OPENHARNESS_MODEL`: 지정 모델을 서브 에이전트에 주입.
- `inherit_context=True` 시 `THESEUS_AGENT_MODE` 추가 전파.

**출력 개선**: `ToolResult.metadata`에 `sub_rbac_level`, `parent_rbac_level` 포함. 로그에 RBAC 레벨 차이 기록.

**`engine_builder.py` 연동**:
- `tool_metadata["user_rbac_level"] = user_level`: AgentTool이 부모 RBAC를 읽는 데 사용.
- `tool_metadata["agent_mode"] = sm.mode.value`: 현재 모드 정보 전달.

---

### Feature 3: Coordinator 모드 [`theseus_engine/models/state.py`, `tui_main.py`] [수정]

**목적**: 복잡한 작업을 병렬 서브 에이전트로 분해·배포·합성·검증하는 4단계 오케스트레이션 파이프라인 모드 도입. Claude Code의 멀티 에이전트 패턴 참조.

**`theseus_engine/models/state.py` 변경**:

1. `AgentMode.COORDINATOR = "Coordinator"` 추가 (기존 ASK/AGENT/PLAN 외 4번째 모드).
2. `CoordinatorPhase` Enum 신규 추가:
   - `DECOMPOSE`: 작업 분해. 병렬 서브태스크 목록 생성.
   - `DISPATCH`: 워커 배포 및 모니터링.
   - `SYNTHESIZE`: 워커 결과 통합 및 병합.
   - `VERIFY`: 최종 결과 검증 및 원본 요구사항 대조.
3. `MODE_DESCRIPTIONS`에 Coordinator 설명 추가.
4. **4개 단계별 전용 시스템 프롬프트** 추가:
   - `_COORDINATOR_DECOMPOSE_PROMPT`: 2~6개 원자적·병렬 서브태스크 분해 → JSON list 출력 → `agent` 툴로 배포 지시.
   - `_COORDINATOR_DISPATCH_PROMPT`: `task_output`으로 진행 모니터링, 실패 워커 재시도/적응 지시.
   - `_COORDINATOR_SYNTHESIZE_PROMPT`: 결과 통합·충돌 해결·요청 범위 내 병합 지시.
   - `_COORDINATOR_VERIFY_PROMPT`: 테스트/검증 실행, 원본 요구사항 대조, 미해결 이슈 솔직하게 보고 지시.
5. `TheseusStateMachine` 개선:
   - `coordinator_phase: Optional[CoordinatorPhase]` 필드 추가.
   - `switch_mode(COORDINATOR)` 시 `coordinator_phase = CoordinatorPhase.DECOMPOSE` 자동 초기화.
   - `set_coordinator_phase(phase)` 메서드 추가 (단계 전환 + 콘솔 출력).
   - `display_mode` 프로퍼티: `"Coordinator/Decompose"` 형태 반환.
   - `get_system_prompt()`: COORDINATOR 모드일 때 단계별 프롬프트 분기 추가.
   - UnicodeEncodeError 방지: `switch_mode()` print 문에 try/except 래핑 (Windows cp949 환경 대응).

**`theseus_engine/tui/tui_main.py` 변경**:
- `CoordinatorPhase` import 추가.
- `action_switch_coordinator()` 메서드 추가: 모드 전환 + 시스템 프롬프트 갱신 + `create_tool` 제외 레지스트리 설정.
- `_sync_permission_mode()`: `AgentMode.COORDINATOR → PermissionMode.FULL_AUTO` 매핑 추가.
- `_cmd_coordinator()` 비동기 핸들러 추가.
- `SlashCommand` 목록에 `coordinator` 등록.
- `theseus_cmd_handlers` 딕셔너리 및 `TheseusInput` 인터셉터 집합 모두에 `"coordinator"` 추가.

**사용 흐름**:
```
/coordinator          → Decompose 단계 시작, 작업 분해 프롬프트 활성화
sm.set_coordinator_phase(CoordinatorPhase.DISPATCH)    → 워커 배포 단계
sm.set_coordinator_phase(CoordinatorPhase.SYNTHESIZE)  → 결과 통합 단계
sm.set_coordinator_phase(CoordinatorPhase.VERIFY)      → 최종 검증 단계
```

---

### 변경 파일 요약

| 파일 | 변경 유형 | 주요 내용 |
|------|-----------|-----------|
| `theseus_engine/observability/stats.py` | 신규 | Reservoir Sampling Stats 시스템 |
| `theseus_engine/engine/cost_tracker.py` | 신규 | 멀티모델 USD 비용 추적기 |
| `theseus_engine/memory/__init__.py` | 신규 | 메모리 패키지 초기화 |
| `theseus_engine/memory/scoped_memory.py` | 신규 | 3단계 스코프 메모리 관리자 |
| `theseus_engine/tools/core/memory_tools.py` | 신규 | MemoryWrite/Read/List 도구 3종 |
| `theseus_engine/tools/core/agent_tool.py` | 수정 | RBAC 상속, 컨텍스트 전파 강화 |
| `theseus_engine/models/state.py` | 수정 | CoordinatorPhase + COORDINATOR 모드 프롬프트 |
| `theseus_engine/wrappers/hooks/theseus_hook_executor.py` | 수정 | stats.tool_start/end 연동 |
| `theseus_engine/wrappers/llm_clients/theseus_client.py` | 수정 | CostTracker 스트림 인터셉트 |
| `theseus_engine/core/tool_retriever.py` | 수정 | RAG 검색 시간 계측 |
| `theseus_engine/core/engine_builder.py` | 수정 | CostTracker/ScopedMemory 초기화 및 tool_metadata 확장 |
| `theseus_engine/tui/tui_main.py` | 수정 | /coordinator 슬래시 명령어 추가 |
| `theseus_engine/tools/core/__init__.py` | 수정 | 메모리 도구 3종 등록 |

## [2026-05-04] Session 20: Tool Calling 고도화 — 보안 강화 · RAG 폴백 · HITL

### 🚀 주요 변경 사항

*   **[Task 1] BashTool 보안 패턴 강화 (`execution_validator.py`)**:
    *   기존 Regex 2개(HTTP 변이, 파일시스템 파괴)에 Bash 전용 위험 패턴 4종 추가.
    *   `_BASH_DESTRUCTIVE_PATTERN`: `rm -rf`, `dd if=`, `mkfs.*`, `shred` 등 파일시스템 파괴 명령 탐지.
    *   `_BASH_RCE_PATTERN`: `curl ... | bash`, `eval $(...)`, `base64 -d | sh` 등 원격 코드 실행 패턴 탐지.
    *   `_BASH_PRIVILEGE_PATTERN`: `sudo rm`, `chmod -R 777`, `chown -R root` 등 권한 상승 명령 탐지.
    *   `_BASH_PATH_TRAVERSAL_PATTERN`: `> /etc/`, `> /bin/`, `../../../` 등 시스템 경로 탈출 탐지.
    *   모든 패턴은 `tool_name == "bash"` 일 때만 적용되어 타 툴에 영향 없음. 기존 PRE_TOOL_USE Hook 파이프라인에 자동 연결됨.

*   **[Task 2] ToolSearchTool 구현 및 RAG 폴백 전략 (`tool_search_tool.py`, `engine_builder.py`)**:
    *   신규 파일 `theseus_engine/tools/core/tool_search_tool.py` 생성.
    *   `ToolSearchTool`: 자연어 쿼리로 `full_registry`에서 시맨틱 검색 → 매칭 툴을 `active_registry`에 즉시 주입 → 툴 이름·설명·입력 스키마 반환.
    *   `engine_builder.py`에 RAG 실패 감지 로직 추가: `ESSENTIAL_TOOL_NAMES` 외 유사도 선택이 0개이거나 예외 발생 시 `rag_failed = True` 플래그 설정.
    *   `rag_failed` 시 `ToolSearchTool`을 `active_registry`에 자동 활성화. RAG 성공 시에는 노출하지 않아 불필요한 컨텍스트 낭비 방지.
    *   `tool_metadata`에 `active_registry` 키 추가. `ToolSearchTool`이 런타임에 직접 레지스트리에 접근하여 즉시 주입 가능.
    *   `ALL_CORE_TOOLS` 및 `__init__.py`에 `ToolSearchTool` 등록.

*   **[Task 3] POST_TOOL_USE 동적 주입 쿼리 품질 개선 (`theseus_hook_executor.py`)**:
    *   기존 `tool_output[:500]` 원문 그대로 사용하던 방식을 `_build_injection_query()` 정적 메서드로 대체.
    *   툴 이름 + 입력 키(값 제외, 민감 정보 노출 방지) + 출력 신호(파일 확장자, 에러/파일 미발견/권한/타임아웃 패턴) 조합으로 쿼리 생성.
    *   노이즈 많은 원문 대신 의미 있는 키워드 중심 쿼리 사용으로 시맨틱 검색 정확도 향상.

*   **[Task 4] `is_destructive` / `is_read_only` 플래그 및 HITL 레이어 구현**:
    *   파괴적 툴 3종에 `is_destructive = True` 추가: `BashTool`, `WriteFileTool`, `EditFileTool`.
    *   읽기 전용 툴 3종에 `is_read_only = True` / `is_destructive = False` 추가: `ReadFileTool`, `GlobTool`, `GrepTool`.
    *   `ToolSearchTool`에도 `is_read_only = True`, `is_destructive = False` 명시.
    *   **Security Pipeline Fixes**:
    *   **AgentHook Refinement**: Removed `read_file` from the security auditor's scope (AgentHook) to prevent false-positive blocks that replaced file content with `{"ok": true}`.
    *   **Markdown Robustness**: Added a heuristic unblocker in `TheseusHookExecutor` to handle LLM auditors returning Markdown-wrapped JSON, preventing unexpected security blocks.
    *   **Tool Result Serialization**: Fixed `number_sorter.py` to use `json.dumps()`, resolving Pydantic validation errors in the `ToolResult` model.
    *   **Interactive HITL**: Integrated a "warn-then-override" mechanism for sensitive tools.
    *   `TheseusHookExecutor`에 `_check_hitl()` 비동기 메서드 추가: `is_destructive=True` 툴 실행 전 `permission_prompt` 콜백을 호출하여 사용자 승인 요청.
    *   응답 `y`/`yes`/`1` → 1회 허용, `a`/`always` → 세션 내 `_always_allow` 캐시에 등록(재확인 면제), 그 외 → `HookResult(blocked=True)`로 차단.
    *   `permission_prompt` 콜백 미제공(비대화형 환경) 시 자동 허용하여 기존 자동화 파이프라인과 하위 호환 유지.

---

## ⚠️ Known Issues / Next Steps
- **Phase 5 (단기)**: Sandbox 도입, Memory System 통합, Hooks + LangSmith 연동 고도화, 세션 저장/복원
- **Phase 6 (중기)**: MCP Client 통합, 멀티 에이전트 (Swarm), Skills & Plugin System
