# Theseus Usage Guide

이 문서는 Theseus를 처음 사용하는 팀원을 위한 간단한 소개와 실행 방법을
정리합니다. 자세한 내부 구조는 `README.md`와 `docs/history/CHANGELOG.md`를
기준으로 확인합니다.

## 1. Theseus란?

Theseus는 프로젝트 코드와 서버 환경을 이해하고, 질문 답변, 코드 조사,
계획 수립, 커스텀 툴 생성, 승인 기반 실행을 돕는 AI agent runtime입니다.

현재 저장소에서는 같은 `theseus_engine` 런타임을 여러 방식으로 실행합니다.

| 실행 방식 | 주 사용처 |
|---|---|
| CLI | 가장 단순한 터미널 대화와 smoke test |
| TUI | 터미널 안에서 세션, 모드, 승인 UI를 함께 쓰는 로컬 실행 |
| VSCode Extension | IDE 사이드바에서 코드 맥락과 함께 쓰는 로컬 daemon 실행 |
| Core Server | API Server, Kafka, Docker sandbox, Remote Workspace와 연결되는 서버 실행 |

공통 원칙은 다음입니다.

- 기본 모델 설정은 `.env`의 `THESEUS_MODEL`을 사용합니다.
- ASK, PLAN, AGENT는 같은 runtime mode입니다.
- API/Kafka에서 쓰는 `ToolPlan`은 툴 생성 서버 계약명이고, 일반 채팅에서는
  PLAN draft 또는 approved plan으로 이해하면 됩니다.
- 도구 노출은 프롬프트 문구만이 아니라 engine의 visibility policy에서
  mode, permission, phase, remote context 기준으로 강제됩니다.
- 위험한 도구 실행은 Human-in-the-Loop 승인 흐름을 거칩니다.

## 2. 공통 준비

Core 서버 폴더로 이동한 뒤 Python 3.11 가상환경을 준비합니다.

```powershell
cd backend\theseus-core-server
uv venv --python 3.11
.\.venv\Scripts\activate
uv pip install -r requirements.txt
```

`.env.example`을 복사해 필요한 값을 채웁니다.

```powershell
Copy-Item .env.example .env
```

최소 확인 항목은 다음입니다.

| 설정 | 설명 |
|---|---|
| `THESEUS_MODEL` | 사용할 기본 LLM 모델 |
| `OPENAI_API_KEY`, `ANTHROPIC_API_KEY`, `GEMINI_API_KEY`, `DEEPSEEK_API_KEY` | 사용할 provider의 API key |
| `AUTH_MODE` | 서버 실행 시 `spring` 또는 로컬 개발용 `mock` |
| `CORE_KAFKA_CONSUMER_ENABLED` | Kafka consumer 사용 여부 |
| `THESEUS_DEBUG_DUMP` | LLM 요청/응답 debug dump 저장 여부 |

선택 기능 의존성은 기본 설치에서 분리되어 있습니다.

```powershell
# 저장소에 포함된 예시 custom tool 실행용
uv pip install -r requirements-custom-tools.txt

# Playwright 기반 브라우저 자동화 도구용
uv pip install -r requirements-browser.txt
python -m playwright install chromium

# PDF, Word, Excel 분석 도구용
uv pip install -r requirements-doc-tools.txt
```

## 3. CLI 사용법

CLI는 가장 단순한 텍스트 기반 실행 경로입니다. 빠른 smoke test나 로컬
대화 확인에 적합합니다.

```powershell
python theseus_cli.py
```

특징은 다음입니다.

- 기본 세션 이름은 `default`입니다.
- 세션 기록은 `.theseus_sessions/*.json`에 저장됩니다.
- `/ask`, `/agent`, `/plan` 같은 slash command로 모드를 바꿉니다.
- local-first 실행이지만, 설정이 켜져 있으면 `ProjectClient`를 통해 서버와
  세션 동기화를 시도할 수 있습니다.

CLI는 화면 구성이 단순하므로 승인 요청, PLAN 단계, tool activity를 사람이
읽는 텍스트로 확인하는 용도에 가깝습니다. IDE 연동이나 실시간 UI가 필요하면
Extension을 사용합니다.

## 4. TUI 사용법

TUI는 Textual 기반 터미널 UI입니다. CLI보다 세션과 승인 흐름을 보기 쉽습니다.

```powershell
python -m theseus_engine.tui.tui_main
```

또는 파일 경로로 직접 실행할 수도 있습니다.

```powershell
python theseus_engine\tui\tui_main.py
```

