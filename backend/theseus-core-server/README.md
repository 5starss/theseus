# 테세우스 (Theseus) Core Server

> 기준 문서: `docs/history/CHANGELOG.md`, `docs/task/remaining_tasks.md`,
> `docs/roadmap/vscode-extension-plan.md`,
> `docs/analysis/src-theseus-engine-alignment-review.md`,
> `docs/analysis/theseus-engine-extension-refactor-gap.md`,
> `docs/prompt/prompt_architecture_map.md`
>
> 최종 반영 기준: 2026-05-14, Session 114

## 1. 개요

Theseus Core Server는 B2B 환경에서 프로젝트 권한, 대화 이력, 과금, 지식
검색, 커스텀 툴 생성 흐름을 제어하면서 `theseus_engine` 에이전트 런타임을
실행하는 Python 기반 코어입니다.

현재 코드는 크게 두 영역으로 나뉩니다.

| 영역 | 책임 |
|---|---|
| `src/` | FastAPI 서버 오케스트레이션, 인증, Spring Boot 연동, SSE 스트리밍, plan 영속화, billing outbox, Kafka tool plan/build workflow, Remote Workspace resolver/route, Docker sandbox |
| `theseus_engine/` | QueryEngine, StreamEvent, RBAC/permission, tool runtime, canonical prompt builder, tool visibility policy, repair loop, memory/skill injection, local runner/runtime |

Spring Boot 서버는 사용자, 프로젝트, 인증, 조직 정책의 source of truth를
담당하고, Core Server는 에이전트 실행과 스트리밍, 서버 내부 비동기 작업을
담당합니다. VSCode Extension은 같은 `theseus_engine`을 로컬 daemon 또는
stdio fallback으로 실행할 수 있습니다.

핵심 설계 원칙은 다음입니다.

- API/Kafka/SSE/FE 계약은 가능한 한 안정적으로 유지하고, 모드/프롬프트/도구
  정책은 Core 내부에서 정리합니다.
- `/stream`의 `ASK`, `AGENT`, `PLAN`은 일반 runtime mode입니다. API/Kafka의
  `ToolPlan`은 툴 생성 전용 서버 계약명이며, LLM-facing prompt에서는
  `PLAN draft`, `plan JSON`, `approved plan` 용어를 우선 사용합니다.
- system prompt의 source of truth는 `theseus_engine/prompts` 패키지입니다.
  `state.py`는 상태 머신 façade와 기존 import 호환만 담당합니다.
- tool visibility는 prompt 문구만이 아니라 `theseus_engine.core.tool_visibility`
  정책에서 mode/phase/RBAC/remote context 기준으로 강제합니다.
- Remote Workspace secret은 stream/Kafka payload에 싣지 않고, Core가
  `remoteWorkspaceId`로 API Server internal resolver를 호출해 필요한 순간에만
  원본 SSH config를 얻습니다.
- 기본 의존성은 Core가 직접 import하는 패키지로 제한하고, 브라우저/문서/예시
  custom tool 의존성은 optional requirements로 분리합니다.

## 2. 현재 핵심 기능

### 2.1 FastAPI SSE 서버

- `GET /api/v1/stream`과 `POST /api/v1/stream`으로 인증된 사용자 요청을
  SSE로 스트리밍합니다.
- Spring Boot 세션 검증 후 `user_id`, `project_id`, `permission_level`을
  받아 요청별 `EngineBuildContext`를 구성합니다.
- `chat_session_id` 기준으로 Spring history를 로드하고, 사용자/assistant
  메시지를 저장합니다.
- 스트림 종료 후 `UsageSnapshot`을 billing outbox에 적재해 백그라운드
  scheduler가 내부망 과금 API로 전송할 수 있게 합니다.
- `plan_id`가 있으면 실행 가능한 plan binding을 검증하고, stream 종료 후
  plan 상태를 복구합니다.
- `remoteWorkspaceId`가 있으면 API Server internal resolver로 SSH 접속 정보를
  조회하고, mode별 remote tool registry를 구성합니다.
- `/health/details`는 기존 `/health`를 변경하지 않고 sandbox, Kafka consumer,
  DB target, Remote Workspace resolver 설정을 진단하는 Core 전용 endpoint입니다.

