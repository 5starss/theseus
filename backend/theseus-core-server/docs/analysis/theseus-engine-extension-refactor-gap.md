# Theseus Engine 리팩토링과 Extension 런타임 차이 기록

작성일: 2026-05-14

## 목적

`theseus_engine` 공통 리팩토링 중 VSCode Extension(local daemon / stdio)과
Core Server 런타임의 기능 차이가 확인되면 코드로 억지 보정하지 않고 이
문서에 남긴다. Extension은 같은 engine을 쓰지만, 서버 builder는 Spring/API,
Kafka, 프로젝트 권한, Remote Workspace 같은 서버 오케스트레이션을 추가로
적용한다.

## 현재 확인된 차이

| 위치 | Extension / local runtime 현재 동작 | Core Server refactor 후 동작 | 영향도 | 코드 보정 여부 | 후속 필요 작업 |
|---|---|---|---|---|---|
| Tool visibility | `theseus_engine.core.tool_visibility` 공통 정책을 사용한다. PLAN DRAFTING/WAIT_FOR_REVIEW는 읽기/분석 도구 중심, PLAN EXECUTING에서 `create_tool`이 노출된다. | 동일한 공통 정책을 사용하되 서버는 Remote Workspace와 plan binding guard를 추가한다. | 낮음 | 보정함 | Extension에서 PLAN DRAFTING 중 쓰기 도구가 필요하다는 UX 요구가 생기면 별도 정책 플래그로 논의 |
| Remote Workspace | Extension/local runtime에는 Remote Workspace resolver와 `remote_*` 도구 주입이 없다. | 서버 builder는 `remoteWorkspaceId`가 resolve된 경우 `remote_*` 도구를 mode별로 주입한다. | 중간 | 문서화만 함 | Extension에서 remote 실행이 필요하면 API/secret resolver 연동 또는 local connector 설계 필요 |
| RAG / Knowledge tool | local runtime은 `theseus_engine/rag` 기반 `search_knowledge_base`, `ingest_document`를 사용할 수 있다. | 서버 builder는 `src/knowledge`와 engine RAG schema 혼동을 막기 위해 기본적으로 engine RAG tool을 비활성화한다. `THESEUS_ENABLE_ENGINE_RAG_TOOLS=true`일 때만 복구할 수 있다. | 중간 | 문서화 + 서버 기본 방어 | 서버용 Knowledge tool은 `src/knowledge` adapter로 별도 정리 필요 |
| create_tool server path | Extension/local은 standalone 파일 저장/검증 경로를 사용한다. | 서버 context는 `src.tooling` adapter로 tool build/storage 정책을 위임한다. | 낮음 | 보정함 | server adapter 계약 변경 시 `tool_server_adapter.py`만 확인 |
| Session persistence | Extension은 `.theseus_sessions/*.json`을 source of truth로 사용한다. | 서버는 Spring/API history를 source of truth로 사용한다. | 낮음 | 문서화만 함 | 장기적으로 local/server session projection 차이를 테스트로 고정 |
| System prompt assembly | Extension/local runtime은 `TheseusStateMachine.get_system_prompt()`를 사용한다. | 서버 worker도 `src/builder/system_prompt.py`를 통해 같은 `theseus_engine.prompts.builder.build_system_prompt()` 결과를 사용한다. | 낮음 | 차이 없음 | prompt 문구 변경 시 `docs/prompt/prompt_architecture_map.md`와 함께 검토 |

## 확인 결과

- Extension의 기존 수정 파일(`vscode-extension/media/components/RunnerStatus.js`,
  `vscode-extension/media/styles.css`, VSIX)은 이번 리팩토링에서 수정하지 않았다.
- Tool visibility 계산은 engine 공통 모듈로 이동했지만, local runner와 TUI는
  기존 `.theseus_sessions` 포맷과 UI history projection을 유지한다.
- `state.py` 프롬프트 모놀리스는 `theseus_engine/prompts/` 패키지로 분리했지만,
  Extension/local runtime과 서버 runtime 모두 같은 canonical builder를 경유하므로
  기능 차이는 확인되지 않았다.

## 주의할 점

- `src/builder/engine.py`는 서버 오케스트레이션 계층이므로 Remote Workspace,
  plan binding, 서버 Knowledge policy 같은 서버 전용 guard를 유지할 수 있다.
- `theseus_engine`은 CLI/TUI/Extension에서도 import되므로 `src.*` 직접 의존은
  optional adapter 뒤에 둔다.
- Extension 기능과 서버 기능이 다를 때는 먼저 이 문서에 차이를 남기고,
  공통화가 제품적으로 필요한지 별도 작업으로 판단한다.