주요 단축키와 명령은 다음입니다.

| 명령 | 단축키 | 설명 |
|---|---|---|
| `/ask` | `Ctrl+S` | 질문 답변 중심 모드 |
| `/agent` | `Ctrl+A` | 도구 사용과 작업 수행 중심 모드 |
| `/plan` | `Ctrl+P` | 계획 작성, 승인, 실행, 검증 흐름 |
| `/tools` | - | 현재 활성 도구 목록 확인 |
| `/session list` | - | 저장된 세션 목록 확인 |
| `/session new <name>` | - | 새 세션 생성 |
| `/session switch <name>` | - | 세션 전환 |
| `/cost` | - | 토큰/비용 요약 |
| `/quit` | `Ctrl+Q` | 저장 후 종료 |

위험한 도구를 실행하려 하면 승인 팝업이 표시됩니다.

| 응답 | 의미 |
|---|---|
| `y` | 이번 한 번 승인 |
| `a` | 현재 세션 동안 항상 승인 |
| `n` 또는 `Esc` | 거부 |

## 5. VSCode Extension 사용법

Extension은 Theseus를 IDE 사이드바에서 사용하는 경로입니다. 현재 기본 경로는
local daemon이며, 실패하면 stdio JSON Lines runner로 fallback합니다.

### 5.1 Extension 설치: 먼저 여기부터 실행

> **가장 쉬운 방법은 저장소 루트의 `Install-Theseus-Extension.cmd`를
> 더블클릭하는 것입니다.**

이 설치기는 다음 작업을 한 번에 처리합니다.

| 처리 항목 | 설명 |
|---|---|
| Python 실행 환경 | `backend\theseus-core-server\.venv` 생성 또는 재사용 |
| 의존성 설치 | `requirements.txt` 설치 |
| VSIX 설치 | `vscode-extension\theseus-vscode-*.vsix` 최신 파일 설치 |
| IDE 설정 | `theseus.corePath`, `theseus.pythonPath`, `theseus.workspacePath`를 IDE User 설정에 기록 |
| 실행 방식 | 기본은 source Python local daemon, `-RunnerPath`를 주면 packaged runner |

설치 위치는 IDE별로 다릅니다.

| IDE | Extension 저장소 | 설정 파일 |
|---|---|---|
| VS Code | `%USERPROFILE%\.vscode\extensions` | `%APPDATA%\Code\User\settings.json` |
| Antigravity | `%USERPROFILE%\.antigravity\extensions` | `%APPDATA%\Antigravity\User\settings.json` |

설치기가 기록하는 경로는 기본적으로 현재 PC에서 해석된 절대경로입니다.
예를 들어 repo 루트에서 실행하면 `theseus.corePath`는
`C:\...\backend\theseus-core-server`처럼 저장됩니다. `${workspaceFolder}`를
User settings에 그대로 저장하면 IDE가 워크스페이스를 열기 전이나 다른
IDE 호환 환경에서 치환하지 못할 수 있어 기본 설치에서는 사용하지 않습니다.
workspace별로 따로 저장해야 하면 설치 시 `-SettingsDir .vscode` 또는
`--settings-dir .vscode`를 명시하면 됩니다.
기본 User 설정 설치에서는 기존 `<workspace>\.vscode\settings.json`에 남아 있던
`theseus.*` 키도 정리해 workspace 설정이 User 설정을 덮어쓰지 않게 합니다.

#### 5.1.1 Windows에서 바로 설치

저장소 루트에서 더블클릭합니다.

```text
Install-Theseus-Extension.cmd
```

명령 프롬프트에서 실행할 수도 있습니다.

```cmd
Install-Theseus-Extension.cmd
```

자동 IDE 감지가 맞지 않으면 설치 대상을 명시합니다.

```cmd
Install-Theseus-Extension.cmd -Ide vscode
Install-Theseus-Extension.cmd -Ide antigravity
```

작업할 프로젝트가 저장소 루트와 다르면 workspace를 지정합니다.

```cmd
Install-Theseus-Extension.cmd -WorkspacePath C:\path\to\your\project
```

core 폴더를 직접 지정해야 하면 `-CorePath`를 사용합니다.

```cmd
Install-Theseus-Extension.cmd -CorePath C:\path\to\theseus-core-server
```

IDE CLI를 자동으로 찾지 못하면 `-Code`를 직접 지정합니다.

```cmd
Install-Theseus-Extension.cmd -Ide antigravity -Code "C:\path\to\antigravity.cmd"
```