### 2.2 Theseus Native Engine

- `QueryEngine`은 LLM streaming, tool call 실행, StreamEvent 발행,
  permission check, hook 실행, auto-compaction, usage 집계를 담당합니다.
- Session 65 기준으로 tool 실행 순서가 정리되어 RBAC/permission 검사가
  PRE hook, AuditLLM, HITL보다 먼저 수행됩니다.
- 단일 tool 실행 예외는 agent loop를 중단시키지 않고
  `ToolExecutionCompleted(is_error=True)`로 회복 가능한 이벤트로 전달합니다.
- POST hook이 tool output을 보정하거나 self-reflection 경고를 추가하면,
  해당 결과가 StreamEvent와 다음 LLM 입력에 반영됩니다.
- `AgentLoopStatus` 이벤트는 모델 턴, tool 실행, loop 완료/오류 상태를
  VSCode WebView 같은 클라이언트가 표시할 수 있게 합니다.
- `theseus_engine.core.tool_visibility`가 ASK/PLAN/AGENT/COORDINATOR mode별
  active tool registry를 공통 계산합니다.
- `theseus_engine.tools.tool_repair`는 CLI/TUI/Extension/Server ToolBuild가
  공유하는 custom tool repair 정책과 실패 분류를 제공합니다.
- LLM debug dump는 사용할 수 있는 tool schema와 실제 history의
  tool_use/tool_result 포함 여부를 분리해 남깁니다.

### 2.2.1 프롬프트와 mode/phase

- `theseus_engine/models/modes.py`가 `AgentMode`, `PlanPhase`,
  `CoordinatorPhase`를 정의합니다.
- `theseus_engine/prompts/`가 base, environment, capability, ASK/AGENT,
  PLAN, Coordinator prompt 본문과 `build_system_prompt()` 조립 함수를
  소유합니다.
- `theseus_engine/models/state.py`는 `TheseusStateMachine` 상태 전환과 기존
  import 호환 re-export를 유지하며, `get_system_prompt()`는 canonical prompt
  builder에 위임합니다.
- 서버 worker는 `src/builder/system_prompt.py` adapter를 통해 같은 prompt
  builder를 사용합니다. Extension/local runtime도 별도 system prompt를 갖지
  않습니다.

### 2.3 PLAN / HITL 흐름

PLAN 모드는 다음 4단계 상태를 사용합니다.

```text
DRAFTING -> WAIT_FOR_REVIEW -> EXECUTING -> VERIFYING
```

- DRAFTING은 읽기 도구 기반 코드 조사와 구조화된 계획 JSON 생성을 맡습니다.
- WAIT_FOR_REVIEW는 승인, 수정, 질문, 취소를 반복 처리합니다.
- EXECUTING은 승인된 계획을 실행하고 진행 상태를 보고합니다.
- VERIFYING은 테스트, 변경 파일 리뷰, 회귀 확인, 계획 완료율 검증을 수행합니다.

local runner/editor runtime은 기존 완료 문자열 감지를 유지하면서도
`PlanPhaseTransitionRequested` 구조화 이벤트를 함께 발행합니다. PLAN 실행
완료 신호를 감지하면 `VERIFYING`으로 전환한 뒤 자동 검증 턴을 이어서
실행하고, 검증 응답이 `Verification complete.` 또는 `검증 완료`를 포함하면
완료 이벤트와 함께 최종 응답으로 반환합니다.

### 2.4 메타 툴링과 서버 worker

- 서버의 tool 생성 워크플로는 `src/tool_plan`, `src/tool_build`,
  `src/tool_generation`에 있습니다.
- `src/tool_generation`은 legacy 이벤트를 신규 plan/build 흐름으로 넘기는
  호환 adapter 역할을 유지합니다.
- `src/builder/system_prompt.py`는 서버 worker가 별도 프롬프트를 복제하지
  않고 `theseus_engine.prompts`의 canonical prompt builder를 재사용하면서,
  현재 활성 tool schema에 맞는 capability 지침만 조건부로 주입하도록 합니다.
- tool plan/build worker는 PLAN DRAFTING, WAIT_FOR_REVIEW, EXECUTING
  프롬프트를 요청 목적에 맞게 주입합니다.
