# OpenHarness TUI 커스텀 명령어 등록 이슈 및 해결 보고서

## 1. 개요 (Issue Overview)
Theseus TUI(`tui_app.py`) 개발 중, 사용자 정의 슬래시 명령어(`/plan`, `/agent`, `/ask` 등)를 OpenHarness 런타임에 등록했으나, TUI의 자동완성 목록과 실제 명령어 실행 시 OpenHarness의 기본 명령어 동작과 설명(Description)이 덮어씌워지지 않고 계속해서 나타나는 **명령어 무시/오버라이드 실패 버그**가 발생했습니다.

## 2. 근본 원인 분석 (Root Causes)
이 문제는 단순한 코드 오타가 아닌 파이썬 모듈 로딩 및 객체 참조의 복합적인 문제로 판단됩니다.

*   **초기화 순서 및 객체 상태 유지 (State Retention)**: 
    `build_runtime()` 호출 시 OpenHarness의 기본 명령어들이 레지스트리에 등록됩니다. 이후 `tui_app.py`에서 이 레지스트리 객체를 수정하려 했으나, 내부적으로 원본 명령어 데이터가 캐싱되거나 복원되는 로직이 개입했을 가능성이 있습니다.
*   **모듈 파편화 (Module Fragmentation)**:
    `sys.path.insert(0, str(PROJECT_ROOT / "OpenHarness" / "src"))`를 통해 OpenHarness 모듈을 강제 로드하면서, 시스템에 이미 설치된 패키지와 로컬 디렉토리의 패키지가 충돌하여 파이썬 메모리 상에 `CommandRegistry`나 `SlashCommand` 객체가 두 개 이상 생성되었을(분리되었을) 가능성이 높습니다. 즉, TUI가 수정하는 레지스트리와 코어 엔진이 실행 시 참조하는 레지스트리/타입이 서로 달랐을 수 있습니다.
*   **불변성 및 딕셔너리 직접 수정 실패**:
    `registry.register(cmd)` 메서드 호출 및 내부 딕셔너리(`_commands`) 강제 덮어쓰기를 시도하고, 번들의 `commands` 객체를 통째로 새 객체로 교체했음에도 엔진(`handle_line`)에서는 예전 데이터가 호출되었습니다. 이는 부모 클래스나 이벤트 루프 어딘가에서 기존 번들 객체의 참조를 끈질기게 유지하고 있음을 의미합니다.

## 3. 문제 해결을 위한 시도 과정 (Attempted Solutions)
1.  **일반적인 등록 (Failed)**: `self._bundle.commands.register()` 사용.
2.  **레지스트리 강제 주입 (Failed)**: `registry._commands` 딕셔너리에 직접 접근하여 키-값을 강제로 덮어쓰기.
3.  **UI 렌더링 강제 수정 (Partial Success)**: 렌더링 직전에만 설명을 바꿔치기하려 했으나, 실제 명령어 실행(`handle_line`) 시에는 여전히 OpenHarness의 기존 핸들러가 동작함.
4.  **레지스트리 객체 완전 교체 (Failed)**: 새로운 `CommandRegistry` 객체를 만들고 번들의 `commands` 속성을 완전히 교체했으나, 명령어 실행 시 예전 객체나 클래스가 참조됨.
5.  **모듈 강제 재로드 (Failed)**: `importlib.reload`를 통해 모듈 스코프를 동기화하려 했으나 해결되지 않음.

## 4. 최종 해결책: `_process_line` 오버라이드 (The Definitive Fix)

### 진짜 근본 원인 발견
위의 모든 시도가 실패한 이유는 **명령어 레지스트리가 문제의 본질이 아니었기 때문**입니다. 
진짜 원인은 부모 클래스 `OpenHarnessTerminalApp._process_line` → `handle_line()` (runtime.py:482)에 있었습니다.

`handle_line()`은 **매 턴마다** 다음을 수행합니다:
1. `bundle.commands.lookup(line)` — 파편화된 레지스트리를 참조 (명령어 문제)
2. `build_runtime_system_prompt()` — **"You are OpenHarness..."** 프롬프트로 리셋 (프롬프트 문제)

따라서 레지스트리를 아무리 수정해도, 시스템 프롬프트는 매번 덮어씌워졌고, 에이전트는 계속 "저는 OpenHarness입니다"라고 답변했습니다.

### 해결: Python MRO를 활용한 메서드 오버라이드
```python
async def _process_line(self, line: str) -> None:
    # 1단계: Theseus 슬래시 명령어 → 레지스트리 없이 직접 디스패치
    if line.startswith("/"):
        cmd_name = line.split()[0][1:].lower()
        if cmd_name in {"plan", "agent", "ask", "session", "clear"}:
            await theseus_cmd_handlers[cmd_name](args, None)
            return
        # OpenHarness 명령어는 handle_line에 위임 (프롬프트 영향 없음)
        await handle_line(bundle, line, ...)
        return

    # 2단계: 일반 메시지 → Theseus 프롬프트 적용 후 engine 직접 호출
    bundle.engine.set_system_prompt(theseus_sm.get_system_prompt())
    async for event in bundle.engine.submit_message(line):
        await self._render_event(event)
```

### 💡 이 해결책이 완벽한 이유
- **모듈 파편화 무관**: 레지스트리를 전혀 건드리지 않습니다.
- **프롬프트 보호**: `handle_line`을 우회하므로 Theseus 프롬프트가 절대 덮어씌워지지 않습니다.
- **OpenHarness 호환**: `/help`, `/exit` 등 기본 명령어는 여전히 정상 작동합니다.
- **Python 기본 기능**: `types.MethodType`이나 `importlib.reload` 같은 해킹 없이, 순수한 메서드 오버라이드(MRO)만 사용합니다.

## 5. 향후 과제 및 교훈
*   **패키지 경로 정리**: 근본적인 원인인 `sys.path` 오염과 모듈 중복 로드 문제를 해결하기 위해, 로컬 OpenHarness 코드를 패키징하거나 가상 환경(Virtualenv)을 더 엄격하게 관리할 필요가 있습니다.
*   **아키텍처 개선**: TUI 인스턴스가 런타임을 구성한 뒤 사후에 수정(Post-customization)하는 방식은 이처럼 알 수 없는 참조 문제를 일으킬 수 있으므로, 향후에는 `build_runtime`에 주입할 플러그인(Plugin) 형태로 명령어들을 완전히 캡슐화하여 전달하는 것이 더 안전합니다.
*   **핵심 교훈**: 프레임워크 내부와 싸우지 말고, 프레임워크가 제공하는 확장 포인트(메서드 오버라이드, 이벤트 체인)를 활용하라.