사용 가능한 옵션은 다음 명령으로 확인합니다.

```cmd
Install-Theseus-Extension.cmd -Help
```

#### 5.1.2 PowerShell에서 설치

PowerShell에서 직접 설치 스크립트를 실행하려면 core 서버 폴더에서 시작합니다.

```powershell
cd backend\theseus-core-server
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\install-vscode-extension.ps1
```

IDE를 명시합니다.

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\install-vscode-extension.ps1 -Ide vscode
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\install-vscode-extension.ps1 -Ide antigravity
```

workspace를 명시합니다.

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\install-vscode-extension.ps1 -WorkspacePath C:\path\to\your\project
```

#### 5.1.3 Git Bash, Linux, macOS에서 설치

Git Bash에서는 core 서버 폴더에서 실행합니다.

```bash
cd backend/theseus-core-server
bash scripts/install-vscode-extension.sh
```

IDE를 명시합니다.

```bash
bash scripts/install-vscode-extension.sh --ide vscode
bash scripts/install-vscode-extension.sh --ide antigravity
```

workspace를 명시합니다.

```bash
bash scripts/install-vscode-extension.sh --workspace-path /path/to/your/project
```

Windows Git Bash에서는 두 경로 형식을 모두 사용할 수 있습니다.

```bash
bash scripts/install-vscode-extension.sh --workspace-path /c/Users/SSAFY/project
bash scripts/install-vscode-extension.sh --workspace-path 'C:\Users\SSAFY\project'
```

스크립트는 IDE 설정에 기록할 경로를 Windows IDE가 읽을 수 있는 형태로
변환합니다.

#### 5.1.4 설치 후 실행 확인

설치가 끝나면 IDE에서 다음 순서로 확인합니다.

1. 작업할 workspace를 엽니다.
2. Activity Bar에서 Theseus 사이드바를 엽니다.
3. Command Palette에서 `Theseus: Start Agent`를 실행합니다.
4. 문제가 있으면 `Theseus: Show Logs` 또는 Output Channel의 `Theseus` 로그를 확인합니다.

로그에서 정상 시작 흐름은 대략 다음과 같습니다.

```text
[Theseus] === Starting local daemon ===
[Theseus] core   : ...
[Theseus] cwd    : ...
[Theseus] python : ...
[Theseus] lifecycle state: {"state":"starting"}
```

#### 5.1.5 자주 쓰는 설치 옵션

| 옵션 | 사용 시점 |
|---|---|
| `-Ide vscode` / `--ide vscode` | VS Code에 설치 |
| `-Ide antigravity` / `--ide antigravity` | Antigravity에 설치 |
| `-WorkspacePath PATH` / `--workspace-path PATH` | agent가 작업할 프로젝트 경로 지정 |
| `-CorePath PATH` / `--core-path PATH` | `theseus_engine/`이 있는 core 서버 경로 지정 |
| `-Code PATH` / `--code PATH` | IDE CLI를 자동으로 찾지 못할 때 직접 지정 |
| `-VsixPath PATH` / `--vsix PATH` | 설치할 VSIX 파일 직접 지정 |
| `-RunnerPath PATH` / `--runner-path PATH` | Python source tree 대신 packaged runner 사용 |
| `-SkipRequirements` / `--skip-requirements` | 이미 requirements가 설치된 경우 생략 |
| `-SkipExtension` / `--skip-extension` | VSIX 설치 없이 설정만 기록 |
| `-SkipSettings` / `--skip-settings` | IDE 설정 기록 없이 VSIX만 설치 |

#### 5.1.6 packaged runner로 설치

테스트 배포에서 핵심 Python 소스 폴더를 직접 전달하지 않으려면 runner binary를
빌드한 뒤 `-RunnerPath`로 설치합니다.

```powershell
cd backend\theseus-core-server
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\build-runner-binary.ps1 -InstallPyInstaller
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\install-vscode-extension.ps1 -RunnerPath .\dist\theseus-runner\theseus-runner\theseus-runner.exe
```

이 경로는 `theseus.runnerPath`와 `theseus.runtimeMode=bundled-runner`를
설정하므로 Extension이 `python -m theseus_engine.daemon` 대신
`theseus-runner.exe`를 실행합니다.

#### 5.1.7 back/infra 제외 로컬 소스 패키지 만들기

서버 orchestration/API 코드, 프론트엔드, 인프라를 제외하고 로컬 extension
설치와 실행에 필요한 파일만 묶으려면 source package를 생성합니다.

