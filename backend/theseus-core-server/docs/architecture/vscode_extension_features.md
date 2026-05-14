# Theseus VSCode Extension 기능 명세서

> 최종 반영 기준: Session 118 (2026-05-14)

본 문서는 Theseus AI 에이전트와 연동되는 **VSCode Extension**의 주요 기능과 UX, 구현 아키텍처에 대한 상세 설명입니다. Theseus 엔진과의 매끄러운 통신을 바탕으로 VSCode 환경에 가장 최적화된 형태의 "Agentic AI Coding Assistant" 경험을 제공합니다.

---

## 1. 아키텍처 개요 (Architecture Overview)

Theseus 익스텐션은 확장이 용이하고 유지보수가 가능하도록 책임별로 모듈화된 아키텍처를 가집니다.

* **`src/providers/`**: VSCode Sidebar Webview 생명주기 및 메시지 통신을 관리합니다. (`ChatViewProvider.ts`)
* **`src/workspace/`**: 사용자의 프로젝트 트리, 진단(Linter) 내역, 현재 활성화된 파일 및 커서 컨텍스트를 파악합니다.
* **`src/inline/`**: 에디터 내에서 `Ctrl+I` 입력 시 동작하는 인라인 편집(Inline Edit) 기능을 제공합니다.
* **`src/composer/`**: 좁은 사이드바 영역을 넘어서 메인 화면에서 넓게 다중 파일 변경 내역을 확인하는 패널을 관리합니다.
* **`media/`**: 프론트엔드 종속성(React, Vue 등) 없이 바닐라 자바스크립트(Vanilla JS)와 CSS로 최적화된 렌더링 계층을 구현했습니다. 이벤트 파이프라인을 `dispatcher.js`로 추상화하여 상태 전이와 DOM 업데이트를 관리합니다.

---

## 2. 주요 기능 (Core Features)

### 2.1. Agentic Loop 가시성 (투명성과 성능 최적화)
복잡한 작업을 스스로 해결하는 에이전트의 불투명성을 극복하기 위한 UX가 반영되었습니다.

* **Activity Log (툴 스택 아코디언)**: 에이전트가 `read_file`, `run_command` 등 툴을 호출하는 즉시 아코디언 형태로 진행 상황을 노출합니다. 작업 중(`running`), 완료(`done`), 실패(`failed`) 상태에 따라 아이콘이 동적으로 전환되며 진행 과정을 투명하게 보여줍니다. **(Session 118 보강)** 실제 툴 호출이 1개 이상 있을 때만 아코디언을 노출하고, 활동 그룹의 sticky 고정을 제거해 스트리밍 도중 콘텐츠가 가려지는 문제를 해결했습니다. 활동 목록은 `max-height: 180px` 내부 스크롤로 처리합니다.
* **시각적 대기 모드 (Shimmer & Spin)**: 응답 대기 시 `.typing-indicator`에 빛 번짐(Shimmer) 애니메이션을, 툴 실행 중에는 회전하는 톱니바퀴 아이콘을 제공하여 시스템 정지 여부에 대한 불안감을 해소합니다.
* **초저지연 렌더링 최적화**: 쏟아지는 SSE(Server-Sent Events) 텍스트 청크를 처리할 때, 브라우저의 `requestAnimationFrame` 스로틀링과 `persistState`의 500ms 디바운싱을 적용해 VSCode 환경에서의 UI 블로킹과 I/O 병목을 원천 제거했습니다. (Phase 4 도입 사항)
* **턴 컨테이너 안정성 (Session 118)**: `.turn` 컨테이너를 grid named-area → flex column으로 전환해 동일 grid-area에 여러 메시지가 겹쳐 글자가 중첩 렌더링되던 버그를 해결했습니다. DOM 순서(user → activity → assistant)가 그대로 시각 순서로 매핑됩니다.

### 2.2. Human-in-the-Loop 및 권한 제어 (Plan & Security)
사용자가 코드를 직접 통제할 수 있도록 강력한 안전 장치를 도입했습니다.

