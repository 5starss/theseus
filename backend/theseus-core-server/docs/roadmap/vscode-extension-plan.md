# VSCode Extension 구현 계획

> 작성일: 2026-05-08
> 최근 갱신: 2026-05-14 (Session 118)
> 배경: Theseus의 핵심 타겟은 "개발에 익숙하지만 에이전트에 익숙하지 않은 사용자"다.
> 이 사용자가 이미 있는 곳(VSCode)에 에이전트를 가져가는 것이 목표.

---

## 최근 적용된 변경 (Session 118 기준)

> 상세 내역은 `docs/history/CHANGELOG.md` Session 118 참고, 기능 명세는 `docs/architecture/vscode_extension_features.md` 참고.

- **툴바/UI**: 반응형 그리드 레이아웃, `Tools`/`Logs` 버튼은 Health 패널로 이동, 세션은 ▾ 아이콘 + tooltip, 📁 워크트리 빠른 선택 버튼/명령 추가
- **Activity Log**: 툴 호출이 있을 때만 노출, sticky 고정 제거, 내부 스크롤로 변경
- **Plan 패널**: 본문을 마크다운으로 렌더(JSON은 토글), Plan review 의사 분류는 엔진에 위임
- **세션·모드 안정화**: SessionManager `lastSentMode` 도입으로 mode 알림 스팸 제거, busy 상태에서도 세션 전환 가능(이벤트 기반 대기), history snapshot 보수적 재생
- **엔진 정합성**: dynamic tool retrieval 메타 자동 반영(✓ 마커), permission 메시지에 `toolName`/`session` 추가

---

## 포지셔닝

| 도구 | 타겟 | 커스텀 툴 |
|------|------|----------|
| Claude Code | 범용 개발자 | 없음 (MCP만) |
| Cursor | 범용 개발자 | 없음 |
| Copilot | 범용 개발자 | 없음 |
| **Theseus** | 에이전트 초보 개발자 | **핵심 차별점** |

커스텀 툴을 코드로 작성하고 에이전트에 즉시 연결하는 경험은
현재 어떤 도구도 잘 제공하지 않는다.

---

## 전체 아키텍처

Extension / 백엔드 / 프론트는 완전히 디커플링된 독립 작업이다.

```
VSCode Extension (사용자 PC)
    │
    ├── THESEUS_SERVER_URL = ""                      → standalone (서버 없음)
    ├── THESEUS_SERVER_URL = "https://company-a.io"  → A사 서버 연결
    └── THESEUS_SERVER_URL = "https://company-b.io"  → B사 서버 연결
            │
            ▼ (URL만 변경, 코드 변경 없음)
    Java 백엔드 (회사/서버 단위 배포)
        ├── 프로젝트 설정 API
        ├── 대화 이력 저장
        └── 토큰 과금 집계
```

Extension은 URL 하나만 바꾸면 어느 서버에도 연결된다.
백엔드가 없어도 standalone으로 완전 동작한다.

---

## Claude Code 참고 패턴

> 코드 복사가 아니라, 확인된 런타임 생명주기 패턴만 Theseus 구조에 맞게 적용한다.

- **Extension Host owns sessions/processes**
  - Python runner process, session id, runner state, ready timeout, lifecycle log는 WebView가 아니라 Extension Host가 소유한다.
  - WebView의 Start 버튼은 새 process를 직접 의미하지 않고 `ensureSession()` 요청을 의미한다.
- **WebView is attachable client**
  - WebView는 현재 Extension Host session에 attach되는 클라이언트다.
  - WebView 재생성, 탭 복귀, focus 변화는 process spawn/kill 조건이 아니다.
- **Visibility change is signal only**
  - `visibilitychange` / `onDidChangeVisibility`는 현재 상태 재동기화와 active file refresh 신호로만 사용한다.
  - 명시적 Stop이 아닌 숨김/dispose 이벤트로 runner를 종료하지 않는다.
- **Transient status is not chat history**
  - `Connected`, `Runner stopped`, startup stale, settings changed 같은 연결/진단 메시지는 대화 이력 source of truth에 저장하지 않는다.
  - 대화 히스토리와 connection/session state 메시지를 프로토콜 레벨에서 분리한다.
- **Serializer is required for editor panel restore**
  - 현재 sidebar view는 `retainContextWhenHidden`와 Extension Host 상태 재전송으로 복귀를 처리한다.
  - 향후 editor tab/panel을 추가하면 `registerWebviewPanelSerializer`로 VS Code 창 복원 시 동일한 attach 흐름을 보장해야 한다.

---

## 세 컴포넌트의 독립성

| 컴포넌트 | 작업 범위 | 의존 관계 |
|---------|---------|---------|
| **Extension** | theseus_engine 코어 + WebView UI | 백엔드 없이 standalone 동작 |
| **백엔드** | 회사 단위 배포, 설정/인증/과금 API | Extension 없이 웹 프론트로 독립 동작 |
| **웹 프론트** | 프로젝트 설정 관리 UI | Extension 없이 독립 동작 |

세 작업을 완전히 병렬로 진행할 수 있다.

---

## Extension 내부 아키텍처

```
VSCode Extension (TypeScript)
    │
    │  child_process.spawn 또는 로컬 HTTP
    ▼
theseus_engine (Python)           ← 코어 수정 없음
    - StreamEvent를 JSON 줄 단위로 stdout 출력
    - THESEUS_SERVER_URL 설정 시 ProjectClient로 백엔드 연동
    │
    ▼
Extension WebView (HTML/CSS/JS)
    - 대화창
    - 툴 실행 현황 패널
    - 커스텀 툴 목록
```

TUI에서 검증한 상태 머신, PLAN 워크플로우, 툴 실행 루프를 그대로 재사용한다.

---

## 선행 작업 1개 (TUI 고도화 불필요)

현재 코어(`StreamEvent`, `QueryEngine`, `ProjectClient`)는 Extension에서 바로 사용 가능하다.
Extension이 파싱할 수 있는 **JSON 모드 진입점**만 추가하면 된다.

```python
# theseus_engine/cli_runner.py (신규, 50줄 이내)
async for event in engine.submit_message(line):
    print(json.dumps({
        "type": type(event).__name__,
        **asdict(event)
    }), flush=True)
```

TUI 고도화 없이 Extension 개발을 바로 시작할 수 있다.

### 현재 구현 상태 (2026-05-12, Session 64)

선행 작업과 Phase 1~4 프로토타입 완료. Session 58에서 AuditLLM 응답 파싱 오류와 에이전트 루프 가시성 문제를 보완했고, Session 59~62에서 VSCode WebView 재진입/탭 복귀, stale runner revive/reattach, stdio orphan cleanup을 보완했다. Session 63에서는 `EditorRuntime` 공용 런타임과 local HTTP/SSE daemon을 추가해 `local-daemon`이 Extension의 우선 실행 경로가 되었고, 기존 stdio JSON Lines runner는 fallback/debug 경로로 남겼다. Session 64에서는 daemon runner state schema validation, `/status` heartbeat polling, SSE reconnect/replay를 추가해 local daemon 안정화 1차 리스크를 낮췄다. 입력창 하단 모드 선택 UI는 공식 모드 전환 경로이며, 사용자-facing 모드 전환 슬래시 명령어(`/agent`, `/ask`, `/plan`, `/coordinator`)는 제거된 상태다.

- `theseus_engine/runner_runtime.py` 구현 완료
  - stdio runner와 local daemon이 공유하는 `EditorRuntime` 추가
  - QueryEngine 초기화, session/slash 명령, mode 전환, PLAN 승인/거부 처리 통합
  - `.theseus_sessions/*.json` 기반 local session provider 유지
- `theseus_engine/daemon.py` 1차 구현 완료
  - bearer token 기반 `127.0.0.1` local HTTP/SSE daemon
  - `GET /health`, `GET /status`, `POST /runs`, `GET /runs/{runId}/events`, `POST /runs/{runId}/interrupt`
  - `.theseus/runner.json`에 pid/host/port/token/workspace/coreRoot/runtime mode 저장
- `theseus_engine/cli_runner.py` stdio fallback 구현 완료
  - stdin 프롬프트 입력
  - stdout JSON Lines 이벤트 출력
  - stderr로 Core 내부 일반 출력 분리
  - `RunnerReady`, `RunnerStopped`, `ErrorEvent` 처리
- `vscode-extension/` Extension 프로토타입 구현 완료
  - Activity Bar `Theseus` 컨테이너
  - Sidebar WebView `Chat`
  - `theseus.start` / `theseus.stop` 명령
  - local daemon attach/start 후 HTTP/SSE로 runner event 수신
  - daemon attach/start 실패 시 `python -m theseus_engine.cli_runner --json-mode` stdio fallback
  - `theseus.pythonPath`, `theseus.serverUrl` 설정 추가
  - `THESEUS_SERVER_URL` 환경변수 주입
- WebView UI 1차 구현 완료
  - 사용자 입력 composer
  - Assistant text delta 스트리밍 표시
  - 툴 실행 시작/완료 이벤트 접이식 패널 표시
  - runner 상태 및 오류 메시지 표시
- 모드 전환 UX 정리 완료
  - 하단 모드 선택 UI: Agent / Ask / Plan 전환
  - `/` 자동완성에는 유틸리티 명령만 표시
  - 직접 입력한 `/agent`, `/ask`, `/plan`, `/coordinator`는 system 안내 후 종료
  - 내부 모드 전환은 WebView `setMode` 메시지 → runner JSON 명령으로 분리