저장소 루트에서 더블클릭합니다.

```text
Package-Theseus-LocalExtension.cmd
```

명령으로 실행하려면 다음을 사용합니다.

```powershell
Package-Theseus-LocalExtension.cmd
```

extension 폴더에서 VSIX 재빌드와 압축을 한 번에 실행할 수도 있습니다.

```powershell
cd backend\theseus-core-server\vscode-extension
npm.cmd run package:local-source
```

Git Bash에서는 다음 wrapper를 사용합니다.

```bash
bash Package-Theseus-LocalExtension.sh
```

생성 결과는 기본적으로 다음 위치에 생깁니다.

```text
backend\theseus-core-server\dist\local-extension-package\Theseus-LocalExtensionSourcePackage.zip
```

포함되는 파일은 다음입니다.

```text
Theseus-LocalExtensionSourcePackage/
  README.md
  Install-Theseus-Extension.cmd
  Uninstall-Theseus-VSCode.cmd
  backend/theseus-core-server/
    .env.example
    requirements*.txt
    usage.md
    theseus_cli.py
    theseus_cli/
    theseus_engine/
    scripts/install-vscode-extension.ps1
    scripts/install-vscode-extension.sh
    vscode-extension/theseus-vscode-*.vsix
```

제외되는 항목은 `src`, `frontend`, `infra`, `backend/theseus-api-server`,
`.venv`, `build`, `dist`, `tests`, 실제 `.env`, Python cache입니다.
배포 ZIP에 들어가는 `requirements*.txt`는 시스템 언어에 따른 Unicode decode
문제를 피하기 위해 ASCII-only로 정리되어 복사됩니다.

받은 사람은 압축을 풀고 `Install-Theseus-Extension.cmd`를 더블클릭하면 됩니다.
이 패키지는 소스 런타임 배포용이므로 핵심 Python 코드를 숨기는 목적에는
맞지 않습니다. source-free 테스트 배포가 필요하면 아래 runner binary 패키지를
사용합니다.

#### 5.1.8 테스터에게 source-free zip으로 보내기

테스터에게 source-free 테스트 패키지를 보내려면 다음 구성을 사용합니다.

```text
Theseus-TestPackage/
  README.md
  Install-Theseus-TestPackage.cmd
  scripts/install-test-package.ps1
  theseus-vscode-0.0.1.vsix
  theseus-runner/
    theseus-runner.exe
    _internal/
```

테스터는 `Install-Theseus-TestPackage.cmd`를 더블클릭하고 workspace 경로를
입력하면 됩니다. 설치 후 IDE가 열리면 Theseus 사이드바에서
`Theseus: Start Agent`를 실행합니다.

VSIX 재빌드와 테스트 zip 생성을 함께 실행하려면 extension 폴더에서 다음을
사용합니다. runner binary가 이미 빌드되어 있어야 합니다.

```powershell
cd backend\theseus-core-server\vscode-extension
npm.cmd run package:test
```

runner binary도 다시 빌드해야 하면 npm 인자를 PowerShell packager에
전달합니다.

```powershell
npm.cmd run package:test -- -BuildRunner
npm.cmd run package:test -- -BuildRunner -InstallPyInstaller
```

Git Bash에서는 저장소 루트에서 Bash wrapper를 사용할 수 있습니다.

```bash
bash Package-Theseus-TestPackage.sh
bash Package-Theseus-TestPackage.sh --build-runner --install-pyinstaller
```

생성 결과는 기본적으로 다음 위치에 생깁니다.

```text
backend\theseus-core-server\dist\test-package\Theseus-TestPackage.zip
```

#### 5.1.9 설치 문제 빠른 진단

| 증상 | 확인할 것 |
|---|---|
| IDE CLI를 찾지 못함 | `-Ide vscode`, `-Ide antigravity`, `-Code PATH`로 명시 |
| Theseus sidebar가 안 보임 | VSIX가 설치된 IDE가 맞는지 확인하고 IDE 재시작 |
| `theseus_engine`을 찾지 못함 | `theseus.corePath`가 `backend\theseus-core-server`를 가리키는지 확인 |
| Python import 오류 | 설치 스크립트를 requirements 설치 생략 없이 다시 실행 |
| `unrecognized arguments: --session default` | 오래된 core 또는 오래된 VSIX 조합입니다. 최신 VSIX 재설치와 `theseus.corePath` 확인 필요 |
| 다른 checkout이 실행됨 | Output의 `core`, `cwd`, `python` 경로가 기대한 경로인지 확인 |
| runner exe에서 import 오류 | 새 Python dependency를 빌드 환경에 설치하고 runner를 다시 빌드 |