- PLAN 생성 전에는 프로젝트 active custom tool `.meta.json`만 읽어 기존 도구
  요약을 prompt context에 주입합니다. 같은 기능이 이미 있으면 새 도구 생성보다
  reuse/extend/rename 전략을 먼저 계획하도록 유도합니다.
- ToolBuild 실패는 기존 API/Kafka `code/message` 계약을 유지하되, Core 내부
  repair loop가 안전한 대체 구현을 시도하고 최종 실패 message에는 자동 repair
  횟수와 마지막 원인을 포함합니다.

### 2.5 VSCode / Editor Runtime

VSCode Extension은 서버와 독립적으로 standalone으로도 동작합니다.

- `theseus_engine/runner_runtime.py`
  - `EditorRuntime`으로 QueryEngine 초기화, session/slash 명령, mode 전환,
    PLAN 승인/거부 처리를 공용화합니다.
- `theseus_engine/daemon.py`
  - `127.0.0.1` 전용 bearer token 기반 local HTTP/SSE daemon입니다.
  - `GET /health`, `GET /status`, `POST /runs`,
    `GET /runs/{runId}/events`, `POST /runs/{runId}/interrupt`를 제공합니다.
  - `.theseus/runner.json`에 pid, host, port, token, runtime mode,
    workspace/coreRoot, schema version, sessionId, workspaceHash를 저장합니다.
  - `/status` heartbeat, stale 판정, SSE reconnect, `after=<eventCount>`
    기반 event replay를 지원합니다.
- `theseus_engine/cli_runner.py`
  - stdio JSON Lines runner입니다.
  - local daemon 실패 시 fallback/debug/CI smoke test 경로로 유지합니다.

Extension 쪽은 `local-daemon`을 기본 실행 경로로 사용하고, 실패하면 기존
stdio JSON Lines runner로 복구하는 방향입니다. 두 경로 모두 민감 도구 실행
시 `PermissionRequest`를 Extension에 전달하고 사용자 허용/거부 응답을
기다립니다.

### 2.6 지식 검색 / RAG

Theseus에는 서버용 `src/knowledge` 경로와 standalone engine용
`theseus_engine/rag` 경로가 함께 존재합니다.

현재 정합성 검토 문서 기준으로 두 경로는 같은 테이블명을 서로 다른 스키마로
해석할 수 있어 통합 전 주의가 필요합니다. 서버 모드에서는 프로젝트 스코프와
영속화 경계를 가진 `src/knowledge` 쪽을 기준으로 정리합니다. 서버 builder는
기본적으로 engine RAG tool을 비활성화하며, 필요 시
`THESEUS_ENABLE_ENGINE_RAG_TOOLS=true`로 복구할 수 있습니다.

### 2.7 Remote Workspace

Remote Workspace는 Core가 외부 서버에 SSH로 접근해 파일/로그/리소스/명령을
다루는 실행 대상 환경입니다.

- FE/API/Kafka/stream payload에는 `remoteWorkspaceId`만 전달합니다.
- Core는 `src/remote_workspace/resolver.py`를 통해 API Server internal
  endpoint에서 SSH 접속 정보를 resolve합니다.
- resolve된 원본 config는 process-local runtime key로 보관하고,
  `tool_metadata`, log, debug dump에는 redacted config만 남깁니다.
- ASK/PLAN은 `remote_read_file`, `remote_grep`, `remote_tail_log`,
  `remote_check_cpu`, `remote_check_memory`, `remote_check_disk` 같은 read-only
  remote tool만 노출합니다.
- AGENT도 기본은 read-only이며, resolver 결과의 `allowWriteExecution=true`일
  때만 `remote_write_file`, `remote_edit_file`, `remote_run_command`가 노출됩니다.
- `remote_run_command`는 shell chaining, command substitution, pipe-to-shell,
  basePath 밖 path argument를 Core에서 차단합니다.

## 3. 주요 API와 실행 경로