- 에이전트 루프 상태 가시화 1차 구현 완료
  - Core `AgentLoopStatus` 이벤트로 모델 턴, 툴 실행, 루프 완료/오류 상태 전달
  - Extension 툴바 `loop-status`로 `thinking`, `running tools`, `tool done`, `loop error` 표시
  - 툴 실행 항목은 완료 후에도 열린 상태를 유지해 호출 여부와 결과 확인 가능
- Runner 재연결/시작 상태 안정화 1차 구현 완료
  - Extension Host 안에 Python child process가 살아 있으면 Start 버튼은 새 프로세스를 만들지 않고 기존 runner 상태를 WebView에 재전송
  - `RunnerStatus`가 `processRunning`과 `lifecycle: ready|starting|stopped`를 전달해 WebView가 시작 중/연결됨/중지 상태를 구분
  - `RunnerStatus`가 `pythonExec`, `coreRoot`, `workspaceCwd`, `lastDiagnostic`도 전달해 WebView 상태 재조회 시 실행 경로와 마지막 실패 원인을 복구
  - WebView는 `runnerState`와 `applyRunnerStatus()`를 통해 runner 상태 갱신 경로를 단일화
  - 탭 복귀/웹뷰 재생성 시 `getRunnerStatus`/`attachSession`으로 기존 process 상태를 자동 재동기화
  - process가 starting 상태일 때 입력한 메시지는 `RunnerReady` 이후 자동 전송
  - `proc && lastReadyEvent`가 있는 stale/starting/error 상태는 attach 가능한 runner로 보고 `ready` 또는 `waiting_input`으로 revive
  - 기존 process가 stale/error 상태라도 `lastReadyEvent`가 없을 때만 unhealthy process로 보고 Start 요청 시 자동 재시작
  - process가 살아 있는데 WebView 상태만 stale이면 pending 입력을 보관하고 재부착 후 자동 전송
  - stopped 상태 또는 process가 없는 error 상태에서는 pending 입력을 자동 전송하지 않고 마지막 진단 또는 Start 필요 안내를 표시
  - Extension Host가 재시작되어 stdio pipe를 잃은 runner는 `.theseus/runner.json`의 pid를 기준으로 orphan 정리 후 새 runner 시작
  - `stop()`/child exit/error 시 `.theseus/runner.json` 삭제
- Local daemon 런타임 안정화 1차 구현 완료
  - Start 시 `.theseus/runner.json`의 daemon metadata를 읽고 `/health` 성공 시 attach
  - live daemon이 없거나 health check가 실패하면 cleanup 후 새 daemon 시작
  - daemon run은 `POST /runs`와 SSE event stream을 통해 기존 WebView event 흐름으로 전달
  - daemon 연결 오류는 pid/state 파일 cleanup과 재연결 안내 진단으로 표시
- Local daemon 런타임 안정화 2차 구현 완료
  - `.theseus/runner.json`에 `schemaVersion`, `sessionId`, `workspaceHash`를 추가하고 Extension attach 시 schema/workspace/coreRoot 정합성 검증
  - daemon `/status` heartbeat polling으로 stale 판정과 회복 처리 추가
  - SSE reconnect 시 `after=<eventCount>` 기반 run event replay 지원
  - daemon event stream을 queue 단일 소비 구조에서 run별 event buffer + condition 알림 구조로 변경해 중복 replay 방지
- AuditLLM 안정화 1차 완료
  - 예시 JSON 포맷 문자열 오류 수정
  - list content block 응답 정규화
  - native `stream_message()` 기반 감사 호출 fallback 추가
- LLM 설정 진단 1차 완료
  - provider별 API key 누락/placeholder 값을 `AuthenticationFailure`로 조기 진단
  - Gemini `GOOGLE_API_KEY` fallback 추가
- TypeScript 컴파일 및 VSIX 패키징 완료
  - `theseus-vscode-0.0.1.vsix`

남은 핵심 리스크는 실제 VSCode Extension Host에서의 end-to-end 회귀 검증, cooperative cancel/권한 승인 UX, Extension/WebView event switch 모듈화, 서버 인증·MCP·Skill 제품화다.

---

## 구현 단계

### Phase 1 — 기반 구조 ✅ 완료

- [x] `theseus_engine/cli_runner.py` — JSON 모드 진입점 구현
- [x] Extension 스캐폴딩 (`vscode-extension/`)
- [x] 사이드바 WebView 패널 등록
- [x] `child_process.spawn("python -m theseus_engine.cli_runner --json-mode")` 연결
- [x] stdout JSON 파싱 → WebView 메시지 전달
- [x] 대화 입력창 + 응답 텍스트 렌더링
- [x] VSCode Extension Host 실제 설치/실행 검증 완료
- [x] `theseus.corePath` 설정으로 Python 코어 경로 지정
- [x] 비정상 종료 시 stderr → WebView 에러 표시
- [x] `OPENHARNESS_MODEL` / `THESEUS_MODEL` 동시 지원 (fallback 통일)

**완료 기준**: VSCode 사이드바에서 에이전트와 대화 가능 ✅

---

### Phase 2 — UX 기반 기능 ✅ 완료

- [x] `ToolExecutionStarted` / `ToolExecutionCompleted` 이벤트 패널 분리 표시
- [x] 툴 이름, 입력 인자, 출력 결과 접이식 패널 (실행 중 → 완료로 동일 항목 업데이트)
- [x] 질문 단위 Activity 아코디언으로 해당 user turn의 tool 실행 이력 묶기
- [x] 에러 발생 툴 강조 표시
- [x] Enter = 전송 / Shift+Enter = 줄바꿈 (채팅 컨벤션)
- [x] 대화 기록 유지 (`vscode.getState()` — WebView 재열림 시 자동 복원)
- [x] `/` 슬래시 명령어 자동완성 드롭다운 + Tab 즉시 완성
- [x] `/` 슬래시 명령어 실행 처리 (cli_runner.py 명령어 인터셉터)
- [x] 사용자-facing 모드 전환 slash 명령 제거 (`/agent`, `/ask`, `/plan`, `/coordinator`)
- [x] 하단 모드 선택 UI → 내부 `setMode` bridge → runner JSON 명령으로 모드 전환 경로 분리
- [x] `@` 워크스페이스 파일 경로 자동완성 드롭다운
- [x] 마크다운 코드블록 렌더링 + Copy 버튼
- [x] 생성 중 Stop 버튼
- [x] 툴바: Start / Stop / Clear / 세션 표시
- [x] `theseus.corePath` 미설정 시 설정 페이지 안내 팝업
- [x] `custom_tools/` 디렉토리 파일 감지 → 툴 등록 알림
- [x] 장시간 실행 툴 진행 상태 표시 (30초 이상 elapsed/running-long)
- [x] 툴 실행 이력 최대 표시 개수 정리 정책 (최근 30개 기본 표시, older 접기)

**완료 기준**: 에이전트가 어떤 툴을 실행하는지 실시간 확인 + 기본 채팅 UX ✅

---

### Phase 3 — 편집기 연동 (2~3주)

- [x] 현재 열린 파일 경로 상태 표시와 조건부 컨텍스트 주입 (툴바 표시 + activeFileChanged 이벤트)
  - active file은 기본적으로 상태 표시만 하고, 사용자가 “현재 파일/이 파일/여기”처럼 현재 편집기 컨텍스트를 명시할 때만 `IDE 보조 컨텍스트`로 추가
  - 사용자가 `@file`을 명시한 입력에는 자동 active file을 추가하지 않아 명시적 context 선택을 우선
- [x] 선택한 코드 블록 에이전트에 전달 (`우클릭 → Ask Theseus` / `Explain Selection`)
- [x] 에이전트가 수정한 파일 → VSCode Diff 뷰 표시
- [x] PLAN 모드 태스크 체크리스트 사이드바 연동
- [x] 현재 커서 위치 파일/라인 컨텍스트 조건부 포함

**완료 기준**: 코드 작업 중 에디터를 벗어나지 않고 에이전트 활용 가능

---

### Phase 4 — 커스텀 툴 UX (1~2주)

- [x] `custom_tools/*.py` 저장 시 자동 감지 + 등록 성공/실패 알림
- [x] 툴 목록 WebView 패널 (이름, 권한 레벨, 상태)
- [x] `create_tool` 성공 시 편집기에서 생성된 파일 자동 열기
- [x] 툴 권한 레벨 인라인 수정 UI
- [x] 툴 실행 성공/실패 통계 누적 표시

**완료 기준**: 툴 파일을 저장하는 것만으로 에이전트가 즉시 사용 — 설정 불필요

---

### Phase 5 — 서버 연동 (URL 설정만으로 완성)

- [x] `theseus.serverUrl` 설정으로 `THESEUS_SERVER_URL` 주입
- [x] `theseus.corePath`, `theseus.pythonPath` 설정 추가
- [ ] 백엔드 로그인 → JWT 토큰 발급 → Extension에 자동 주입
- [ ] 연결 상태 표시 (standalone / 서버 연결됨) 툴바 인디케이터
- [ ] `THESEUS_PROJECT_ID`, `THESEUS_SESSION_TOKEN` 설정/저장 방식 확정
- [ ] 서버 연결 실패 시 standalone fallback 또는 명시적 오류 정책

**완료 기준**: URL 입력 후 팀/회사 서버에 즉시 연결

---

### Phase 6 — UX 고도화 (추가 검토)