### 5.2 개발 중 Extension 실행

Extension 코드를 직접 수정하는 중이면 먼저 컴파일합니다.

```powershell
cd backend\theseus-core-server\vscode-extension
npm.cmd run compile
```

그 다음 VSCode에서 `backend/theseus-core-server/vscode-extension` 폴더를 열고
`F5`로 Extension Development Host를 실행합니다.

패키징이 필요하면 다음을 실행합니다.

```powershell
npm.cmd run package:vsix
```

`package:vsix`는 `out/`, `media/`, `package.json` 등 VSIX에 들어가야 하는 핵심 입력 파일이 있는지 먼저 확인합니다.
설치 후 Health 패널의 `sourceMarker`, `builtAt`, `mediaBuiltAt` 값을 보면 현재 설치된 번들이 최신 빌드인지 확인할 수 있습니다.

### 5.3 Extension에서 가능한 일

- ASK/PLAN/AGENT 모드 선택
- 현재 IDE workspace, 활성 파일, diagnostics 맥락 활용
- local daemon 상태 확인과 재시작
- PLAN 승인/거부
- tool activity, tool result, file diff 확인
- custom tool 목록 확인
- 생성된 파일 열기 또는 diff 확인

Extension은 사용성 측면에서 가장 권장되는 로컬 실행 방식입니다. CLI/TUI는
디버깅과 단순 실행에 더 적합합니다.

## 6. Core Server 사용법

Core Server는 API Server와 연결되는 서버 실행 경로입니다. FE/API/Kafka,
Docker sandbox, Remote Workspace를 포함한 통합 흐름은 이 경로를 사용합니다.

```powershell
uvicorn src.main:app --reload --host 0.0.0.0 --port 8000
```

확인 endpoint:

| 경로 | 설명 |
|---|---|
| `GET /health` | 기본 health check |
| `GET /health/details` | sandbox, Kafka, DB, Remote Workspace 설정 진단 |
| `GET /docs` | FastAPI 문서 UI |

주요 실행 endpoint:

| 경로 | 설명 |
|---|---|
| `GET /api/v1/stream` | 직접 SSE stream |
| `POST /api/v1/stream` | API Server proxy용 JSON body stream |
| `POST /api/v1/plans` | plan 생성 |
| `POST /api/v1/sandbox/execute` | sandbox code 실행 |
| `POST /api/v1/remote-workspaces/test-connection` | Remote Workspace SSH 연결 테스트 |

서버 실행에서는 Spring Boot가 사용자, 프로젝트, 권한, 세션, Remote Workspace
등록 정보의 source of truth입니다. Core는 요청별 context를 받아
`theseus_engine`을 실행하고, 결과를 SSE/Kafka/API 응답으로 되돌립니다.

## 7. 실행 방식별 차이

| 항목 | CLI | TUI | Extension | Core Server |
|---|---|---|---|---|
| 주 목적 | 빠른 로컬 대화 | 터미널 UI | IDE 통합 | FE/API/Kafka 통합 |
| 실행 방식 | 직접 Python | Textual 앱 | local daemon 또는 stdio | FastAPI |
| 세션 저장 | `.theseus_sessions` | `.theseus_sessions` | `.theseus_sessions` + WebView 상태 | API Server history |
| 권한/승인 | 텍스트 prompt | 팝업 modal | WebView 승인 UI | API/FE 승인 흐름 |
| 파일 맥락 | 현재 cwd | 현재 cwd | IDE workspace/active file | API payload/history |
| ToolBuild | local create_tool | local create_tool | local/server-assisted 가능 | Kafka/Sandbox worker |
| Remote Workspace | 기본 대상 아님 | 기본 대상 아님 | 서버 연결 시 확장 대상 | `remoteWorkspaceId` resolver |
| 적합한 상황 | smoke test | 터미널 작업 | 실제 개발 UX | B2B 서버 통합 |

## 8. 모드 차이

| 모드 | 목적 | 도구 사용 |
|---|---|---|
| ASK | 질문 답변, 설명, 읽기 중심 분석 | 기본적으로 안전한 읽기/검색 중심 |
| PLAN | 작업 계획 작성, 승인 대기, 실행 계획 정리 | DRAFTING/REVIEW 단계에 맞게 제한 |
| AGENT | 승인된 목표를 실제로 수행 | 권한과 승인에 따라 파일/명령/툴 사용 |
| COORDINATOR | 여러 작업 조율 | 상황에 따라 제한적으로 사용 |