| 경로 | 설명 |
|---|---|
| `GET /health` | Core Server health check |
| `GET /health/details` | sandbox, Kafka consumer, DB, Remote Workspace resolver 상세 진단 |
| `GET /api/v1/stream` | 인증된 에이전트 SSE 스트림 |
| `POST /api/v1/stream` | API Server proxy용 JSON body 기반 에이전트 SSE 스트림 |
| `POST /api/v1/plans` | plan 생성 |
| `GET /api/v1/plans/{plan_id}` | plan 조회 |
| `GET /api/v1/sessions/{chat_session_id}/plans` | 세션별 plan 목록 |
| `PATCH /api/v1/plans/{plan_id}/submit` | plan review 제출 |
| `PATCH /api/v1/plans/{plan_id}/approve` | plan 승인 |
| `PATCH /api/v1/plans/{plan_id}/reject` | plan 거부 |
| `PATCH /api/v1/plans/{plan_id}/execute` | plan 실행 상태 전환 |
| `POST /api/v1/sandbox/execute` | sandbox 기반 tool code 실행 |
| `POST /api/v1/remote-workspaces/test-connection` | Remote Workspace SSH 연결 테스트 |

## 4. 개발 환경

- Python 3.11 권장
- FastAPI / Uvicorn
- `uv` 기반 가상환경과 의존성 설치
- PostgreSQL + pgvector
- Docker sandbox
- LangSmith tracing
- Spring Boot 내부 API 연동
- Kafka tool plan/build/generation consumer
- Remote Workspace SSH 연결은 `paramiko` 기반입니다.
- 브라우저/문서/샘플 custom tool 의존성은 optional requirements로 분리합니다.

## 5. Quick Start

### 5.1 의존성 설치

```powershell
cd backend\theseus-core-server
uv venv --python 3.11
.\.venv\Scripts\activate
uv pip install -r requirements.txt
```

기본 `requirements.txt`는 Core Server와 공통 runtime이 직접 import하는
의존성만 포함합니다. 선택 기능은 아래 파일로 분리합니다.

```powershell
# 저장소에 포함된 예시 custom tool 전체 실행용
uv pip install -r requirements-custom-tools.txt

# Playwright 기반 브라우저 자동화 도구만 활성화할 때
uv pip install -r requirements-browser.txt
python -m playwright install chromium

# PDF/Word/Excel 분석 도구를 활성화할 때
uv pip install -r requirements-doc-tools.txt
```

`playwright-stealth`처럼 bot-detection 우회 성격의 패키지는 기본/optional
의존성에 포함하지 않습니다. 필요하면 대상 서비스 약관과 배포 정책을 먼저
검토한 뒤 별도 프로젝트 의존성으로 관리합니다.

### 5.2 환경 변수

`.env.example`을 복사해 `.env`를 만들고 필요한 값만 채웁니다.

```powershell
Copy-Item .env.example .env
```

최소 확인 항목은 다음과 같습니다.

| 설정 | 설명 |
|---|---|
| `THESEUS_MODEL` | 기본 LLM 모델 |
| `OPENAI_API_KEY`, `ANTHROPIC_API_KEY`, `GEMINI_API_KEY`, `DEEPSEEK_API_KEY` | 사용하는 provider에 맞는 API key |
| `AUTH_MODE` | `spring` 또는 로컬 개발용 `mock` |
| `SPRING_BOOT_*` | Spring Boot 인증, 권한, history, billing 내부 API |
| `POSTGRES_*` | Core DB와 pgvector 설정 |
| `CORE_KAFKA_CONSUMER_ENABLED` | Kafka consumer 활성화 여부 |
| `CORE_LEGACY_TOOL_GENERATION_CONSUMER_ENABLED` | legacy tool generation adapter 활성화 여부. 기본 tool 생성 경로입니다. |
| `CORE_TOOL_PLAN_CONSUMER_ENABLED` | 신규 `tool-plan` topic consumer 활성화 여부. API Server가 `tool-plan` topic으로 전환된 뒤 opt-in으로 켭니다. |
| `SPRING_BOOT_REMOTE_WORKSPACE_CONFIG_URL` | Remote Workspace SSH config를 resolve할 API Server internal endpoint |
| `THESEUS_TOOL_REPAIR_MAX_ATTEMPTS` | CLI/TUI/Extension/Server가 공유하는 custom tool repair 최대 시도 횟수 |
| `SANDBOX_*` | Docker sandbox 이미지, 리소스 제한, startup check, shared workdir |
| `SANDBOX_HOST_TEMP_ROOT`, `SANDBOX_CONTAINER_TEMP_ROOT` | Docker socket/Core 컨테이너 경로 mismatch 방지를 위한 sandbox shared temp root |
| `LANGCHAIN_*` | LangSmith tracing |
| `THESEUS_DYNAMIC_TOOL_RETRIEVAL` | 질의별 top-k tool retrieval 활성화 |
| `THESEUS_ENABLE_ENGINE_RAG_TOOLS` | 서버 registry에서 standalone engine RAG tool을 명시적으로 활성화 |
| `THESEUS_ENABLE_AGENT_HOOK` | 파일 작업 AuditLLM/hook 활성화 |
| `THESEUS_DEBUG_DUMP`, `THESEUS_DEBUG_DUMP_DIR` | LLM request/response/debug payload dump 활성화 및 저장 경로 |