> 범용 채팅 에이전트 도구들의 편의 기능 벤치마크 기반으로 도출.

#### 입력 UX
- [x] 이전 입력 히스토리 `↑/↓` 키 탐색 (터미널 방식)
- [x] 멀티라인 편집 시 자동 높이 확장 (textarea auto-resize)
- [x] `@` 파일 경로 자동완성 안정화 (검색어 우선 필터링, workspacePath 기준 정합성, 공백 경로 처리)
- [x] 드래그 앤 드롭으로 파일 경로 삽입
- [x] 이미지 붙여넣기 → `.theseus/assets/` 저장 후 경로 자동 삽입

#### 메시지 UX
- [x] 메시지별 복사 버튼 (전체 assistant 메시지 복사)
- [x] 메시지 재전송 버튼 (user 메시지 hover → ↺ 버튼 → 입력창 재삽입)
- [ ] 어시스턴트 응답 스트리밍 중 부분 텍스트 선택/복사
- [x] 긴 응답 접기/펼치기 (25줄 이상 자동 fold + 더 보기 버튼)
- [x] 타임스탬프 표시 (hover 시)

#### 세션 UX
- [x] 세션 목록 패널 (`/session list` 결과를 사이드바 드롭다운으로)
- [x] 원클릭 새 세션 생성과 세션별 삭제 버튼
- [x] 우측 상단 세션 메뉴에서 새 세션명 직접 입력 생성과 compact `x` 삭제 버튼 제공
- [x] 세션 목록 아코디언 + `+` 버튼으로 untitled session 생성, 첫 질문 기반 title metadata 저장
- [x] 세션 이름 변경 UI
- [ ] 세션별 토큰 사용량 요약 표시
- [x] 세션 내보내기 (Markdown / JSON)
- [x] 로컬 SessionProvider 구현 완료 (`source: "local"` 이벤트, 서버 provider 확장 가능)
- [x] 세션별 PLAN 상태 분리 (`.theseus_sessions/<session>.json`의 `plan_state` 저장/복원)

#### PLAN 모드 UX
- [x] PLAN Drafting 단계: 태스크 체크리스트 별도 패널 표시
- [ ] PLAN Executing 단계: 현재 실행 중인 스텝 강조
- [x] 승인/거부 버튼 인라인 표시 (WAIT_FOR_REVIEW 상태)
- [x] 승인 버튼/짧은 자연어 승인 후 다음 입력 없이 PLAN Executing 바로 시작
- [x] 진행 중인 PLAN 빠른 취소/삭제 액션 (`Cancel`, `Delete`, `/plan cancel`, `/plan delete`)
- [x] 계획 JSON 구조화 표시 (트리 뷰)

#### 접근성 / 품질
- [ ] 키보드 전용 조작 완성 (마우스 없이 모든 기능 사용 가능)
- [x] 응답 중 로딩 인디케이터 (점 바운스 애니메이션)
- [x] 에러 재시도 버튼 (RunnerError 발생 시 "↺ Restart Agent" 인라인)
- [x] 설정 변경 시 재시작 필요 배너 표시 (runner 중지 상태는 다음 Start 때 반영)
- [x] 에이전트 루프 상태 표시 (`AgentLoopStatus` → 툴바 loop-status)
- [x] WebView 재진입/탭 복귀 시 기존 runner 상태 재동기화 (`RunnerStatus.processRunning`, `lifecycle`)
- [x] Start 버튼 중복 클릭 시 기존 process 재사용 및 상태 재전송
- [x] WebView runner 상태 갱신 경로 단일화 (`runnerState`, `applyRunnerStatus`)
- [x] Runner startup 진단 보존 (`RunnerStatus.lastDiagnostic`, 실행 경로 metadata)
- [x] stale/processRunning 상태에서 기존 runner revive 및 WebView pending 입력 자동 재전송
- [ ] 실제 runner ping/status command 기반 alive check
- [ ] Stop generation을 실제 runner interrupt/cancel 프로토콜로 연결

---

### Phase 7 — Agent 역량 확장 (MCP / Skills / Knowledge)

> Extension이 단순 채팅 클라이언트를 넘어서, 프로젝트별로 확장 가능한 에이전트 런타임이 되기 위한 기능.

#### MCP 확장
- [ ] MCP 서버 등록 UI
  - 프로젝트별 `.theseus/mcp.json` 또는 VSCode 설정(`theseus.mcpServers`)에 MCP 서버 목록 저장
  - command / args / env / cwd / enabled 필드 지원
- [ ] MCP 서버 연결 상태 패널
  - connected / disconnected / error 상태 표시
  - 연결 실패 시 stderr 또는 handshake 오류를 WebView에서 확인
- [ ] MCP tool discovery → Theseus ToolRegistry 브릿지
  - MCP tool schema를 Core `BaseTool` compatible wrapper로 변환
  - 권한 레벨, 프로젝트 스코프, 실행 로그를 기존 tool 패널과 동일하게 표시
- [ ] MCP 리소스 / 프롬프트 탐색
  - resource 목록을 `@` mention 후보 또는 별도 picker로 노출
  - prompt template은 `/` 명령이 아니라 composer action으로 삽입
- [ ] 보안 정책
  - MCP 서버별 허용 권한 레벨 설정
  - 네트워크/파일 시스템 접근이 강한 MCP 서버는 기본 비활성 또는 승인 필요

#### `SKILL.md` 기반 스킬 시스템
- [ ] 프로젝트 스킬 디렉토리 표준화
  - 후보 경로: `.theseus/skills/<skill-name>/SKILL.md`
  - 스킬은 설명, trigger 조건, 사용 절차, 참조 파일, 제한 사항을 포함
- [ ] Skill discovery
  - Extension 시작 또는 workspace 변경 시 `SKILL.md` 스캔
  - 스킬 이름, 설명, trigger 키워드를 WebView 패널에 표시
- [ ] Skill activation
  - 사용자가 명시적으로 스킬을 선택하거나, 입력 내용이 trigger와 일치할 때 system context로 주입
  - 자동 활성화는 과도한 컨텍스트 주입을 피하기 위해 "추천 → 적용" 흐름 우선
- [ ] Skill authoring UX
  - 새 스킬 생성 command: `Theseus: Create Skill`
  - 템플릿: 목적, 언제 사용할지, 절차, 금지사항, 예시 입력/출력
  - `SKILL.md` 저장 시 lint/preview 제공
- [ ] Core 연동
  - `QueryEngine`에 active skills metadata 전달
  - 스킬 본문은 필요 시점에만 로드해 토큰 낭비 방지
  - 세션 이력에는 "어떤 스킬이 적용됐는지"만 메타데이터로 저장

#### Agent Memory / Knowledge 보강
- [ ] 프로젝트 규칙 자동 수집
  - README, docs/conventions, `.editorconfig`, package scripts 등 요약
  - 항상 주입하지 않고 작업 유형별로 retrieval
- [ ] 장기 메모리와 스킬 분리
  - Memory: 프로젝트 사실, 사용자 결정, 과거 작업 이력
  - Skill: 반복 가능한 절차와 도구 사용법
- [ ] Knowledge source 관리 UI
  - 인덱싱 대상 문서 추가/제외
  - 마지막 ingest 시각, chunk 수, 검색 테스트 표시

#### 완료 기준
- Extension에서 MCP 서버와 프로젝트 스킬을 등록/확인할 수 있다.
- 에이전트가 선택된 MCP tool과 skill 절차를 기존 ToolRegistry/StreamEvent 흐름 안에서 사용한다.
- skill과 memory가 구분되어 저장되고, 컨텍스트 주입량이 제어된다.

---

### Phase 8 — Extension Runtime 안정화

> 목표: WebView 생명주기와 Python runner 생명주기를 분리하고, 시작/중단/재연결 실패 원인을 사용자가 구분할 수 있게 한다.

- [x] `TheseusSessionManager` 도입
  - 단일 active session 기준으로 `sessionId`, `state`, `proc`, `readyEvent`, `pendingInput`, `lastEventAt`, `lastHeartbeatAt`, `exitReason`을 Extension Host에서 관리
  - 기존 process가 살아 있으면 Start/attach 요청은 새 spawn 없이 현재 state를 재전송
- [x] session/channel protocol 1차 정리
  - WebView → Extension: `init`, `launchSession`, `attachSession`, `sendInput`, `setMode`, `stopSession`, `interruptSession`, `getStatus`, `visibilityChanged`
  - Extension → WebView: `sessionState`, `runnerEvent`, `diagnostic`, `historySnapshot`, `transientNotice`
  - 기존 `start`, `send`, `stop`, `getRunnerStatus` 메시지는 호환용으로 유지
- [x] startup diagnostics 1차
  - `RunnerReady` timeout 시 process를 죽이지 않고 `starting_stale`/`stale` 상태와 diagnostic을 표시
  - spawn 실패, import 실패 추정, crash exit, user stop, send failure를 서로 다른 diagnostic code로 분류
  - 최근 100개 lifecycle event를 in-memory ring buffer로 유지하고 `Theseus: Show Logs`에서 Output Channel에 표시
- [x] MessageQueue 1차
  - WebView `postMessage`를 직렬화해 session state와 runner event 순서 꼬임을 줄임
- [x] Session State Store 1차
  - `workspaceState`에는 마지막 active session metadata만 저장
  - 실제 대화는 기존 WebView state / `.theseus_sessions` / runner history를 source of truth로 유지
