# Frontend Guide Locator Tool Demo Prompt

## 목적

Theseus 시연에서 사용자가 자연어로 AI 자동매매 가이드 문구 변경을 요청하면,
생성된 커스텀 Tool이 관련 프론트엔드 파일과 수정 위치를 빠르게 찾고,
실제 수정은 Agent의 `read_file` / `edit_file` 경로로 수행하는 흐름을 검증한다.

이 문서는 PLAN 모드에서 그대로 붙여 넣을 Tool 생성 요청 프롬프트를 제공한다.

## Tool 생성 요청 프롬프트

```text
AI 자동매매 가이드 페이지 수정 위치를 빠르게 찾는 Theseus 커스텀 Tool을 만들고 싶어.

Tool 이름은 `frontend_guide_locator`로 해줘.

목적:
이 Tool은 파일을 직접 수정하지 않는다. 사용자의 자연어 변경 요청을 분석해서
어떤 프론트엔드 파일의 어떤 컴포넌트/문구/라인 근처를 수정해야 하는지 찾아준다.
이후 실제 수정은 Agent가 `read_file`과 `edit_file`을 사용해서 수행한다.

허용 읽기 파일:
- `frontend/src/components/layout/sidebar/AIGuideModal.tsx`
- `frontend/src/components/layout/sidebar/AIPopover.tsx`
- 사용자가 실제 자동매매 설정값 변경을 명시한 경우에만:
  - `frontend/src/api/ai.ts`

찾아야 할 주요 위치:
- `AIGuideModal.tsx`
  - `DialogTitle`
  - `DialogDescription`
  - 도입 문구
  - STEP 1 설명
  - STEP 2 설명
  - STEP 3 설명
  - 마무리 안내 박스
  - 체크포인트 문구 배열
  - 확인 버튼 문구
- `AIPopover.tsx`
  - 가이드를 여는 버튼/툴팁 문구
- `ai.ts`
  - 사용자가 최대 관심종목 수 같은 실제 설정값 변경을 명시한 경우에만 후보로 포함

입력값:
- `user_request`: 사용자의 자연어 변경 요청
- `project_root`: 프로젝트 루트 경로

구현 필수 조건:
- `from theseus_engine.tools.core.base_tools import BaseTool, ToolExecutionContext, ToolResult`를 사용한다.
- Pydantic 입력 모델을 정확히 하나 정의한다. 이름은 `FrontendGuideLocatorInput`으로 한다.
- `BaseTool` 하위 클래스를 정확히 하나 정의한다. 이름은 `FrontendGuideLocatorTool`로 한다.
- `FrontendGuideLocatorTool`에는 반드시 `input_model = FrontendGuideLocatorInput`을 지정한다.
- `FrontendGuideLocatorTool`에는 반드시 `permission_level = 2`를 지정한다.
- `FrontendGuideLocatorTool`에는 반드시 아래 시그니처의 실행 메서드를 직접 정의한다:
  `async def execute(self, arguments: FrontendGuideLocatorInput, context: ToolExecutionContext) -> ToolResult:`
- `execute` 메서드를 생략하지 않는다.
- 실행 로직을 `main`, standalone function, helper class에만 두지 말고, 반드시 `execute`에서 입력 검증, 파일 읽기, 후보 추출, `ToolResult` 반환을 수행한다.
- `execute`는 JSON 직렬화 가능한 dict를 `ToolResult.output`에 담아 반환한다.

동작 규칙:
- 위 allowlist에 없는 파일은 절대 읽지 않는다.
- 어떤 파일도 쓰지 않는다.
- `Path.write_text`, `open(..., "w")`, `edit`, `delete`, `mkdir` 같은 쓰기 동작을 사용하지 않는다.
- shell 실행, subprocess, os.system, os.popen, 임의 명령 실행은 절대 사용하지 않는다.
- 외부 API 호출은 하지 않는다.
- Python 표준 라이브러리만 사용한다.
- `project_root`가 들어와도 최종 resolved path가 allowlist 파일 중 하나가 아니면 거부한다.
- 파일은 `Path.read_text(encoding="utf-8")`로 읽는다.
- 한글이 깨져 보이거나 UTF-8 decode에 실패하면 파일을 수정하지 말고 `encoding_warnings`에 기록한다.
- 사용자 요청이 단순 가이드 문구 변경이면 `AIGuideModal.tsx`, `AIPopover.tsx`만 후보로 둔다.
- 사용자가 "관심종목 개수 제한", "자동매매 설정값", "실제 동작값" 변경을 명시한 경우에만 `ai.ts`를 후보로 포함한다.

반환 형식:
JSON 직렬화 가능한 결과를 `ToolResult.output`에 반환해줘.

필수 반환 필드:
- `status`: `"found"`, `"not_found"`, `"needs_user_feedback"`, `"failed"`
- `change_type`: `"guide_copy_change"` 또는 `"behavior_change"`
- `target_files`: 수정 후보 파일 목록
- `matches`: 파일별 수정 후보 목록
  - `file_path`
  - `section`
  - `line_hint`
  - `current_snippet`
  - `suggested_new_text`
  - `confidence`
- `edit_strategy`: Agent가 `edit_file`을 어떻게 쓰면 되는지에 대한 짧은 지침
- `requires_behavior_change`: 실제 자동매매 설정값 변경이 필요한지 여부
- `encoding_warnings`: UTF-8 또는 한글 깨짐 관련 경고
- `warnings`: 애매한 요청, 대상 문구 미발견, 동작값 변경 여부 등
- `verification_steps`: 수정 후 화면에서 확인할 방법

권한:
- `execution_spec.permissionLevel`은 반드시 `2`로 명시해줘.
- `permission_rationale`은 "허용된 프론트엔드 파일을 읽고 수정 위치와 변경 후보만 제안하는 read-only 분석 Tool"이라고 작성해줘.

MVP 제외:
- 파일 수정
- allowlist 외 파일 읽기
- 전체 프로젝트 자동 스캔
- 임의 코드 리팩토링
- shell 명령 실행
- 외부 API 호출
- 자동 git commit
- dev server 실행

시연 검증:
- Tool build 산출물에 `FrontendGuideLocatorTool.execute(...)` 메서드가 반드시 존재해야 한다.
- 가이드 문구 변경 요청은 `AIGuideModal.tsx` 또는 `AIPopover.tsx` 후보를 반환해야 한다.
- 최대 관심종목 수 변경 요청처럼 실제 동작값 변경이 명시된 경우에만 `ai.ts` 후보를 반환해야 한다.
- allowlist 밖 경로를 요청하면 파일을 읽지 않고 `needs_user_feedback` 또는 `failed`로 반환해야 한다.
```

