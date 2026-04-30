# Theseus-Gemini 통합 및 아키텍처 개선 보고서

- **작성일**: 2026-04-29
- **작성자**: Antigravity (Theseus AI Agent)
- **대상**: Gemini 3.1 Pro 기반 에이전트 시스템 안정화 및 TUI 커맨드 인터셉트

---

## 1. Gemini 3.1 Pro 도구 사용(Tool Use) 통합 분석

### 1.1 문제 현상
Google Gemini 3.1 Pro 모델은 OpenAI 호환 API를 제공하지만, 도구 사용 시 `thought_signature` (또는 `extra_content`)라는 비표준 필드를 필수적으로 요구합니다. 
- **수집**: LLM이 도구를 호출할 때 이 필드를 함께 보냅니다.
- **재주입**: 도구 실행 결과를 다시 LLM에게 보낼 때, **이전 턴의 도구 호출 정보에 이 필드가 그대로 포함되어 있어야 합니다.**
- **누락 시**: `400 Bad Request (INVALID_ARGUMENT)` 에러가 발생하며 "Missing thought signature" 메시지를 반환합니다.

### 1.2 해결 과정 (Evolution)
1. **v1. Monkey-Patching (External)**: `theseus_client.py`에서 런타임에 OpenAI 클라이언트의 메서드를 덮어쓰려 했으나, OpenHarness 엔진이 매 요청마다 클라이언트를 새로 생성/교체하면서 패치가 소멸되는 불안정성 발생.
2. **v2. Wrapper Class**: `TheseusGeminiClient` 래퍼를 통해 처리하려 했으나, 여전히 엔진 내부의 리프레시 로직과 충돌.
3. **v3. Core Integration (Final)**: OpenHarness 코어 코드(`openai_client.py`)에 Gemini 전용 처리 로직을 직접 통합.
    - `_patch_gemini_messages()` 함수를 통해 도구 결과 전송 직전, 메시지 히스토리에서 캡처해둔 `extra_content`를 자동으로 복원.
    - 엔진의 어떤 로직도 이 과정을 방해할 수 없도록 가장 기저 레벨에서 처리하여 완벽한 안정성 확보.

---

## 2. Textual TUI 이벤트 바이패스 해결

### 2.1 문제 현상
`TheseusTUI`(App)에서 `/plan`, `/agent` 같은 전용 슬래시 커맨드를 가로채려고 했으나, 부모 클래스인 `OpenHarnessTerminalApp` 역시 동일한 이벤트를 동시에 처리하려 시도함.
- **결과**: Theseus 로직이 실행되기도 전에 부모 클래스의 로직이 먼저 실행되어 "Unknown command" 에러가 발생하거나 텍스트가 일반 대화로 흘러들어가는 현상 발생.

### 2.2 해결책: `TheseusInput` 커스텀 위젯 도입
- **원리**: Textual의 이벤트 버블링(Widget → Container → App) 구조 활용.
- **구현**: `Input` 위젯을 상속받은 `TheseusInput`을 만들고, 여기서 `event.stop()`을 호출.
- **효과**: 이벤트가 위젯 레벨에서 '소멸'되므로, 최상단 App(오픈하네스)은 해당 커맨드가 입력되었다는 사실조차 모르게 되어 충돌 가능성을 물리적으로 차단.

---

## 3. 주요 트러블슈팅 사례

| 문제점 | 원인 | 해결책 |
| :--- | :--- | :--- |
| **API Error: sys is not defined** | 디버그 로깅 함수(`_dump_debug_payload`)에서 `import sys` 누락 | `theseus_client.py` 상단에 명시적 임포트 추가 |
| **400 Authorization Error** | `theseus_cli.py`에서 `.env` 파일을 로드하지 않아 API 키 누락 | `python-dotenv`를 통한 환경 변수 로드 로직 추가 |
| **Event Loop Cancelled Error** | CLI 종료 시 비동기 루프의 강제 중단 | `KeyboardInterrupt` 예외 처리 및 세션 자동 저장 로직 보강 |
| **Old Session 400 Error** | `thought_signature`가 없던 과거 메시지가 히스토리에 남음 | `.theseus_sessions/default.json` 초기화 |

---

## 4. 향후 과제 (Next Steps)
- **Base64 Protobuf Validation**: Gemini의 서명이 단순 문자열이 아닌 Protobuf 형식을 요구할 경우에 대비한 `_FALLBACK_EXTRA_CONTENT` 보강.
- **Multi-Turn Reliability**: 5회 이상의 연속 도구 호출 시 서명 유실 여부 지속 모니터링.
- **Sandbox Integration**: 현재 로컬에서 실행되는 도구들을 격리된 환경으로 전송하는 파이프라인 구축.