- [x] stdio runner orphan cleanup 1차
  - `.theseus/runner.json`에 현재 runner pid/session/workspace metadata 저장
  - Extension Host 재시작 등으로 `this.proc` pipe를 잃은 경우 pid 파일 기준 orphan process를 정리하고 새 runner를 시작
  - stop/exit/error 시 pid 파일을 삭제하고, pid mismatch 시 새 runner 상태 파일을 지우지 않도록 보호
- [x] local daemon 런타임 1차
  - `theseus_engine.daemon`이 local HTTP/SSE API와 bearer token 인증을 제공
  - Extension Start 시 live daemon health check 후 attach하고, 없으면 새 daemon을 시작
  - daemon attach/start 실패 시 stdio runner fallback으로 복구
  - daemon run event는 기존 `RunnerEvent` 흐름으로 WebView에 전달
- [ ] Heartbeat runner event
  - daemon `/status` 또는 `RunnerHeartbeat` 기반 alive check를 추가
  - Extension Host는 heartbeat stale을 UI stale/reconnecting 상태로 노출
- [ ] interrupt/cancel protocol 완성
  - 현재 daemon `POST /runs/{runId}/interrupt`와 stdio JSON interrupt 요청은 1차 bridge
  - Python runner와 QueryEngine 쪽 cooperative cancel 처리 필요
- [ ] optional editor panel serializer
  - sidebar 외 editor tab/panel 제공 시 `WebviewPanelSerializer`로 reload/window restore attach 보장
- [ ] Extension 코드 모듈화
  - `extension.ts`의 session/process 관리, WebView provider, diff provider, custom tool 관리, path/config utility를 파일 단위로 분리
  - 기능 이동만 수행하고 public command id, WebView message shape, VSCode 설정명은 유지
- [ ] WebView 코드 모듈화
  - `media/main.js`를 state, protocol, message list, tool panel, plan panel, composer, session menu, autocomplete 모듈로 분리
  - 직접 DOM 조작을 줄이고 render/update 경계를 명확히 해 상태와 UI 동기화 버그를 줄임
- [ ] WebView HTML 템플릿 분리
  - `extension.ts` 내부 하드코딩 HTML 문자열을 별도 template 또는 view builder로 분리
  - CSP nonce, resource URI 주입, command id는 Extension Host에서 관리

#### 추가 기술 후보

- `AbortController`: stop/interrupt/restart 시 child process와 pending request 취소를 같은 생명주기로 묶는다.
- `MessageQueue`: WebView `postMessage`를 직렬화해 상태 이벤트 순서를 안정화한다.
- `Heartbeat`: Python runner가 주기적 heartbeat/status event를 발행해 stale 감지를 가능하게 한다.
- `Session State Store`: `workspaceState`는 마지막 active session metadata만 저장하고 대화 source of truth는 runner/session history로 유지한다.
- `Diagnostics Layer`: spawn 실패, Ready timeout, model init 실패, Python import 실패, user stop, crash exit를 서로 다른 원인 코드로 노출한다.
- `WebviewPanelSerializer`: sidebar 외 editor tab/panel 지원 시 필수로 추가한다.
- `Typed Protocol`: Extension Host와 WebView가 공유하는 message/event 타입을 `src/shared/protocol.ts`로 정의해 postMessage 런타임 오류를 줄인다.
- `Vite/React/Vue`: WebView가 더 복잡해질 경우 선택적으로 도입한다. 1차 리팩토링은 ES Modules와 typed protocol로 진행하고, 프레임워크 도입은 이후 판단한다.

---

## 코드 리팩토링 및 모듈화 과제

> 판단: 코드 리뷰 피드백은 적절하다. 구조 개선 1~6차로 `SessionManager`, runner client, pid/process utility, diff provider, workspace helper, WebView HTML template, feature helper, WebView ES Modules, typed event schema, WebView 주요 component, `ChatViewProvider`를 분리했다. 현재 `vscode-extension/src/extension.ts`는 약 123라인, `media/main.js`는 약 880라인까지 줄었다. 남은 큰 덩어리는 WebView host event switch와 daemon 안정화 작업이다.

### 진행 현황 (2026-05-12)

- [x] `src/shared/protocol.ts` 추가
  - `RunnerEvent`, Host → WebView, WebView → Host 메시지 타입 정의
  - `asWebviewToHostMessage()` guard로 WebView message routing 진입점 검증
- [x] `media/protocol.js` 추가
  - WebView에서 `acquireVsCodeApi()`를 protocol wrapper로 감싸고, host message shape를 normalize
- [x] WebView utility module 1차 분리
  - `media/markdown.js`: assistant/message markdown rendering helper 분리
  - `media/runnerStatus.js`: runner lifecycle normalize와 diagnostic text formatting helper 분리
  - `ChatViewHtml.ts`가 `protocol.js` → utility helper → `main.js` 순서로 script를 로드
- [x] WebView ES Modules 1차 분리
  - `media/main.js`를 `type="module"`로 로드하고 CSP에 `webview.cspSource`를 추가해 module import를 허용
  - `media/state.js`: `vscode.getState()` 초기화와 `vscode.setState()` persistence adapter 분리
  - `media/components/Autocomplete.js`: slash/mention 자동완성 상태, 키보드 처리, 후보 DOM 갱신 분리
  - `media/components/MessageList.js`: transient message 필터, fold, typing indicator, retry banner helper 분리
  - `media/components/PlanPanel.js`: PLAN task/checklist/json render 분리
  - `media/components/CustomTools.js`: custom tool list, permission input render 분리
- [x] WebView component 잔여 1차 분리
  - `media/components/ToolPanel.js`: tool started/completed DOM, long-running timer, diff action, create_tool 후속 액션 분리
  - `media/components/SessionMenu.js`: session list/action render와 New/Rename/Export action wiring 분리
  - `media/components/Composer.js`: mention insertion, pasted/dropped image save bridge 분리
  - `media/components/RunnerStatus.js`: loop-status render, AgentLoopStatus label formatting, RunnerStatus state transition helper 분리
- [x] PLAN 리뷰 패널/Custom Tools/Slash UI 안정화
  - `승인`, `진행해`, `approve`, `reject`, `취소`처럼 짧은 자연어 PLAN 리뷰 결정을 runtime review action으로 정규화
  - `PlanReviewEvent` 승인/거부/완료 수신 시 WebView 저장 plan을 정리해 WAIT_FOR_REVIEW가 아닌 상태의 승인/거부 버튼이 남지 않도록 수정
  - `WAIT_FOR_REVIEW`가 아닌 상태로 도착한 stale 승인/거부 요청은 `PlanReviewEvent(action=not_reviewable)`로 정규화하고, WebView는 기존 오류 문구를 표시하지 않고 PLAN 패널만 정리
  - Custom Tools 패널은 헤더만 남기고 접을 수 있으며 접힘 상태는 WebView state에 저장
  - daemon startup에서 runner runtime을 미리 초기화하고 상태 재동기화 때 Custom Tools 목록을 refresh
  - `/plan approve` / `/plan reject`는 mode slash 차단에 걸리지 않으며 `/help`, `/tools`, `/session`, `/session list`는 runner 없이도 로컬 처리
  - `/cost`, `/stats`, `/validate` 같은 runner slash command에는 active file cursor context를 주입하지 않아 slash command 그대로 전달
  - plan header, custom tools permission controls, composer footer가 좁은 사이드바에서 wrap되도록 CSS min-width/grid/flex 규칙 보강
  - PLAN state를 session별로 저장하고 cancel/delete 액션으로 stale PLAN 패널과 runner `plan_state`를 함께 정리
  - PLAN approve는 review event 이후 같은 runner submit 루프에서 실행 프롬프트로 이어지고, session menu는 새 세션/삭제를 버튼으로 처리
  - tool 실행 이력은 전역 나열 대신 마지막 사용자 질문 아래의 Activity 아코디언으로 묶고, 실행/완료/실패 상태와 diff action을 같은 group에서 갱신
- [x] P0~P2 UX/UI 개선
  - `RunnerStatusBar` 역할을 `media/components/RunnerStatus.js`로 확장해 runner 상태 문구, 마지막 diagnostic tooltip, Start/Reconnect/Restart/Logs/Tools/Health 액션을 toolbar에 통합
  - PLAN panel을 stepper 기반 흐름(`Draft → Review → Execute → Verify → Done`)으로 바꾸고 review 상태에서만 승인/거부를 노출, 완료 plan은 접힌 요약으로 전환
  - `metadata.changed_file.old_content` 기반 Diff Snapshot 변경 검토 패널을 추가하고 Extension Host에서 파일 단위 revert를 처리
  - composer context bar에서 session, active file, `@` mention context를 pill로 보여주며 removable context는 다음 전송에서 제외
  - Custom Tools manager에 검색, 상태 필터, 정렬, details 기반 상세 보기와 좁은 sidebar 대응 layout을 추가
  - `/` 자동완성을 command palette 형태로 바꾸고 각 command의 설명과 실행 조건을 표시
  - agent busy 상태에서도 WebView가 메시지를 보류하지 않고 즉시 Extension Host로 전달하며, 실행 직렬화는 SessionManager/daemon 계층에 맡김
  - Problems context menu command(`Theseus: Explain Problem`, `Theseus: Fix Problem`)를 추가해 diagnostic context를 prompt에 주입
  - WebView protocol에 `getHealth`, `revertChangedFile`, `explainProblem`, `fixProblem`, `healthStatus`, `changeReviewUpdated` 계약을 추가
  - Health panel에서 corePath/pythonPath/serverUrl/workspacePath, runner lifecycle, daemon pid/port, last diagnostic을 확인하고 Settings/Logs/Restart/Refresh 액션을 제공
  - WebView shell을 명시적 grid area로 고정해 health/change/plan panel이 숨겨져도 composer가 항상 하단 row에 남도록 보정
