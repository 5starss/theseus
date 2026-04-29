# Tool Execution Flow

## Draft 생성 흐름

```text
사용자 메시지 입력
  -> 프로젝트 멤버 권한 확인
  -> Tool row 생성(status = DRAFT, draft_phase = PLAN)
  -> USER 메시지 저장(message_type = TOOL_DRAFT_REQUEST, content_type = TEXT, tool_id = tools.id)
  -> Assistant 계획 또는 명세 생성
  -> ASSISTANT 메시지 저장(message_type = TOOL_DRAFT_RESPONSE, content_type = MARKDOWN or JSON, tool_id = tools.id)
  -> Tool draft 저장(raw_markdown, structured_plan_json, draft_snapshot)
  -> draft_phase = REVIEW
```

## 첨삭 흐름

```text
사용자 첨삭 입력
  -> Tool 생성자 또는 수정 권한 확인
  -> USER 메시지 저장(message_type = TOOL_FEEDBACK, content_type = TEXT, tool_id = tools.id)
  -> draft_phase = PLAN
  -> Assistant 수정 계획 또는 명세 생성
  -> ASSISTANT 메시지 저장(message_type = TOOL_REGENERATE_RESPONSE, content_type = MARKDOWN or JSON, tool_id = tools.id)
  -> Tool draft 갱신(raw_markdown, structured_plan_json, draft_snapshot)
  -> draft_phase = REVIEW
```

## 승인 요청 흐름

```text
사용자 승인 요청
  -> Tool 생성자 확인
  -> status = DRAFT 확인
  -> draft_phase = REVIEW 확인
  -> USER 메시지 저장(message_type = TOOL_APPROVAL_REQUEST, content_type = TEXT, tool_id = tools.id)
  -> tool_approvals row 생성(approval_status = PENDING)
  -> tools.status = PENDING
```

## 검토 흐름

```text
ADMIN 또는 MANAGER 검토
  -> 승인 시 tools.status = APPROVED, tool_approvals.approval_status = APPROVED
  -> 반려 시 tools.status = REJECTED, tool_approvals.approval_status = REJECTED
```

## 메시지 연결 규칙

하나의 채팅 세션은 여러 Tool 생성 흐름을 포함할 수 있다.

| 메시지 종류 | `message_type` | `content_type` | `tool_id` |
| --- | --- | --- | --- |
| 일반 대화 | `CHAT` | `TEXT` | `NULL` |
| Tool 생성 요청 | `TOOL_DRAFT_REQUEST` | `TEXT` | 생성된 Tool ID |
| Tool 계획 또는 명세 제시 | `TOOL_DRAFT_RESPONSE` | `MARKDOWN`, `JSON` | 생성된 Tool ID |
| Tool 첨삭 요청 | `TOOL_FEEDBACK` | `TEXT` | 대상 Tool ID |
| Tool 재제시 | `TOOL_REGENERATE_RESPONSE` | `MARKDOWN`, `JSON` | 대상 Tool ID |
| Tool 승인 요청 | `TOOL_APPROVAL_REQUEST` | `TEXT` | 대상 Tool ID |
| 시스템 안내 | `SYSTEM_NOTICE` | `TEXT`, `JSON` | 관련 Tool이 있으면 대상 Tool ID, 없으면 `NULL` |

`message_order`는 세션 전체 순서다. Tool 단위 대화 이력은 `tool_id`로 필터링하고, 정렬은 `message_order ASC`를 사용한다.

`message_type`은 업무 흐름 분류다. `content_type`은 본문 파싱 또는 렌더링 형식이다. 숫자, 배열, 객체 같은 구조화된 값은 `content_type = JSON`으로 저장한다.

## 상태 전이

```text
DRAFT / PLAN
  -> DRAFT / REVIEW
  -> DRAFT / PLAN
  -> DRAFT / REVIEW
  -> PENDING
  -> APPROVED

DRAFT / PLAN
  -> DRAFT / REVIEW
  -> PENDING
  -> REJECTED
  -> DRAFT / PLAN
```

## 저장 데이터

| 컬럼 | 저장 내용 |
| --- | --- |
| `tools.raw_markdown` | Assistant가 사용자에게 제시한 원본 Markdown 계획 또는 명세 |
| `tools.structured_plan_json` | 단계별 계획, 입력값, 출력값, 검증 기준을 구조화한 JSON |
| `tools.draft_snapshot` | 화면 복원과 재생성을 위한 Draft 상태 스냅샷 |
| `chat_messages.content` | 실제 대화 메시지 본문 |
| `chat_messages.tool_id` | 메시지가 특정 Tool 생성 흐름에 속하는지 나타내는 선택적 FK |
| `chat_messages.message_type` | 메시지가 속한 업무 흐름 |
| `chat_messages.content_type` | 메시지 본문의 파싱 또는 렌더링 형식 |