### 5.3 FastAPI 서버 실행

```powershell
uvicorn src.main:app --reload --host 0.0.0.0 --port 8000
```

문서 UI는 `/docs`, health check는 `/health`에서 확인합니다.

### 5.4 로컬 daemon 실행

VSCode Extension은 일반적으로 Extension Host가 daemon을 직접 시작합니다.
수동 실행이 필요하면 다음 형태를 사용합니다.

```powershell
python -m theseus_engine.daemon --workspace . --host 127.0.0.1 --port 0
```

`--port 0`은 사용 가능한 포트를 자동 선택합니다. daemon은
`.theseus/runner.json`에 접속 정보를 기록합니다.

stdio fallback을 직접 확인하려면 다음을 사용합니다.

```powershell
python -m theseus_engine.cli_runner --json-mode
```

### 5.5 VSCode Extension 간편 설치

Extension을 로컬 실행 환경과 함께 설치하려면 스크립트를 사용할 수 있습니다.
스크립트는 `.venv` 생성, `requirements.txt` 설치, VSIX 설치,
IDE별 `settings.json` 병합을 수행합니다.
VS Code는 기본적으로 워크스페이스 `.vscode/settings.json`, Antigravity는
사용자 설정 파일 `%APPDATA%\Antigravity\User\settings.json`을 사용합니다.
VSIX는 기본적으로 로그인 사용자 홈의 IDE 확장 저장소에 설치합니다.
VS Code는 `%USERPROFILE%\.vscode\extensions`, Antigravity는
`%USERPROFILE%\.antigravity\extensions`를 사용합니다.

Windows에서 가장 간단한 방법은 저장소 루트의
`Install-Theseus-Extension.cmd`를 더블클릭하는 것입니다. 이 파일은
`backend\theseus-core-server\scripts\install-vscode-extension.ps1`을 호출해
저장소 루트를 workspace path로, `backend\theseus-core-server`를 core path로
설정합니다. 자동 감지가 맞지 않으면 명령 프롬프트에서 다음처럼 실행합니다.

```cmd
Install-Theseus-Extension.cmd -Ide antigravity
Install-Theseus-Extension.cmd -Ide vscode
```

`-WorkspacePath`, `-CorePath`를 직접 넘기면 wrapper의 기본값 대신 사용합니다.
사용 가능한 옵션은 `Install-Theseus-Extension.cmd -Help`로 확인할 수 있습니다.

설치가 끝나면 IDE에서 Theseus 사이드바를 열고 `Theseus: Start Agent`를
실행합니다. Extension Host가 설정된 local Python venv로 daemon을 시작합니다.

테스트 배포에서 핵심 Python 소스 폴더를 직접 전달하지 않으려면 packaged
runner를 먼저 빌드한 뒤 Extension 설정에 연결합니다.

```powershell
cd backend\theseus-core-server
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\build-runner-binary.ps1 -InstallPyInstaller
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\install-vscode-extension.ps1 -RunnerPath .\dist\theseus-runner\theseus-runner\theseus-runner.exe
```

`-RunnerPath`를 지정하면 설치 스크립트가 `theseus.runnerPath`와
`theseus.runtimeMode=bundled-runner`를 기록합니다. 이 경우 Extension은
`python -m theseus_engine.daemon` 대신 runner binary를 실행합니다. 테스트
배포용 편의 기능이며, binary 역공학 방지나 라이선스/SBOM 정리는 별도 배포
단계에서 확인해야 합니다.