- [x] Extension Host `ChatViewProvider` 분리
  - `src/providers/ChatViewProvider.ts`: WebviewViewProvider, WebView message routing, WebviewMessageQueue, diff open bridge 분리
  - `extension.ts`: activate/deactivate, command registration, custom tool watcher wiring, start/stop/log command 중심으로 축소
- [x] Typed event schema 1차 고도화
  - `KnownRunnerEvent` discriminated union, `RunnerStatusEvent`, `ToolExecution*`, `AgentLoopStatus`, session/asset/custom tool event 타입 정의
  - `asRunnerEvent()`와 `asHostToWebviewMessage()` runtime guard 추가
  - stdio stdout와 daemon SSE event parse 경로에서 invalid event를 guard 후 무시/진단 처리
  - `media/protocol.js`도 host message normalize 시 runner event shape를 1차 검증
- [x] `src/session/SessionManager.ts` 추출
  - local daemon/stdin runner lifecycle, pid/orphan cleanup, status, diagnostics, pending input, interrupt bridge를 `extension.ts` 밖으로 이동
- [x] `RunnerClient` 경계 1차 분리
  - `DaemonRunnerClient`: daemon process spawn, HTTP request, SSE event stream 처리
  - `StdioRunnerClient`: stdio process spawn, stdout/stderr/exit/error attach, stdin write 처리
  - `RunnerStateStore`: `.theseus/runner.json` write/read/remove/orphan cleanup 처리
  - `ProcessUtils`: pid liveness check와 OS별 process tree 종료 처리
- [x] `src/providers/DiffProvider.ts` 추출
  - `theseus-diff` virtual document provider와 changed file metadata parsing 분리
- [x] `src/providers/ChatViewHtml.ts` 추출
  - WebView HTML/CSP/resource URI 생성을 Extension Host message routing에서 분리
- [x] `src/workspace/WorkspaceContext.ts` 추출
  - core root/workspace path, active cursor, `@` file search, custom tool search root 분리
- [x] Feature helper 1차 분리
  - `src/tools/CustomToolManager.ts`: custom tool discovery, validation, permission update, file watcher 생성 분리
  - `src/assets/AssetStore.ts`: pasted image 저장과 generated tool path resolution 분리
  - `src/session/LocalSessionStore.ts`: `.theseus_sessions` 기반 local session summary 분리

### 현재 기술 부채

| 영역 | 현재 상태 | 리스크 |
|------|-----------|--------|
| `extension.ts` | activation/command wiring, selected-code command, start/stop/log command 중심으로 축소 | activation wiring은 단순해졌고 provider 변경 충돌 위험 감소 |
| `src/session/SessionManager.ts` | runner transport와 pid store는 분리됐고, session state/timer/diagnostic orchestration을 담당 | heartbeat/reconnect/cancel 정책 추가 시 상태 전이 회귀 가능 |
| `src/session/*RunnerClient.ts` | daemon/stdin 전송 경계 1차 분리 완료 | reconnect/replay/cancel API 계약은 아직 얇음 |
| `media/main.js` | ES Modules로 전환했고 state/autocomplete/message/plan/custom tools/tool panel/composer/session menu/runner status는 분리 완료. host event switch와 일부 orchestration은 남아 있음 | event handler가 아직 길어 신규 event 추가 시 추적 난이도 증가 |
| HTML 생성 | `ChatViewHtml.ts`로 1차 분리 완료 | 추후 `media/index.html` 또는 template asset로 더 분리 가능 |
| postMessage protocol | `KnownRunnerEvent` union과 runtime guard 1차 추가, WebView protocol normalize도 event shape 검증 | daemon replay/cancel/permission approval 같은 신규 event payload는 추가 세분화 필요 |
| CSS | PLAN panel/composer/custom tools의 좁은 폭 wrapping은 1차 보강됐으나 컴포넌트 경계와 1:1로 대응하지 않음 | UI 모듈화 후 스타일 소유권 불명확 |

### Extension Host 분리안

1차 리팩토링은 behavior 변경 없이 파일 이동 중심으로 진행한다.

```text
vscode-extension/src/
  extension.ts                    # activate/deactivate, command wiring only
  session/SessionManager.ts        # session state, lifecycle orchestration, status
  session/DaemonRunnerClient.ts    # local daemon spawn, HTTP/SSE transport
  session/StdioRunnerClient.ts     # stdio runner spawn, stdout/stdin transport
  session/RunnerStateStore.ts      # .theseus/runner.json lifecycle
  session/ProcessUtils.ts          # pid liveness and process tree cleanup
  session/LocalSessionStore.ts      # .theseus_sessions summary fallback
  providers/ChatViewProvider.ts    # WebViewViewProvider, message routing
  providers/DiffProvider.ts        # theseus-diff virtual document provider
  tools/CustomToolManager.ts       # custom tool discovery, validation, permission update
  workspace/WorkspaceContext.ts    # corePath/workspacePath/active cursor/file search
  assets/AssetStore.ts             # pasted image and .theseus/assets handling
  shared/protocol.ts               # RunnerEvent, WebViewMessage, HostMessage types
  utils/path.ts
  utils/json.ts
```

분리 원칙:

- command id, configuration key, WebView message type은 리팩토링 중 변경하지 않는다.
- `TheseusSessionManager`를 먼저 추출하고, 이후 provider/tool/workspace utility를 분리한다.
- `SessionManager` 뒤의 `RunnerClient` 계층은 1차 구현됐으며, 이후 heartbeat/reconnect/cancel API를 이 경계에 추가한다.

### WebView 분리안

1차는 framework 없이 ES Modules로 분리한다. framework 도입은 WebView API와 protocol이 안정된 뒤 재평가한다.

```text
vscode-extension/media/
  main.js                    # bootstrap only
  state.js                   # local state, persist/restore
  protocol.js                # postMessage wrappers
  markdown.js                # current classic-script markdown helper
  runnerStatus.js            # current classic-script runner lifecycle/diagnostic helper
  components/MessageList.js
  components/CustomTools.js
  components/PlanPanel.js
  components/Autocomplete.js
  components/ToolPanel.js
  components/Composer.js
  components/SessionMenu.js
  components/RunnerStatus.js
  utils/dom.js
  utils/markdown.js
```

분리 원칙:

- DOM id와 CSS class를 안정화하고, 컴포넌트별 render/update 함수를 둔다.
- runner state, selected session, selected mode, plan state를 하나의 state module에서 관리한다.
- `updateSession()` 라벨 같은 표시 정책은 component 내부로 격리한다.
- 현재 `vscode.getState()` 캐시는 유지하되 daemon 전환 후에는 `fullState` snapshot을 우선 source로 사용한다.

### HTML 템플릿화

- `ChatViewProvider`의 HTML 문자열을 별도 `media/index.html` 또는 `src/webview/template.ts`로 분리한다.
- Extension Host는 CSP nonce, `main.js`, `styles.css` URI만 주입한다.
- template 분리 후에는 WebView layout 변경이 session/process 코드 diff와 섞이지 않게 한다.

### Typed Protocol

- Extension Host → WebView:
  - `fullState`
  - `runnerEvent`
  - `sessionState`
  - `diagnostic`
  - `customTools`
  - `activeFileChanged`
  - `transientNotice`
- WebView → Extension Host:
  - `webviewReady`
  - `sendInput`
  - `setMode`
  - `launchSession`
  - `attachSession`
  - `stopSession`
  - `interruptSession`
  - `getFiles`
  - `openDiff`
  - `updateToolPermission`

공통 타입은 `src/shared/protocol.ts`에 정의하고, WebView 번들 또는 JSDoc typedef로 재사용한다. local daemon 전환 시 `RunnerEvent`와 daemon SSE event shape도 이 파일에서 관리한다.

### 리팩토링 순서

1. [x] `SessionManager`와 pid/orphan cleanup을 `src/session/SessionManager.ts`로 추출
2. [x] path/config/cursor/file-search helper를 `workspace/WorkspaceContext.ts`로 추출
3. [x] `DiffProvider` 분리
4. [x] `ChatViewProvider`를 message routing과 HTML/template 공급으로 나누기
5. [x] `shared/protocol.ts` 추가 후 postMessage handler에 타입 가드 적용
6. [x] `SessionManager` 내부를 `RunnerClient` 인터페이스 + `DaemonRunnerClient` / `StdioRunnerClient`로 추가 분리
7. [x] WebView utility helper 1차 분리 (`media/markdown.js`, `media/runnerStatus.js`)
8. [x] `CustomToolManager`, `AssetStore`, local session summary helper 분리
9. [x] `media/main.js`를 ES Modules로 전환하고 state/autocomplete/message/plan/custom tools 1차 분리
10. [x] ToolPanel, Composer, SessionMenu, RunnerStatus 추가 분리
11. [x] Extension Host `ChatViewProvider` message routing을 `src/providers/ChatViewProvider.ts`로 분리
12. [ ] WebView host event switch를 추가 분리
13. [ ] `media/index.html` asset 또는 더 얇은 template builder로 HTML 템플릿 분리
14. [ ] 필요 시 Vite 기반 WebView build 도입 검토

### 검증 기준

