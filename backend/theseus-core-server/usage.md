# Theseus Agent Execution Guide

## 실행 방법

터미널에서 아래 명령어로 TUI를 실행합니다.

```bash
python theseus_engine/tui/tui_main.py
```

또는 CLI(텍스트 전용) 모드로 실행할 수도 있습니다.

```bash
python theseus_cli.py
```

> **환경 변수**: 사용할 LLM 모델은 `.env` 파일의 `OPENHARNESS_MODEL` 값으로 지정합니다. (기본값: `gpt-4o`)

---

## VS Code Extension 설치 방법

Theseus는 VS Code 사이드바 확장으로도 실행할 수 있습니다.

### VSIX 파일로 설치

프로젝트 루트(`S14P31A308`)에서 아래 명령어를 실행합니다.

```bash
code --install-extension backend/theseus-core-server/vscode-extension/theseus-vscode-0.0.1.vsix
```

Antigravity에 설치할 때도 같은 방식으로 실행합니다.

```bash
antigravity --install-extension backend/theseus-core-server/vscode-extension/theseus-vscode-0.0.1.vsix
```

이미 `backend/theseus-core-server/vscode-extension` 폴더 안에 있다면 VSIX 파일만 지정합니다.

```bash
code --install-extension ./theseus-vscode-0.0.2.vsix
antigravity --install-extension ./theseus-vscode-0.0.2.vsix
```

설치 후 VS Code를 다시 로드하면 Activity Bar에 **Theseus** 아이콘이 표시됩니다.
아이콘을 클릭한 뒤 Chat 뷰에서 **Start** 버튼을 누르거나 Command Palette에서 `Theseus: Start Agent`를 실행합니다.

### 개발 중 직접 실행

확장 코드를 수정한 뒤에는 먼저 컴파일합니다.

```bash
cd backend/theseus-core-server/vscode-extension
npm run compile
```

그 다음 VS Code에서 `backend/theseus-core-server/vscode-extension` 폴더를 열고 `F5`를 눌러 Extension Development Host를 실행합니다.

> Windows PowerShell에서 `npm.ps1` 실행 정책 오류가 나면 `npm.cmd run compile`을 사용합니다.

### 확장 코드 수정 후 VSIX 다시 만들기

확장 코드를 수정한 뒤 설치용 VSIX 파일을 다시 만들려면 확장 폴더에서 컴파일 후 패키징합니다.

```bash
cd backend/theseus-core-server/vscode-extension
npm run compile
npx @vscode/vsce package
```

PowerShell에서 `npm.ps1` 실행 정책 오류가 나면 아래처럼 실행합니다.

```powershell
npm.cmd run compile
npx.cmd @vscode/vsce package
```

생성되는 파일명은 `package.json`의 `name`과 `version`을 따릅니다. 예를 들어 `version`이 `0.0.2`이면 `theseus-vscode-0.0.2.vsix`가 생성됩니다.
기존 설치본 위에 다시 설치할 때는 `package.json`의 `version`을 올린 뒤 패키징하고, 생성된 VSIX를 다시 설치합니다.

```bash
code --install-extension ./theseus-vscode-0.0.1.vsix --force
antigravity --install-extension ./theseus-vscode-0.0.1.vsix --force
```

---

## 주요 명령어

### 모드 전환

| 커맨드 | 단축키 (TUI) | 설명 |
|--------|-------------|------|
| `/agent` | `Ctrl+A` | 자율 에이전트 모드 (기본값). 도구를 자유롭게 사용하여 문제를 해결합니다. |
| `/plan`  | `Ctrl+P` | 복잡한 작업을 단계별로 분해하고 실행하는 Planning 모드입니다. |
| `/ask`   | `Ctrl+S` | 도구 사용 없이 질문에만 답하는 지식 검색 전용 모드입니다. |
| `/coordinator` | — | 다중 작업 조율 모드입니다. |

### 세션 관리

| 커맨드 | 설명 |
|--------|------|
| `/session list` | 저장된 세션 목록을 표시합니다. |
| `/session new <이름>` | 새 세션을 생성하고 전환합니다. |
| `/session switch <이름>` | 기존 세션으로 전환합니다. |
| `/clear` | 현재 세션의 대화 내용을 모두 삭제합니다. |

### 툴 관리

| 커맨드 | 설명 |
|--------|------|
| `/tools` 또는 `/tools all` | 현재 활성화된 전체 툴 목록을 표시합니다. 커스텀 툴은 `[custom]` 태그로 구분됩니다. |
| `/tools custom` | 커스텀 툴만 필터링하여 권한 레벨·상태·설명과 함께 표시합니다. |
| `/validate <툴이름>` | 지정한 커스텀 툴의 코드 유효성을 검사합니다. |

### 통계 및 비용

| 커맨드 | 설명 |
|--------|------|
| `/cost` | 현재 세션의 토큰 사용량 및 비용 리포트를 표시합니다. |
| `/stats` | 툴 실행 횟수 등 세션 통계를 표시합니다. |

### 종료

| 커맨드 | 단축키 (TUI) | 설명 |
|--------|-------------|------|
| `/quit` | `Ctrl+Q` | 세션 히스토리를 저장하고 안전하게 종료합니다. |
| `/exit` | — | `/quit`와 동일합니다. |
| `/bye`  | — | `/quit`와 동일합니다. |

---

## 세션 저장 및 복구 (Session Memory)

멀티턴(Multi-turn) 대화를 지원합니다.

- 에이전트 턴이 완료될 때마다 대화 내역이 자동으로 로컬 파일에 백업됩니다.
- 다음에 동일 세션 이름으로 실행하면 이전 컨텍스트를 자동으로 불러옵니다.
- 세션 파일 저장 경로: `theseus_sessions/<세션이름>.json`

---

## 안전 장치 (Human-in-the-Loop)

에이전트가 파괴적 툴(`bash`, `write_file`, `edit_file`, `create_tool`, `system_reboot` 등)을 실행하려 할 때,
TUI 화면 중앙에 **보안 승인 팝업(SecurityApprovalModal)**이 나타납니다.

| 응답 | 키 | 동작 |
|------|----|------|
| 승인 | `y` | 이번 한 번만 실행을 허가합니다. |
| 항상 승인 | `a` | 세션 동안 해당 툴의 실행을 항상 자동 허가합니다. |
| 거부 | `n` 또는 `Esc` | 실행을 취소합니다. |

---

## 자동완성

Input 창에서 아래 트리거로 자동완성 드롭다운이 활성화됩니다.

| 트리거 | 동작 |
|--------|------|
| `/` | 등록된 슬래시 커맨드 목록 표시 |
| `@` | 현재 디렉터리 기준 파일/폴더 경로 제안 |
| `Tab` | 하이라이트된 항목 선택 적용 |
| `↑` / `↓` | 드롭다운 항목 이동 |

---

## Plan 모드 단계 흐름

```
DRAFTING  →  EXECUTING  →  VERIFYING  →  (완료)
                ↓
         에러 발생 시 Auto-Resume (최대 5회 자동 재시도)
                ↓
         MaxTurnsExceeded → WAIT_FOR_REVIEW (상태 보존)
```

- **DRAFTING**: LLM이 작업 계획(JSON)을 작성합니다. 사이드바에 태스크 체크리스트가 표시됩니다.
- **EXECUTING**: 계획의 각 단계를 순서대로 실행합니다. 툴 에러 발생 시 자동으로 재시도합니다.
- **VERIFYING**: 실행 결과를 검증합니다.
- **WAIT_FOR_REVIEW**: 최대 턴 초과 시 현재 상태를 저장하고 사용자 검토를 기다립니다.