테스터에게 보내는 zip에는 다음 파일을 함께 넣으면 더블클릭 설치가 가능합니다.

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

테스터는 `Install-Theseus-TestPackage.cmd`를 더블클릭하고 workspace 경로만
입력하면 됩니다. 설치기는 VSIX 설치, `theseus.runnerPath` 설정, workspace
오픈까지 처리합니다. 패키지의 `README.md`에는 Theseus 소개, 폴더 구성,
더블클릭 실행 방법, CLI override 예시가 포함됩니다.

VSIX를 다시 빌드하면서 위 테스트 zip까지 한 번에 만들려면 다음 명령을
사용합니다. runner binary가 이미 빌드되어 있어야 합니다.

```powershell
cd backend\theseus-core-server\vscode-extension
npm.cmd run package:test
```

core runtime 코드도 바뀌어 runner binary를 다시 만들어야 하면 npm 인자를
PowerShell packager에 전달합니다.

```powershell
npm.cmd run package:test -- -BuildRunner
npm.cmd run package:test -- -BuildRunner -InstallPyInstaller
```

저장소 루트에서는 `Package-Theseus-TestPackage.cmd`를 더블클릭해 같은 흐름을
실행할 수 있습니다. 결과물은 기본적으로
`backend\theseus-core-server\dist\test-package\Theseus-TestPackage.zip`에
생성됩니다.

Git Bash에서는 같은 작업을 Bash wrapper로 실행할 수 있습니다.

```bash
bash Package-Theseus-TestPackage.sh
bash Package-Theseus-TestPackage.sh --build-runner --install-pyinstaller
```

서버 orchestration/API, 프론트엔드, 인프라를 제외하고 로컬 extension 설치와
실행에 필요한 source runtime만 묶으려면 별도 source package를 생성합니다.

```powershell
Package-Theseus-LocalExtension.cmd
```

또는 extension 폴더에서 VSIX 재빌드와 압축을 한 번에 실행합니다.

```powershell
cd backend\theseus-core-server\vscode-extension
npm.cmd run package:local-source
```

Git Bash에서는 다음 wrapper를 사용할 수 있습니다.

```bash
bash Package-Theseus-LocalExtension.sh
```

결과물은 기본적으로
`backend\theseus-core-server\dist\local-extension-package\Theseus-LocalExtensionSourcePackage.zip`에
생성됩니다. 이 패키지는 `theseus_engine`, `theseus_cli`, requirements, VSIX,
설치/삭제 스크립트, `usage.md`만 포함하며 `src`, `frontend`, `infra`,
`theseus-api-server`, `.venv`, `build`, `dist`, `tests`, 실제 `.env`는 제외합니다.

Windows PowerShell에서는 다음을 실행합니다.

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\install-vscode-extension.ps1
```

PowerShell에서도 현재 터미널/실행 중인 IDE를 기준으로 `code` 또는
`antigravity` CLI를 자동 선택합니다. 자동 감지가 맞지 않으면 설치 대상을
명시합니다.

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\install-vscode-extension.ps1 -Ide antigravity
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\install-vscode-extension.ps1 -Ide vscode
```

특정 CLI 경로를 직접 지정해야 하면 `-Code`를 사용합니다.
설정 디렉터리를 워크스페이스 기준으로 직접 지정해야 하면 `-SettingsDir`를
사용합니다.
portable/profile 구성으로 확장 저장소가 다르면 `-ExtensionsDir`를 사용합니다.

Git Bash, Linux, macOS에서는 다음을 실행합니다.

```bash
bash scripts/install-vscode-extension.sh
```

Git Bash에서는 현재 터미널/실행 중인 IDE를 기준으로 `code` 또는
`antigravity` CLI를 자동 선택합니다. 자동 감지가 맞지 않으면 설치 대상을
명시합니다.

```bash
bash scripts/install-vscode-extension.sh --ide antigravity
bash scripts/install-vscode-extension.sh --ide vscode
```

특정 CLI 경로를 직접 지정해야 하면 `--code`를 사용합니다.
설정 디렉터리를 워크스페이스 기준으로 직접 지정해야 하면 `--settings-dir`를
사용합니다.
portable/profile 구성으로 확장 저장소가 다르면 `--extensions-dir`를 사용합니다.