- `npm.cmd run compile` 성공
- 기존 VSIX 패키징 파일 수와 resource URI가 정상인지 확인
- Start/Stop/Attach, message send, session menu, tool panel, PLAN panel, diff view, custom tool permission update가 리팩토링 전후 동일하게 동작
- postMessage type 변경 없이 기존 WebView state 복구가 유지
- 리팩토링 단계마다 behavior 변경과 파일 이동을 같은 커밋에 섞지 않음

---

## 추가 개발 방향 — Local Daemon 기반 최종 안정형

> 판단: 방향은 적절하다. Session 63에서 local daemon 1차 구현이 들어갔고, stdio JSON Lines runner는 fallback/debug 경로로 낮아졌다. 다음 단계는 daemon을 제품 기본 경로로 안정화하면서 Extension Host를 client/bridge 역할로 줄이고, 세션·툴·스킬·MCP의 source of truth를 daemon 쪽으로 옮기는 것이다.

### 목표 아키텍처

```text
VSCode Extension
  - WebView UI
  - Extension Host Controller
  - Daemon Client
  - VSCode API Bridge

Theseus Local Daemon
  - QueryEngine runtime
  - SessionManager
  - ToolRegistry
  - SkillRegistry
  - MCP Gateway
  - Run/Event Store
  - ProjectClient(optional)

Optional Remote Server
  - auth / project config / billing / history sync / org policy
```

- Extension Host는 daemon discover/start/stop/restart, WebView 중계, VSCode API 접근, diff view, active file/cursor 수집만 담당한다.
- Local Daemon은 QueryEngine, 세션, 툴, 스킬, MCP, run/event store의 source of truth를 소유한다.
- Remote Server는 선택 사항이며 standalone 모드에서는 없어도 동작한다.
- 기존 stdio runner는 개발/디버그 fallback, CI smoke test, daemon 실패 시 fallback으로 유지한다.

### Runtime Mode

| 모드 | 설명 | 상태 |
|------|------|------|
| `local-daemon` | 로컬 HTTP/SSE daemon 실행 | 현재 우선 실행 경로(1차) |
| `stdio` | 기존 JSON Lines runner | fallback/debug |
| `hybrid` | local daemon + remote server 정책/과금/세션 동기화 | B2B 기본 후보 |
| `remote-only` | 모든 실행을 원격 서버에서 처리 | 장기 옵션 |

추가 설정 후보:

```json
{
  "theseus.runtimeMode": "local-daemon",
  "theseus.autoStartDaemon": true,
  "theseus.keepDaemonAlive": true,
  "theseus.autoOpenDiff": false
}
```

기존 `theseus.corePath`, `theseus.workspacePath`, `theseus.pythonPath`, `theseus.serverUrl`은 유지한다. `runtimeMode`, `corePath`, `workspacePath`, `pythonPath`, `serverUrl` 변경 시 daemon 재시작이 필요하다.

### Local Daemon 계약

daemon 실행 명령 후보:

```bash
python -m theseus_engine.daemon \
  --host 127.0.0.1 \
  --port 0 \
  --workspace "C:/path/to/project" \
  --core-root "C:/path/to/theseus-core-server"
```

daemon은 `<workspace>/.theseus/runner.json`에 `schemaVersion`, `mode: "local-daemon"`, `pid`, `host`, `port`, `token`, `sessionId`, `workspaceHash`, `workspaceCwd`, `coreRoot`, `startedAt`을 기록한다. Extension은 schema/workspace/coreRoot 정합성이 맞는 state만 attach 대상으로 인정한다.

보안 기본값:

- `127.0.0.1` bind만 허용하고 `0.0.0.0` bind는 금지한다.
- 모든 daemon API는 `Authorization: Bearer <runner.json.token>`을 요구한다.
- token은 workspace별 `.theseus/runner.json`에 저장한다.
- daemon scope는 `workspacePath` 안으로 제한한다.

필수 API 1차:

```http
GET  /health
GET  /status
POST /runs
GET  /runs/{runId}/events
POST /runs/{runId}/interrupt
```

Session 63에서 위 1차 API를 구현했고, Session 64에서 `/status` 기반 heartbeat polling, SSE reconnect, run history replay를 1차 완료했다. 남은 작업은 interrupt의 QueryEngine cooperative cancel 연결과 실제 Extension Host 장시간 회귀 검증이다.

2차 API:

```http
GET /sessions
POST /sessions
POST /sessions/{sessionId}/switch
PATCH /sessions/{sessionId}
GET /sessions/{sessionId}/export?format=markdown

GET /tools
PATCH /tools/{toolName}/permission
POST /tools/validate
GET /tools/stats

GET /skills
POST /skills/activate
POST /skills/deactivate
POST /skills/lint
POST /skills/create

GET /mcp/servers
POST /mcp/servers
POST /mcp/servers/{id}/connect
POST /mcp/servers/{id}/disconnect
GET /mcp/tools
```

### Extension 전환 계획

- WebView 초기화는 `webviewReady` 단일 handshake로 정리하고 Extension은 `fullState` snapshot을 내려준다.
- WebView state는 표시 캐시로 제한하고, 실제 runner/session/run 상태의 source of truth는 daemon으로 둔다.
- 입력 전송은 WebView → Extension `sendInput` → daemon `POST /runs` → `GET /runs/{runId}/events` SSE 순서로 처리한다.
- Extension 시작 또는 WebView ready 시 `.theseus/runner.json`을 읽고 `/health` 성공이면 attach한다.
- `/health` 실패 시 pid tree를 정리하고 `runner.json`을 삭제한 뒤 `autoStartDaemon=true`이면 새 daemon을 시작한다.
- 파일 변경 diff는 daemon event의 `metadata.changedFile`을 받아 Extension이 VSCode diff view를 여는 방식으로 유지한다.

### Remote Session Sync

> 판단: 이 기능도 넣는 편이 맞다. 단, remote server가 로컬 파일 작업을 직접 실행하면 안 된다. 서버는 세션 목록/히스토리/정책/과금의 source가 될 수 있고, 실제 file operation과 tool execution은 항상 Local Daemon의 현재 workspace scope 안에서 수행한다.

Provider 구조:

```text
LocalSessionProvider
  - .theseus/sessions/*
  - offline standalone 기본값

RemoteSessionProvider
  - 백엔드 서버의 사용자 계정 세션
  - 로그인 필요
  - 여러 PC/워크스페이스 간 세션 조회/동기화

HybridSessionProvider
  - remote session 목록을 불러오고 선택한 세션을 local daemon에 mirror
  - 새 이벤트는 local append 후 sync queue로 remote 업로드
```

추가 백엔드 API 후보:

```http
POST /api/auth/extension-token
GET  /api/agent/me
GET  /api/agent/sessions?workspaceHash=...&projectId=...
GET  /api/agent/sessions/{sessionId}
POST /api/agent/sessions
PATCH /api/agent/sessions/{sessionId}
POST /api/agent/sessions/{sessionId}/events
POST /api/agent/sessions/{sessionId}/sync
```

저장 정책:

- access/refresh token은 VSCode `SecretStorage`에 저장한다.
- remote session cache는 `.theseus/sessions/remote/`에 저장한다.
- sync queue는 `.theseus/sync/queue.jsonl`에 append-only event log로 저장한다.
- remote server에는 기본적으로 전체 파일 내용, 민감한 환경변수, 로컬 절대경로 전체, secret이 포함될 수 있는 tool input을 저장하지 않는다.
- remote에는 user/assistant message, tool name/status, changed file relative path, token usage, plan state, skill metadata를 저장한다.

동기화 정책:

- 이벤트는 `message.created`, `assistant.delta.committed`, `tool.started`, `tool.completed`, `plan.drafted`, `plan.approved`, `plan.rejected`, `file.changed`, `skill.activated`, `mode.changed` 같은 append-only 단위로 저장한다.
- remote 연결이 끊겨도 local append는 계속하고, 연결 복구 후 sync queue를 순차 업로드한다.
- 같은 remote session을 여러 기기에서 열면 message/event는 append-only, title/mode metadata는 last-write-wins로 시작한다.
- remote session의 workspaceHash가 현재 workspace와 다르면 history 조회는 허용하되 file operation은 현재 workspace에서 실행된다는 경고를 표시한다.

### 단계별 구현 순서

1. **Phase A — Remote session read-only**
   - `SecretStorage` 기반 로그인 토큰 저장
   - `GET /api/agent/me`, `GET /api/agent/sessions`
   - WebView session dropdown에 Remote 섹션 추가
   - remote session 선택 시 history 표시
2. **Phase B — Local daemon MVP ✅ 1차 완료**
   - `theseus_engine.daemon` 모듈 추가 완료
   - `/health`, `/status`, `/runs`, `/runs/{id}/events`, `/runs/{id}/interrupt` 구현 완료
   - Extension에 daemon attach/start/SSE 수신 경로 추가 완료
   - `runtimeMode=local-daemon` 상태 노출 및 stdio fallback 유지
3. **Phase C — Local mirror**
   - `GET /api/agent/sessions/{id}`
   - `.theseus/sessions/remote/{id}.json` 저장
   - remote session을 active local session으로 전환
   - 이후 새 메시지는 local에 먼저 append
4. **Phase D — 양방향 sync**
   - `POST /api/agent/sessions/{id}/events`
   - `.theseus/sync/queue.jsonl`
   - 실패 재시도, sync 상태 UI, token usage sync
