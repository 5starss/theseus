# Textual TUI를 이용한 `@` 파일 선택기 구현 방안

### 1. 목표
사용자가 커맨드 라인 입력창에 `@` 문자를 입력했을 때, 터미널 내에서 인터랙티브한 파일 및 디렉토리 선택기(File Picker)를 모달(Modal) 형태로 띄웁니다. 사용자는 키보드로 파일을 탐색하고 선택할 수 있으며, 선택된 파일의 경로는 자동으로 입력창에 완성됩니다.

### 2. 핵심 컨셉: 단순 CLI에서 TUI(Text-based User Interface)로의 전환
- **현재 구조:** 현재 `app.py`는 `input()`과 `print()`에 의존하는 단순 순차 실행 구조입니다. 이는 키 입력 감지나 화면의 특정 부분만 업데이트하는 등의 복잡한 상호작용이 불가능합니다.
- **도입할 구조:** Python 라이브러리인 **`Textual`**을 도입하여 애플리케이션의 UI를 이벤트 기반으로 재구성합니다. 이를 통해 터미널 화면 전체를 하나의 애플리케이션처럼 제어할 수 있게 되며, '팝업'과 같은 동적인 위젯 구현이 가능해집니다.

### 3. 주요 구성 요소 및 구현 단계

**A. 의존성 추가**
- `pyproject.toml` 이나 `requirements.txt`에 `textual`을 추가해야 합니다.
  ```bash
  pip install textual
  ```

**B. 애플리케이션 구조 리팩토링 (`app.py`)**
- 현재의 `while True` 루프를 `textual.app.App` 클래스를 상속받는 새로운 메인 애플리케이션 클래스(예: `TheseusApp`)로 대체해야 합니다.
- `TheseusApp`은 다음과 같은 기본 위젯을 가집니다.
    1.  **대화 내용 표시 영역:** `textual.widgets.RichLog`를 사용하여 이전 대화 내용을 스크롤하며 볼 수 있는 화면을 구성합니다.
    2.  **사용자 입력 영역:** `textual.widgets.Input`를 사용하여 사용자의 명령어를 입력받습니다.
    3.  **상태 표시줄:** `textual.widgets.Footer`를 사용하여 모드(`AGENT`, `PLAN` 등)나 단축키 정보를 표시합니다.

**C. 파일 선택기 모달 화면 구현**
- `textual.screen.ModalScreen`을 상속받는 `FilePickerModal` 클래스를 새로 작성합니다.
- 이 모달 화면의 핵심 위젯은 `textual.widgets.DirectoryTree`가 됩니다. 이 위젯은 지정된 경로의 파일과 디렉토리를 트리 형태로 보여주며, 키보드 탐색 기능을 기본적으로 제공합니다.
- 사용자가 `Enter` 키로 파일이나 디렉토리를 선택했을 때의 동작을 정의합니다. (예: `action_select_file`)

**D. `@` 트리거 메커니즘 구현**
- 메인 앱(`TheseusApp`)의 `Input` 위젯에서 사용자의 입력이 변경될 때마다 이를 감시하는 로직을 추가합니다. (`watch_` 메서드나 `@on(Input.Changed)` 데코레이터 사용)
- `Input` 위젯의 값이 비어있거나 `@` 문자로 시작하는 경우, `app.push_screen(FilePickerModal())`을 호출하여 파일 선택기 모달을 화면에 띄웁니다.

**E. 선택 결과 반환 및 입력창 자동 완성**
- `FilePickerModal`에서 사용자가 파일을 선택하고 `Enter`를 누르면, 모달은 선택된 파일의 절대 또는 상대 경로를 결과값으로 하여 닫힙니다 (`self.dismiss(result=selected_path)`).
- `app.push_screen`은 콜백(callback) 함수를 받을 수 있습니다. 이 콜백 함수는 모달이 닫힐 때 반환된 결과값(파일 경로)을 받아, 메인 화면의 `Input` 위젯에 해당 경로를 자동으로 채워 넣는 역할을 합니다.

### 4. 예시 의사코드 (Pseudocode)

```python
# app.py (리팩토링 후의 모습)
from textual.app import App, ComposeResult
from textual.widgets import RichLog, Input, Footer, DirectoryTree
from textual.screen import ModalScreen
from textual import on

class FilePickerModal(ModalScreen):
    """파일 선택을 위한 모달 화면"""

    def compose(self) -> ComposeResult:
        # 현재 작업 디렉토리를 기준으로 파일 트리를 보여줌
        yield DirectoryTree(".")

    def on_directory_tree_file_selected(self, event: DirectoryTree.FileSelected):
        """사용자가 파일을 선택했을 때 실행"""
        # 선택된 파일 경로를 결과로 반환하며 모달을 닫음
        self.dismiss(result=str(event.path))

class TheseusApp(App):
    """메인 Textual 애플리케이션"""

    def compose(self) -> ComposeResult:
        yield RichLog(id="history", wrap=True) # 대화 내용
        yield Input(placeholder="Enter your command...") # 사용자 입력
        yield Footer()

    @on(Input.Submitted)
    async def handle_submission(self, event: Input.Submitted):
        """사용자가 Enter를 쳤을 때"""
        user_input = event.value
        self.query_one("#history").write(f"> {user_input}")
        self.query_one(Input).value = "" # 입력창 비우기

        # 여기에 기존의 engine.submit_message() 비동기 로직 호출
        # 결과를 RichLog에 스트리밍으로 표시하는 워커 실행
        # 예시: async for chunk in engine.submit_message(user_input):
        #           self.query_one("#history").write(chunk)

    @on(Input.Changed)
    def check_for_trigger(self, event: Input.Changed):
        """입력창 내용이 바뀔 때마다 확인"""
        if event.value == "@":
            # 입력값이 '@'이면 파일 선택기를 띄움
            self.push_screen(FilePickerModal(), self.on_file_selected)

    def on_file_selected(self, path: str):
        """파일 선택기가 닫히고 경로를 받았을 때 실행되는 콜백"""
        if path:
            # 입력창의 내용을 선택된 경로로 업데이트
            self.query_one(Input).value = f"@{path}"
            self.query_one(Input).focus()

if __name__ == "__main__":
    app = TheseusApp()
    app.run()
```

### 5. 주요 과제 및 고려사항
- **리팩토링 규모:** 기존의 간단한 `asyncio` + `input` 루프를 완전한 `Textual` 애플리케이션으로 전환하는 것은 상당한 초기 작업이 필요합니다.
- **비동기 처리 통합:** `engine.submit_message`는 비동기 스트리밍 함수입니다. `Textual`은 비동기 작업을 잘 지원하므로, `run_worker` 등을 사용하여 엔진의 응답을 `RichLog` 위젯에 실시간으로 업데이트하는 로직을 신중하게 구현해야 합니다.
- **사용자 경험(UX):** 파일 탐색 중 `ESC` 키로 취소하는 기능, 현재 경로를 표시하는 기능 등 부가적인 UX 개선이 필요합니다.