* **Plan Mode**: 복잡한 파일 변경이나 다단계 작업 실행 전, 에이전트가 "Draft Implementation Plan"을 생성하여 사이드바 상단에 노출합니다. 사용자가 승인(`Accept`)해야만 후속 작업(Execute)이 진행됩니다.
* **Plan MD 본문 렌더링 (Session 118)**: Plan 패널 본문이 서버의 `formatPlanMarkdown`과 동일한 로직으로 마크다운 렌더링됩니다. `goal/title`은 heading, tasks는 번호 매긴 굵은 항목 + 상태 이탤릭 + 들여쓴 메타, 기타 plan 필드는 재귀적 key/value로 표현됩니다. JSON 보기는 기본 숨김 토글, [Open MD]는 외부 에디터에서 전체 문서를 여는 용도로 분리.
* **엔진 위임형 Plan Review (Session 118)**: 익스텐션이 한국어/영어 키워드로 사용자 의도를 분류하지 않습니다. 명시적 승인/거부는 PlanPanel의 [Approve]/[Reject] 버튼 또는 `/plan approve`·`/plan reject` 슬래시 명령으로만 트리거하고, 일반 텍스트는 그대로 엔진에 전달해 해석을 엔진/플랜 가드에 위임합니다.
* **모드 전환 시 Plan 안전 처리 (Session 118)**: plan → 다른 모드 전환 시 `wait/drafting` 단계 plan만 자동 cancel하고, `executing/verifying` 단계는 사용자 경고만 표시하고 plan을 유지해 실행 중 race를 방지합니다.
* **위험 툴 실행 통제 (Permission Request)**: 셸 커맨드 실행 등 파괴적이거나 위험할 수 있는 툴 콜링 발생 시 팝업을 통해 사용자에게 권한을 요청합니다. 거절(Reject)할 경우 에러를 반환하여 에이전트가 우회 수단(대안)을 스스로 모색하도록 유도합니다.
* **Permission Provider 친화적 메시지 (Session 118)**: `updateToolPermission` 메시지에 `toolName`, `session` 필드가 동반 전달됩니다. 백엔드가 `PermissionProvider` 추상화를 도입하면 의미적 식별자 기반으로 처리하고, 미도입 환경에서는 기존 `metadataPath` fallback으로 동작합니다.

### 2.3. 다차원 컨텍스트 멘션 (@ Mentions)
에이전트에게 IDE 내의 구체적인 상황을 쉽게 주입할 수 있도록 시스템 멘션 문법을 지원합니다. (`WorkspaceContext.ts` 기반)

* **`@problems`**: 현재 열려있는 워크스페이스의 에러 및 경고 내역(Linter/Compiler diagnostics)을 텍스트로 추출하여 프롬프트에 주입합니다.
* **`@folder` / `@file`**: 특정 디렉토리나 파일의 구조를 멘션으로 직접 참조할 수 있습니다.
* 모델은 이러한 컨텍스트 토큰을 사전에 해석(`resolveContextMentions`)하여, 사용자가 일일이 코드를 복붙하지 않아도 신속한 에러 분석이 가능해집니다.

### 2.4. 인라인 에디터 (Inline Edit)
채팅창을 벗어나 코드 에디터 상에서 직접 상호작용합니다.

* **단축키 연동 (`Ctrl+I`)**: 특정 코드 블록을 드래그하거나 빈 줄에서 단축키를 눌러 바로 프롬프트 입력창을 띄웁니다.
* **스트리밍 치환**: 사용자가 수정을 요청하면, 에이전트의 답변이 코드에디터 버퍼에 스트리밍되며 실시간으로 텍스트를 덮어쓰고 배경을 하이라이팅 처리합니다.

### 2.5. 다중 파일 컴포저 (Composer Panel)
여러 파일이 얽힌 대규모 리팩토링 시 사이드바의 좁은 화면으로는 변경 내역(Diff)을 파악하기 힘든 문제를 해결합니다.

* **독립된 전면 WebviewPanel**: 에이전트의 툴 콜에 의해 파일들이 변경되면, `ComposerPanel`이 활성화되어 메인 뷰에서 어떤 파일들이 어떻게 변경되었는지 포괄적인 트리를 제공합니다.
* **Accept All / Reject All**: 모든 변경 사항을 한눈에 리뷰하고 일괄 수락하거나 거부할 수 있는 강력한 코드 검토 인터페이스를 제공합니다.

### 2.6. 워크트리 빠른 선택 (Session 118)
사용자가 settings.json을 직접 편집하지 않고도 작업 폴더를 빠르게 전환할 수 있는 인터페이스를 제공합니다.