5. **Phase E — Runtime 확장**
   - `/sessions`, `/tools`, `/skills`, `/mcp` API를 daemon으로 승격
   - Skill.md registry, MCP Gateway, PLAN current step, AgentHandoffEvent를 같은 daemon runtime 위에 통합

### 수용 기준

- WebView가 재생성되어도 `fullState`로 세션, history, plan, tools, skills, active file 상태가 복구된다.
- Extension Host reload 후 `.theseus/runner.json`을 읽어 live daemon에 재접속한다.
- daemon이 죽어 있거나 workspace가 다르면 재접속하지 않고 cleanup/restart 또는 경고를 표시한다.
- 5분 이상 실행되는 tool task 중 WebView를 숨겨도 SSE reconnect 후 run status와 이후 event를 확인할 수 있다.
- daemon은 `127.0.0.1`에만 bind하고 모든 API에 bearer token을 요구한다.
- `serverUrl`이 비어 있으면 standalone local-first로 동작한다.
- remote session을 불러와도 실제 파일 작업은 Local Daemon의 현재 workspace scope 안에서만 실행된다.

---

## Python ↔ Extension 통신 방식

### Option A: stdio (fallback)

```typescript
const proc = spawn("python", ["-m", "theseus_engine.cli_runner", "--json-mode"]);
proc.stdout.on("data", (chunk) => {
    const lines = chunk.toString().split("\n");
    lines.forEach(line => {
        if (!line.trim()) return;
        const event = JSON.parse(line);
        panel.webview.postMessage(event);
    });
});
```

```python
# cli_runner --json-mode
async for event in engine.submit_message(user_input):
    print(json.dumps({"type": type(event).__name__, **asdict(event)}), flush=True)
```

stdio는 MVP, 개발 디버그, CI smoke test, daemon 실패 시 fallback으로 유지한다. Extension의 최종 기본 실행 경로로는 사용하지 않는다.

### Option B: 로컬 HTTP/SSE daemon (최종 기본 경로)

```
Extension → POST localhost:PORT/runs
Extension ← GET  localhost:PORT/runs/{runId}/events (SSE)
```

FastAPI 또는 aiohttp 기반 local daemon으로 구성한다. `THESEUS_SERVER_URL`이 있으면 ProjectClient를 통해 remote auth, policy, billing, history sync를 붙이고, 없으면 standalone으로 동작한다.

---

## 백엔드가 추가로 구현해야 하는 것

Extension이 호출하는 API (`project_client.py`에 주소 확정):

```
GET  /api/agent/project-config          → user_level, tool_permissions 반환
POST /api/agent/sessions/{id}/history   → 대화 이력 저장
POST /internal/billing/usage            → 토큰 사용량 집계
POST /api/auth/extension-token          → Extension용 JWT 발급
```

Extension 없이도 웹 프론트에서 독립적으로 구현 가능하다.

## 웹 프론트엔드가 추가로 구현해야 하는 것

```
프로젝트 설정 관리 페이지   → tool_permissions, custom_tools 편집
Extension 토큰 발급 페이지  → JWT 복사 → .env에 붙여넣기
세션 히스토리 뷰어 (선택)   → Extension에서 작업한 이력 웹에서 조회
```

---

## 배포 시나리오

| 시나리오 | Extension | 백엔드 | 비고 |
|---------|-----------|--------|------|
| 개인 사용 | ✅ | ❌ | standalone, URL 설정 불필요 |
| 팀 도입 | ✅ | ✅ | `THESEUS_SERVER_URL` 설정 후 즉시 연결 |
| 엔터프라이즈 | ✅ | ✅ | 사내 서버 URL 배포 |

---

## TUI와의 관계

TUI(`tui_main.py`)는 유지한다. 고도화 없이 현상 유지.

| | TUI | Extension |
|---|---|---|
| 용도 | 개발/디버깅, 서버 환경, SSH | 일반 사용자 프로덕트 |
| 진입장벽 | 터미널 필요 | VSCode만 있으면 됨 |
| 커스텀 툴 UX | 텍스트 알림 | 파일 감지 + 시각적 피드백 |
| PLAN 시각화 | 체크리스트 패널 | Diff + 체크리스트 |

---

## 현재 상태 (2026-05-12)

| Phase | 상태 | 비고 |
|-------|------|------|
| Phase 1 기반 구조 | ✅ 완료 | 로컬 모델 연결 검증 완료 |
| Phase 2 UX 기반 | ✅ 완료 | custom_tools 파일 감지 포함 전 항목 완료 |
| Phase 3 편집기 연동 | ✅ 완료 | 활성 파일 표시·우클릭 Ask·Diff 뷰·PLAN 체크리스트·커서 위치 컨텍스트 완료 |
| Phase 4 커스텀 툴 UX | ✅ 완료 | 저장 감지 검증, 권한 인라인 수정, 실행 통계 표시 완료 |
| Phase 5 서버 연동 | 🔶 부분 | serverUrl 설정 완료, JWT 연동 미구현 |
| Phase 6 UX 고도화 | 🔶 부분 | 로컬 세션 provider/dropdown/export, 이미지 저장, PLAN 승인/거부, JSON 트리, 설정 재시작 배너, loop-status, runner 상태 재동기화·진단 표시 완료 |
| Phase 7 Agent 역량 확장 | 📝 계획 | MCP 서버 등록/ToolRegistry 브릿지, `SKILL.md` 기반 스킬, Memory/Knowledge 관리 필요 |
| Phase 8 Extension Runtime 안정화 | 🔶 부분 | `TheseusSessionManager`, session/channel protocol, startup diagnostics, `RunnerStatus.lastDiagnostic`, MessageQueue, lifecycle ring buffer, stdio orphan cleanup, local daemon heartbeat/reconnect/replay 1차 완료. 실제 Extension Host e2e, 코드 모듈화, serializer/Python cancel은 미구현 |
| **코드 리팩토링/모듈화** | 🔶 진행 중 | `extension.ts` 약 123라인, `ChatViewProvider.ts` 약 305라인, `SessionManager.ts` 약 727라인, `main.js` 약 880라인. session/protocol/diff/workspace/template/provider/runner client/WebView utility/feature helper/WebView ES Modules/typed event schema/WebView component 1차 분리 완료, WebView host event switch 모듈화 필요 |
| **크리티컬 버그 수정** | ✅ 완료 | TDZ 버그·버튼 불작동·화면 사라짐 수정 후 재설치 (Session 52) |
| **모드 전환 UX 정리** | ✅ 완료 | `/agent` `/ask` `/plan` 사용자 입력 경로 제거, 하단 모드 선택 + 내부 `setMode` 경로로 통일 (Session 56) |
| **AuditLLM 안정화** | 🔶 부분 | JSON 포맷 문자열, list content 응답, native stream fallback 수정. 실제 모델별 회귀 검증 필요 (Session 58) |
| **Agent 루프 가시성** | 🔶 부분 | Core `AgentLoopStatus` + WebView `loop-status` 1차 완료. stale 감지/interrupt는 미구현 (Session 58) |
| **Runner 재연결 안정성** | 🔶 부분 | 같은 Extension Host 내 reattach/revive, stdio orphan cleanup, local daemon attach/start, heartbeat 기반 stale 판정, SSE reconnect, run event replay 1차 완료. 실제 VSCode Extension Host에서 장시간 tool run 회귀 검증 필요 |

## 해결된 이슈 — AuditLLM fail-closed 오탐

파일 수정 툴(`write_file`, `edit_file`) 실행 전 AuditLLM이 응답을 문자열로만 가정해 list content block 응답에서 `expected string or bytes-like object, got 'list'` 예외가 발생했다. fail-closed 정책 때문에 안전한 파일 생성/수정도 차단될 수 있었다.

- **해결**: Audit 프롬프트의 예시 JSON 중괄호를 escape 처리해 `.format(arguments=...)` 예외를 제거했다.
- **해결**: Audit 응답을 문자열, list, `{text}`, `{content}`, `ConversationMessage`, `TextBlock`에서 텍스트로 정규화한다.
- **해결**: `generate()`가 없는 Theseus native client에서도 `stream_message()`로 AuditLLM을 호출할 수 있게 했다.
- **남음**: 실제 Gemini / OpenAI-compatible / Anthropic backend별 Audit 응답 샘플 회귀 검증이 필요하다.
- **남음**: fail-closed 정책은 유지하되, “감사 모델 응답 형식 문제”와 “실제 보안 차단”을 UI에서 구분해 보여줘야 한다.

## 해결된 이슈 — 에이전트 루프 진행 상태 불명확

기존 WebView는 `ToolExecutionStarted` / `ToolExecutionCompleted` 패널은 있었지만, 모델이 툴 호출을 선택했는지, 루프가 정상 종료됐는지, 빈 assistant 메시지나 max turns로 끊겼는지 사용자가 즉시 판단하기 어려웠다.

- **해결**: Core가 `AgentLoopStatus` 이벤트를 발행해 모델 턴, 툴 개수, 툴 시작/완료, 루프 완료/오류를 구조적으로 전달한다.
- **해결**: WebView 툴바의 `loop-status` pill이 `thinking`, `running tools`, `tool done`, `loop error` 상태를 표시한다.
- **해결**: 툴 실행 항목은 완료 후에도 열린 상태를 유지해 호출 여부와 결과를 바로 확인할 수 있다.
- **남음**: 일정 시간 이벤트가 없을 때 stale 상태로 표시하고, 재시도/중단/로그 열기 액션을 제공해야 한다.
- **남음**: 여러 툴 병렬 실행 시 현재 남은 툴 수와 실패 툴 요약을 더 명확히 보여주는 UI가 필요하다.