PLAN은 일반적으로 다음 흐름을 따릅니다.

```text
DRAFTING -> WAIT_FOR_REVIEW -> EXECUTING -> VERIFYING
```

서버의 ToolPlan Kafka workflow는 이름이 비슷하지만, “툴 생성 전용 worker
계약”입니다. 일반 `/stream`의 PLAN 모드와 같은 철학을 공유하되 실행 경로는
다릅니다.

## 9. Custom Tool과 ToolBuild

Theseus는 custom tool을 생성하고 실행할 수 있습니다.

- local runtime에서는 `create_tool`을 통해 custom tool 파일과 `.meta.json`을
  생성합니다.
- server runtime에서는 ToolPlan/ToolBuild worker가 Kafka 이벤트를 처리하고,
  Docker sandbox로 생성 코드를 검증합니다.
- tool 호출 이름과 저장 파일명은 분리될 수 있습니다.
  - 예: 호출 이름 `system_monitor`
  - 파일명 `system_monitor_tool.py`
- 생성된 tool metadata에는 `toolName`, `moduleName`, `fileName`,
  `permissionLevel`, 입력/출력 schema가 저장됩니다.

ToolBuild 실패 시 Core는 공통 repair loop를 통해 안전한 대체 구현을
시도합니다. `subprocess`, `os.system`, `socket`, `ctypes`처럼 금지된 기능은
기본적으로 허용하지 않습니다. 안전한 대체가 없으면 실패 이유와 가능한 대안을
사용자에게 전달합니다.

## 10. Remote Workspace

Remote Workspace는 Core가 외부 서버에 SSH로 접속해 파일, 로그, 리소스,
제한된 명령을 다루는 실행 대상 환경입니다.

중요한 보안 원칙:

- FE/API/Kafka/stream payload에는 `remoteWorkspaceId`만 전달합니다.
- password나 private key path는 payload, history, debug dump에 직접 남기지
  않습니다.
- Core는 API Server internal resolver로 SSH config를 조회하고, metadata에는
  redacted 정보만 남깁니다.
- ASK/PLAN에서는 remote read-only 도구만 노출합니다.
- AGENT에서도 `allowWriteExecution=true`일 때만 write/command remote tool을
  노출합니다.

대표 remote tool:

| 도구 | 설명 |
|---|---|
| `remote_read_file` | basePath 안의 파일 읽기 |
| `remote_grep` | 원격 파일 텍스트 검색 |
| `remote_tail_log` | 로그 tail |
| `remote_check_cpu` | CPU 상태 확인 |
| `remote_check_memory` | 메모리 상태 확인 |
| `remote_check_disk` | 디스크 상태 확인 |
| `remote_write_file` | 허용된 AGENT 실행에서 원격 파일 쓰기 |
| `remote_edit_file` | 허용된 AGENT 실행에서 원격 파일 수정 |
| `remote_run_command` | 제한 정책 안에서 원격 명령 실행 |

## 11. Debug Dump와 문제 확인

LLM 요청/응답을 확인해야 할 때는 `.env`에서 debug dump를 켭니다.

```env
THESEUS_DEBUG_DUMP=true
THESEUS_DEBUG_DUMP_DIR=.theseus/debug
```

debug dump는 다음을 구분해 남깁니다.

- 모델에 전달된 messages
- 사용 가능한 tool schema 목록
- 실제 history에 포함된 tool_use/tool_result 개수
- provider 변환 이후 OpenAI-compatible payload 요약

서버에서 sandbox, Kafka, DB, Remote Workspace 설정을 확인하려면 다음을 봅니다.

```text
GET /health/details
```

## 12. 어떤 실행 방식을 선택해야 하나?

| 상황 | 추천 |
|---|---|
| 단순히 대화 흐름만 빠르게 확인 | CLI |
| 터미널에서 승인 UI와 세션을 함께 확인 | TUI |
| 실제 개발 중 코드 파일과 함께 사용 | VSCode Extension |
| FE/API/Kafka/Spring 연동을 검증 | Core Server |
| Remote Workspace, ToolBuild sandbox 검증 | Core Server |
| Extension runner 문제 디버깅 | local daemon + `cli_runner --json-mode` fallback |

일반 개발자는 Extension을 사용하고, Core/AI 서버 담당자는 CLI/TUI로 빠르게
재현한 뒤 Core Server로 통합 검증하는 흐름이 가장 실용적입니다.