* **툴바 📁 버튼**: 챗 상단 메타 영역의 폴더 아이콘 버튼을 클릭하면 QuickPick이 열려 VSCode 작업 폴더 목록 + Browse(OS 다이얼로그) + Clear 옵션 중 선택할 수 있습니다. 현재 활성 폴더는 `(current)`로 표시됩니다.
* **`theseus.selectWorktree` 명령**: Command Palette에서도 동일한 picker를 호출할 수 있습니다.
* **자동 등록 강화**: `getWorkspaceName` 응답이 setting(`theseus.workspacePath`)을 반영한 실제 활성 경로를 반환하도록 정렬되어 toolbar 라벨이 정확히 동기화됩니다.
* **재시작 안내**: 워크트리 변경 시 runner가 실행 중이면 "Restart Runner / Later" 경고 모달이 표시되어 옛 경로로 분석이 계속되는 혼란을 방지합니다.

### 2.7. 동적 Tool 가시성 및 Custom Tools 패널 (Session 118)
엔진의 dynamic tool retrieval(prompt별 top-k tool 노출) 방향과 익스텐션의 정적 목록 노출이 어긋나지 않도록 표시 계층을 정렬했습니다.

* **활성 tool 마커**: 엔진 이벤트의 `metadata.active_tools` / `active_tool_names` / `retrieved_tools`를 자동 추출해 이번 턴에 모델에 노출된 tool에 `✓` 마커와 좌측 강조 테두리를 부여합니다. 비활성 tool은 옅게 표시됩니다.
* **카운트 일관성**: 활성 tool 중 정적 패널에 없는 항목(core/built-in 가능성)은 `(이 패널 밖 N개 포함)`으로 별도 카운트되어 사용자가 차이를 즉시 이해할 수 있습니다.
* **Disclaimer**: 활성 정보가 없을 때 패널은 "전체 등록 목록 (응답마다 모델에 노출되는 tool은 다를 수 있음)" 안내를 표시합니다.

### 2.8. 세션·모드·히스토리 안정화 (Session 118)
runner와 익스텐션 간 상태 동기화의 race를 방지하는 보호 장치를 추가했습니다.

* **Mode dedupe**: `SessionManager`가 `lastSentMode`를 추적해 같은 mode 재전송 시 runner에 `setMode` 명령을 보내지 않습니다. `send`, `setMode`, `flushPendingInput` 세 경로 모두 적용. 결과적으로 runner의 "✅ Agent 모드로 전환됐습니다." 알림 스팸이 사라집니다.
* **실패 시 rollback**: daemon `sendDaemon` 실패 시 `lastSentMode`를 이전 값으로 복원, `setState('error')` 또는 `stop()` 시 `lastSentMode`를 비워 다음 send에서 mode를 재동기화합니다.
* **세션 전환 (busy 허용)**: 응답 생성 중에도 사용자가 다른 세션을 선택하면 `SessionController`가 자동으로 인터럽트하고 `sessionManager.onEvent()`로 ready transition을 감지해 라우팅합니다(5초 안전망 fallback). 매직 타임아웃 없는 이벤트 기반 대기.
* **History 보수적 재생**: `replayHistorySnapshot`은 로컬 `savedHistory`가 비어 있을 때만 전체 재생, 그 외에는 상태 이벤트만 재생합니다. visibility change 등 정상 시나리오에서 대화 내역이 wipe되던 회귀를 해결.
* **/clear 후 welcome 복원**: 채팅을 비우면 추천 프롬프트가 포함된 welcome 화면이 다시 노출되어 첫 사용 인상이 일관됩니다.

---

## 3. 내부 상태 관리와 프로토콜

* **`src/shared/protocol.ts`**: Webview(프론트)와 Extension(호스트) 간 메시지 통신을 위한 엄격한 타입 인터페이스 모음. `sendMessage`와 `postMessage` 사이의 모든 Payload 명세가 들어 있습니다.
* **`media/state.js` & `media/main.js`**: VSCode가 제공하는 `acquireVsCodeApi().setState`를 이용해 채팅 이력, 열려있는 세션, 사용자 커스텀 툴 접힘 상태 등을 디스크에 영속적으로 보존합니다. 창을 껐다 켜도 컨텍스트가 유지됩니다.

---

## 4. 로드맵 (Next Steps)

* **Phase 5**: 특정 프로젝트 워크스페이스와 연동되는 **RBAC(역할 기반 접근 제어)** 및 **다이내믹 툴 필터링** 도입.
* 텐서(Tensor) 등 무거운 바이너리 처리나 터미널 결과물에 대한 `@terminal` 로그 주입 기능 강화.