## 시연 실행 예시

Tool build가 완료된 뒤 AGENT 모드에서 다음처럼 요청한다.

```text
frontend_guide_locator를 사용해서 AI 가이드 모달의 제목과 도입 문구를
시연용으로 더 짧고 직관적으로 바꾸려면 어느 파일의 어느 문구를 수정해야
하는지 찾아줘. project_root는 현재 프로젝트 루트야.
```

기대 결과:

```text
status = found
change_type = guide_copy_change
target_files에 AIGuideModal.tsx 포함
matches에 line_hint, current_snippet, suggested_new_text 포함
edit_strategy에 read_file/edit_file 적용 지침 포함
```

이후 Agent가 locator 결과를 바탕으로 `read_file`과 `edit_file`을 사용해
실제 프론트 코드를 수정하고, 프론트 화면에서 hot reload 또는 새로고침으로
변경 결과를 확인한다.

## 운영 주의

- 프론트 dev server 실행은 이 Tool의 책임이 아니다. 시연 전에 별도로 켜둔다.
- 직접 파일 쓰기는 generated Tool이 아니라 Theseus의 기존 `edit_file` 안전 경로가 담당한다.
- 이 Tool은 데모용 가이드 파일 위치 탐색에 특화한다. 범용 프론트 코드 수정 Tool로 확장하지 않는다.
