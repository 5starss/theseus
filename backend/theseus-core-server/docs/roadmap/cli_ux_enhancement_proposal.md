# 🛠️ CLI UX Enhancement Strategy: prompt_toolkit

## 1. 개요 (Context)
현재 Theseus 프로젝트의 메인 클라이언트는 Textual 기반의 **TUI(tui_app.py)**로 이동하고 있습니다. 하지만 서버 환경이나 레거시 터미널, 혹은 SSH를 통한 원격 접속 시 TUI 렌더링이 불안정할 수 있는 경우를 대비해 **순수 CLI 모드(app.py)**의 유지보수 및 강화 전략이 필요합니다.

본 문서는 파이썬 내장 `input()` 함수의 한계를 극복하고, CLI 환경에서도 상용 수준의 UX를 제공하기 위한 `prompt_toolkit` 도입 방안을 제안합니다.

---

## 2. 왜 `prompt_toolkit` 인가?
OpenHarness 프레임워크는 이미 내부적으로 `prompt-toolkit>=3.0.0`에 의존하고 있습니다. 따라서 추가적인 패키지 설치 없이 즉시 도입이 가능하며, 다음과 같은 강력한 기능을 CLI에 이식할 수 있습니다.

- **Tab 기반 자동완성**: 슬래시 명령어 및 파일 경로에 대한 인라인 제안.
- **히스토리 탐색**: 위/아래 방향키를 통한 이전 입력 내역 복원.
- **멀티라인 편집**: 복잡한 프롬프트 작성이 용이한 편집 환경.
- **구문 강조(Syntax Highlighting)**: 입력 중인 명령어에 대한 실시간 색상 적용.

---

## 3. 핵심 구현 기능

### 3.1 Slash Command Autocomplete
사용자가 `/`를 입력하고 Tab을 누르면 Theseus의 특수 명령어(` /plan`, `/agent`, `/ask`, `/session` 등) 목록을 표시합니다.

### 3.2 File Mention Autocomplete (@)
`@` 문자를 인식하여 현재 작업 디렉토리 내의 파일 목록을 동적으로 스캔하고 제안합니다. TUI에서 구현된 `iterdir()` 기반의 고도화된 로직을 CLI에도 동일하게 적용할 수 있습니다.

### 3.3 Persistent History
세션별 혹은 전역 대화 내역을 파일로 저장하여, 앱을 재시작하더라도 이전 입력값들을 방향키로 쉽게 불러올 수 있게 합니다.

---

## 4. 제안 코드 구조 (Refactoring Blueprint)

```python
from prompt_toolkit import prompt
from prompt_toolkit.completion import Completer, Completion
from theseus_engine.sessions import list_sessions
import os

class TheseusCLICompleter(Completer):
    def get_completions(self, document, complete_event):
        text = document.text_before_cursor
        
        # 1. 명령어 자동완성 (/)
        if text.startswith('/'):
            commands = ['/ask', '/agent', '/plan', '/session', '/clear', '/exit']
            for cmd in commands:
                if cmd.startswith(text):
                    yield Completion(cmd, start_position=-len(text))
                    
        # 2. 파일 자동완성 (@)
        elif '@' in text:
            # 마지막 @ 이후의 텍스트를 경로 접두사로 인식
            parts = text.split('@')
            path_prefix = parts[-1]
            try:
                # 현재 디렉토리 스캔
                for filename in os.listdir('.'):
                    if filename.startswith(path_prefix):
                        yield Completion(f"@{filename}", start_position=-len(path_prefix)-1)
            except Exception:
                pass

# 사용 예시
# user_input = await asyncio.to_thread(prompt, "> ", completer=TheseusCLICompleter())
```

---

## 5. 전략적 리소스 분배 (Priority)

현재 Theseus 개발의 우선순위는 다음과 같이 설정합니다.

1.  **Priority 1 (TUI Focus)**: `tui_app.py`의 기능적 완성도와 시각적 안정성 확보.
2.  **Priority 2 (CLI Fallback)**: `app.py`는 현재의 `input()` 기반 단순 형태를 유지하되, TUI 환경이 제한적인 사용자 피드백이 발생할 경우 `prompt_toolkit`으로 업그레이드 수행.
3.  **Long-term Goal**: CLI와 TUI가 동일한 비즈니스 로직(세션, RBAC)을 공유하되, I/O 레이어만 환경에 맞게 최적화된 하이브리드 클라이언트 아키텍처 완성.

---

## 6. 결론
`prompt_toolkit`은 CLI 모드를 "구식 인터페이스"에서 "전문가용 고속 도구"로 탈바꿈시킬 수 있는 핵심 열쇠입니다. TUI 고도화가 정점에 도달한 시점에 이 전략을 실행하여 Theseus의 접근성을 극대화할 것을 권장합니다.