기본값은 `theseus-core-server`를 core path로, 저장소 루트를 workspace path로
사용합니다. 다른 프로젝트를 작업 워크스페이스로 연결하려면
`-WorkspacePath` 또는 `--workspace-path`를 지정합니다.

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\install-vscode-extension.ps1 -WorkspacePath C:\path\to\project
```

```bash
bash scripts/install-vscode-extension.sh --workspace-path /path/to/project
```

Playwright 기반 도구의 브라우저 바이너리까지 준비해야 하면
`-InstallPlaywright` 또는 `--install-playwright`를 추가합니다.
이 옵션은 기본 의존성에서 분리된 `playwright` 패키지를 설치한 뒤 Chromium
브라우저 바이너리를 준비합니다. 저장소에 포함된 예시 custom tool까지
실행하려면 별도로 `requirements-custom-tools.txt`를 설치합니다.

### 5.6 DB 스키마 초기화

현재 Core Server는 Alembic migration이 아니라 SQLAlchemy metadata
`create_all()`로 필요한 테이블을 자동 생성합니다. 서버 시작 시 `init_db()`가
호출됩니다. 수동 초기화가 필요하면 다음 스크립트를 사용할 수 있습니다.

```powershell
python scratch\create_db.py
```

## 6. 검증 명령

최근 문서에 기록된 주요 smoke/regression 명령은 다음과 같습니다.

```powershell
python -m unittest tests.test_local_daemon tests.test_query_engine_execution
python -m unittest tests.test_runner_runtime_plan_flow
python -m unittest tests.test_lsp_tool tests.test_task_manager
python -m py_compile theseus_engine\core\plan_flow.py theseus_engine\runner_runtime.py theseus_engine\tui\tui_main.py
```

VSCode Extension 변경 검증은 `vscode-extension`에서 실행합니다.

```powershell
npm.cmd run compile
node --check media\main.js
```

## 7. 폴더 구조

```text
theseus-core-server/
├── src/                         # FastAPI 서버 계층
│   ├── auth/                    # Spring session/auth/permission 연동
│   ├── builder/                 # 서버용 QueryEngine assembly, prompt injection
│   ├── db/                      # SQLAlchemy 모델, repository, DB 초기화
│   ├── history/                 # Spring history persistence 연동
│   ├── knowledge/               # 서버 스코프 knowledge/RAG 계층
│   ├── plan/                    # plan lifecycle persistence/gating
│   ├── remote_workspace/        # API resolver, SSH connector, remote_* tools
│   ├── routes/                  # health, stream, plan, sandbox routes
│   ├── sandbox/                 # Docker sandbox executor
│   ├── tooling/                 # 서버 tool artifact/persistence/activation
│   ├── tool_plan/               # 신규 tool plan Kafka worker
│   ├── tool_build/              # 신규 tool build Kafka worker
│   └── tool_generation/         # legacy generation adapter/consumer
├── theseus_engine/              # 에이전트 실행 코어
│   ├── core/                    # engine_builder, plan_flow, tool_retriever
│   ├── engine/                  # QueryEngine, StreamEvent, usage/cost
│   ├── memory/                  # scoped memory
│   ├── models/                  # modes, state machine façade, RBAC
│   ├── prompts/                 # canonical system prompt 본문과 builder
│   ├── tools/                   # core tools, validators, tool factory
│   ├── skills/                  # skill discovery/injection
│   ├── rag/                     # standalone RAG 경로
│   ├── tasks/                   # background task manager
│   ├── tui/                     # Textual TUI
│   ├── wrappers/                # LLM clients, hooks
│   ├── runner_runtime.py        # EditorRuntime 공용 런타임
│   ├── daemon.py                # local HTTP/SSE daemon
│   └── cli_runner.py            # stdio JSON Lines fallback
├── vscode-extension/            # VSCode Extension Host + WebView
├── scripts/                     # 로컬 설치/운영 보조 스크립트
├── docs/                        # history, roadmap, architecture, analysis 문서
├── tests/                       # unittest 기반 회귀 테스트
├── scratch/                     # 로컬 스크립트와 디버그 보조 파일
├── Dockerfile
├── requirements.txt             # Core 기본 의존성
├── requirements-browser.txt     # Playwright optional
├── requirements-custom-tools.txt # 번들 예시 custom tool optional
├── requirements-doc-tools.txt   # 문서/스프레드시트 tool optional
└── README.md
```

## 8. 운영 / 보안 주의사항

- 서버 SSE 경로는 클라이언트가 직접 과금 API를 호출하지 않게 하고, Core가
  billing outbox를 통해 내부망으로 사용량을 전달합니다.
- local daemon은 `127.0.0.1` bind와 bearer token 인증을 전제로 합니다.
- `.theseus/runner.json`은 런타임 상태 파일이므로 커밋 대상이 아닙니다.
- LangSmith tracing은 `LANGCHAIN_API_KEY`와 `THESEUS_TRACING_ENABLED=true`가
  모두 설정된 경우에만 활성화됩니다. 단, `LANGCHAIN_TRACING_V2=false`가
  설정되면 Theseus tracing wrapper는 우선적으로 bypass되며, decorator 적용
  실패 시에도 core import를 막지 않고 원본 호출로 폴백합니다.
- 생성된 custom tool과 shell 실행은 프로덕션에서 sandbox 또는 원격 실행
  격리를 거쳐야 합니다.
- `BashTool`, `write_file`, `edit_file` 같은 상태 변경 도구는 RBAC,
  permission prompt, validator/hook 정책의 대상입니다.
- Remote Workspace credential은 stream/Kafka/history/debug dump에 직접
  남기지 않습니다. 사용자/LLM 노출 metadata에는 redacted config만 사용하고,
  실제 SSH 실행은 Core helper/runtime key 경계에서 처리합니다.
- Remote Workspace write/command 도구는 AGENT 또는 승인된 tool 실행에서만
  열 수 있으며, ASK/PLAN에서는 read-only 도구만 노출합니다.
- 기본 `requirements.txt`는 Core 직접 의존성만 포함합니다. 브라우저 자동화,
  시스템 리소스 조회, speedtest, 문서 분석 패키지는 optional requirements로
  분리해 배포 크기와 라이선스/약관 리스크를 줄입니다.
- `lsp` tool은 workspace 밖 파일 접근을 차단하는 경로 보안 검사를 거칩니다.
- LLM API key는 provider별 placeholder/빈 값이면 조기 진단하도록 보완되어
  있습니다.

## 9. 현재 이행기 이슈와 다음 우선순위

문서상 현재 가장 중요한 정리 지점은 다음입니다.

1. Remote Workspace는 SSH MVP가 들어왔지만, 운영 배포 전에는
   `secretRef` 전환, known_hosts/fingerprint pinning, capability 기반
   allowlist, audit event를 API Server와 함께 설계해야 합니다.
2. `src/knowledge`와 `theseus_engine/rag`의 DB schema/API 충돌 가능성을
   먼저 정리합니다. 서버 기본값은 `src/knowledge` 기준이고, engine RAG tool은
   명시 opt-in입니다.
3. legacy `tool_generation` consumer와 신규 `tool_plan`/`tool_build`
   pipeline의 운영 경계를 명확히 하고 중복 소비를 방지합니다.
4. 서버 history에는 아직 구조화된 tool call/result 장기 복원이 완전하지
   않습니다. Core-only projection은 들어갔지만, 완전 복원은 API history schema
   확장이 필요합니다.
5. custom tool dependency와 라이선스 고지는 optional requirements 기준으로
   관리하고, VSIX/daemon binary 배포 전에는 `THIRD_PARTY_LICENSES`, `NOTICE`,
   SBOM 생성을 별도 작업으로 진행합니다.
6. VSCode Extension은 local daemon long-running run, hide/show,
   Extension Host reload, SSE reconnect/replay, stdio fallback을 실제
   Extension Host에서 계속 회귀 검증해야 합니다.
7. cooperative interrupt/cancel, destructive tool permission 승인 UX, runtime
   오류 원인 분류, Output Channel 액션을 이어서 완성합니다.
8. 서버 인증/sync, MCP bridge, `SKILL.md` 기반 Skill, Knowledge/Memory 관리
   UI는 local daemon runtime 위에 제품화 확장으로 통합합니다.