## 남은 작업 — 시작과 재시작 안정성

WebView가 숨김/재생성되는 경우는 `RunnerStatus.processRunning`, `lifecycle`, `attachSession` 재동기화로 보완했다. Start 버튼을 다시 눌러도 Extension Host 안에 기존 runner가 살아 있으면 새 프로세스를 만들지 않고 상태를 재전송하거나, attach 가능한 stale 상태를 `ready`/`waiting_input`으로 revive한다. Session 63부터는 live local daemon이 있으면 `/health` 확인 후 attach하고, 없거나 실패하면 cleanup 후 새 daemon을 시작한다. stdio pipe를 잃은 기존 runner는 fallback 경로에서 orphan cleanup 대상으로만 처리한다.

- [x] WebView 숨김/재생성/탭 복귀 시 runner 상태 재요청
- [x] 기존 process가 살아 있을 때 Start 버튼은 새 spawn 대신 상태 재전송 또는 attach 요청
- [x] ready 전 starting 상태를 UI에 표시하고, 입력은 `RunnerReady` 이후 자동 전송
- [x] `RunnerStatus.lastDiagnostic`와 실행 경로 metadata로 Start 실패 원인 보존
- [x] WebView의 runner 상태 갱신을 `runnerState`/`applyRunnerStatus()`로 단일화
- [x] `proc && lastReadyEvent`가 있는 stale/starting/error 상태는 Start 또는 상태 재조회 시 기존 runner로 revive
- [x] `lastReadyEvent`가 없는 stale/error 상태의 기존 process는 Start 요청 시 자동 재시작
- [x] stale/processRunning 상태에서는 pending 입력을 유지하고 attach 후 자동 전송
- [x] stopped 또는 process가 없는 error 상태에서는 pending 입력 자동 전송 중단 및 진단 안내 표시
- [x] non-JSON stdout 시작 잡음은 `json_parse_error` 진단으로 분리해 살아 있는 process를 즉시 error 처리하지 않음
- [x] Extension Host 재시작/리로드 후 orphan Python runner 정리
  - stdio pipe를 잃은 runner는 `.theseus/runner.json` pid 파일로 감지하고 cleanup 후 새 runner 시작
- [x] local daemon attach/start 1차
  - `.theseus/runner.json`의 host/port/token으로 `/health` 확인 후 attach
  - live daemon이 없으면 새 daemon 시작, 실패 시 stdio fallback

- [x] 마지막 runner 시작 metadata 저장 1차
  - coreRoot, workspaceCwd, pythonPath, serverUrl, sessionId를 Extension workspace state에 저장
- [ ] 마지막 runner 설정 저장 고도화
  - session, mode, runtimeMode, daemon schema version까지 포함해 재시작/복구 UX에서 사용할 수 있도록 확장
- [x] stdio orphan 자동 정리 정책 1차
  - 사용자가 명시적으로 Stop한 경우는 pid 파일을 삭제해 다음 Start에서 자동 orphan cleanup 대상이 되지 않게 함
  - Extension Host 재시작 후 남은 Python runner는 재부착 불가 대상으로 보고 새 Start 전에 정리
- [x] local daemon 기반 재접속 정책 1차
  - health/status check 이후 SSE reconnect, run event replay, 실패 시 stale/restart UX 제공
- [x] runner heartbeat 추가
  - daemon `/status` polling으로 Python runtime 생존 상태 확인
- [ ] 실제 VSCode Extension Host 장시간 run 회귀 검증
  - 5분 이상 실행되는 tool task 중 WebView hide/show, Extension Host reload, SSE reconnect/replay 동작 확인
- [x] startup 비정상 종료 원인 분류 1차
  - Python spawn 실패, import 실패, ready timeout, 사용자 Stop을 서로 다른 UI 상태로 표시
- [ ] 런타임 오류 원인 분류 고도화
  - LLM API 실패, max turns, AuditLLM 차단, tool failure를 서로 다른 UI 상태로 표시
- [ ] 재시작 UX 개선
  - Restart 버튼은 기존 프로세스 정리 → 새 프로세스 시작 → RunnerReady timeout 감시 순서로 동작
- [ ] Output Channel 바로가기
  - runner error/stale 상태에서 Theseus Output Channel 열기 액션 제공

## 남은 작업 — VSCode Extension 고도화 정리

1. **코드 구조 개선 최우선**
   - 완료: `SessionManager`, `DaemonRunnerClient`, `StdioRunnerClient`, `RunnerStateStore`, `DiffProvider`, `ChatViewProvider`, `WorkspaceContext`, WebView HTML template, shared protocol, WebView utility helper, WebView ES Modules 일부, ToolPanel/Composer/SessionMenu/RunnerStatus, `CustomToolManager`, `AssetStore`, `LocalSessionStore` 1차 분리
   - 다음: WebView host event switch를 추가 분리하거나 daemon 안정화로 이동
2. **Typed protocol**
   - 완료: Extension Host ↔ WebView top-level message 타입, `KnownRunnerEvent` discriminated union, `asRunnerEvent()`/`asHostToWebviewMessage()` runtime guard 1차 정의
   - 완료: daemon SSE event와 기존 stdio JSON event 진입점에 guard 적용
   - 다음: reconnect/replay/cancel/permission approval 신규 event payload를 추가 세분화
   - 다음: legacy `start/send/stop/getRunnerStatus` 메시지는 호환 계층으로만 유지
3. **Runtime 안정화**
   - 완료: daemon `/status` heartbeat, stale 판정, SSE reconnect, run history replay 구현
   - 완료: daemon `runner.json`에 schema version/sessionId/workspace hash를 추가하고 validation 실패 시 cleanup/restart
   - stdio fallback도 compile/smoke test 대상으로 계속 유지
   - 다음: 실제 VSCode Extension Host에서 장시간 run hide/show, reload, reconnect 회귀 검증
4. **실행 제어와 권한 UX**
   - `POST /runs/{runId}/interrupt`를 QueryEngine cooperative cancel까지 연결
   - Stop generation, tool 실행 중단, user stop, daemon crash를 서로 다른 UI 상태로 표시
   - destructive tool permission request를 WebView 인라인 승인 UX로 연결
5. **제품화 확장**
   - 서버 로그인/JWT/`THESEUS_PROJECT_ID`/session token 저장 정책 확정
   - standalone/server 연결 상태와 sync 상태 표시
   - MCP 서버 등록/상태/ToolRegistry bridge, `SKILL.md` discovery/activation/authoring, Knowledge/Memory 관리 UI를 daemon runtime 위에 통합

## 해결된 이슈 — 모드 전환 slash 명령 사용자 노출

입력창 하단의 모드 선택 UI가 공식 모드 전환 경로가 되었기 때문에, `/agent`, `/ask`, `/plan`, `/coordinator`를 사용자-facing slash 명령에서 제거했다.

- **해결**: `/` 자동완성에는 세션/툴/통계/검증/도움말 같은 유틸리티 명령만 표시한다.
- **해결**: 사용자가 직접 `/plan` 등 모드 slash를 입력해도 사용자 메시지/assistant 대기 UI를 만들지 않고 system 안내만 표시한다.
- **해결**: Extension Host에 `setMode` 메시지 타입을 추가해 내부 모드 전환을 raw slash 입력과 분리했다.
- **해결**: JSON Lines runner는 `{ "type": "setMode", "mode": "..." }` 내부 명령만 실제 모드 전환으로 처리한다.
- **해결**: runner stdin에 직접 `/agent`, `/ask`, `/plan`, `/coordinator`가 들어와도 모드 전환 없이 안내 메시지만 반환한다.

## 해결된 이슈 — `@` 경로 자동완성 일부 누락

이전 구현은 `main.js`가 커서 앞의 `/[/@]\S*$/` 토큰을 감지하고, Extension Host의 `getFiles` 핸들러가 `vscode.workspace.findFiles('**/*', '**/node_modules/**', 100)`로 받은 결과를 필터링했다.

- **해결**: `getFiles`를 검색어 기반 glob으로 변경해 VSCode Host 단계에서 후보를 먼저 좁힌다.
- **해결**: `theseus.workspacePath`를 파일 검색 root로 사용하고, 결과를 에이전트 cwd 기준 상대경로로 반환한다.
- **해결**: 공백 포함 경로는 `@"path with spaces"` 형태로 삽입한다.
- **해결**: `.git`, `out`, `dist`, `build`, `.next`, `target`, 가상환경, `__pycache__` 등을 검색에서 제외한다.

남은 보완 후보는 매우 큰 monorepo에서의 지속 인덱싱/cache, 최근 열린 파일 우선순위, fuzzy matching이다.

## 다음 우선순위

1. **실행 제어 완성**: cooperative interrupt/cancel, 권한 승인 UX, 에러 원인 분류, Output Channel 액션 연결
2. **실제 Extension Host 회귀 검증**: local daemon long-running run, hide/show, reload, SSE reconnect/replay, stdio fallback smoke 확인
3. **WebView event switch 마무리**: `main.js`의 host event switch를 별도 dispatcher로 이동
4. **제품화 확장**: 서버 인증/sync, MCP bridge, Skill/Knowledge/Memory 관리 UI를 daemon runtime 위에 통합
5. **회귀 검증/패키징**: VSIX resource URI, WebView module import, Start/Stop/Attach, session/tool/PLAN/diff/custom tool permission e2e 확인
