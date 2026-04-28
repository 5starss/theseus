# Changelog

## [Unreleased] - 2026-04-27

### 🚀 Features (주요 구현 내용)

#### Session 7 (2026-04-27)

- **`ToolExecutionCompleted` 오류 수정**:
  - `theseus_engine/app.py`에서 발생하는 `'ToolExecutionCompleted' object has no attribute 'result'` 오류의 원인을 분석했습니다.
  - OpenHarness의 `stream_events.py` 소스 코드를 직접 확인하여 `ToolExecutionCompleted` 객체의 결과 속성이 `result`가 아닌 `output`임을 명확히 파악했습니다.
  - 사용자에게 `app.py`의 `event.result`를 `event.output`으로 직접 수정하도록 안내하여 핵심 실행 루프의 오류를 해결했습니다.

- **TUI(Text-based User Interface) 도입 계획 수립**:
  - 사용자가 `@` 문자를 통해 파일 시스템에 쉽게 접근할 수 있는 UI 기능 추가를 요청했습니다.
  - 현재의 단순 CLI 환경에서 GUI 팝업 구현의 기술적 어려움(실행 환경, 복잡성, 원격 실행 문제)을 분석하고 설명했습니다.
  - 대안으로 Python의 `Textual` 라이브러리를 사용하여 터미널 내에서 동작하는 TUI 파일 선택기를 구현하는 방안을 제시했습니다.
  - 해당 구현 계획, 주요 구성 요소, 의사코드, 고려사항 등을 상세히 담은 `textual_implementation_plan.md` 문서를 작성하여 향후 엔진 개발 로드맵을 구체화했습니다.

#### Session 6 (2026-04-27)

- **LLM API 통신 호환성 및 자동 복구(Auto-Recovery) 강화**:
  - **Gemini 3.1 Pro 도구 호출(`thought_signature` 누락) 400 에러 해결**:
    - 최신 Gemini 모델의 Function Calling 과정에서 발생하는 `thought_signature` 누락 현상을 해결하기 위해 `theseus_engine/monkey_patches.py` 신규 작성.
    - OpenHarness 패키지의 내부 코드를 오염시키지 않기 위해 런타임에 동적으로 `_stream_once` 제너레이터와 `_parse_assistant_response`, `_convert_assistant_message`를 가로채는(Monkey-patching) 방식으로 구현.
    - 스트리밍 조각(Chunk)을 수집할 때 무시되던 `extra_content`를 추출하여 보존한 뒤 다음 턴에 다시 전달함으로써 Gemini 환경 완벽 호환.
  - **API `ErrorEvent` 자가 복구 루프 구축**:
    - `test_phase2_3.py` 루프에서 API 통신 단절이나 기타 예외 상황 시 시스템이 종료되는 문제 개선.
    - `Exceeded maximum turn limit` 방어 메커니즘과 동일한 사상으로, API 레벨의 예외(`ErrorEvent`) 발생 시 에러 내용을 LLM에게 다시 피드백(`System Error Encountered...`)하여 자가 치유를 시도하도록 로직 추가.

### 🔧 Changes (변경 사항)

- (해당 세션에서 핵심 기능 변경 사항 없음)

### 📋 Documentation

- **`docs/history/CHANGELOG_25_pro.md`**: 신규 작성. Session 7의 핵심 작업 내역을 기록.
- **`textual_implementation_plan.md`**: 신규 작성. `@` 파일 선택기 기능을 위한 Textual TUI 구현 계획 및 의사코드 포함.
