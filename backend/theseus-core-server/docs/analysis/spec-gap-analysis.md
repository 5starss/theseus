# 명세(Spec) vs theseus_engine 갭 분석

> 분석 대상: Java 백엔드 Tool 생성/PLAN 재설계 명세 (2026-05-08 기준)
> 분석 범위: theseus_engine (src/ 레이어 제외)

---

## 1. 멀티턴 LLM 관점

### 문제: 진짜 멀티턴이 아닌 이력 주입 방식

명세는 매 Kafka 메시지에 `history: ConversationMessage[]` 전체를 담아 Core로 전달한다.
Core는 이것을 받아 새 세션처럼 실행한다.

```
[요청 1] history=[]         → LLM 호출 (새 세션)
[요청 2] history=[turn1]    → LLM 호출 (새 세션)
```

**영향:**
- `QueryEngine`의 `_messages` 누적 상태가 매번 버려진다.
- `TheseusStateMachine`, `ScopedMemory`, `ToolRetriever` 인덱스가 매 요청 초기화된다.
- Tool 실행 중간 결과(내부 tool_call 루프)가 다음 요청의 history에 없다.

**권장 대응 (theseus_engine 범위):**
- `sessionId` 기반 engine 인스턴스 재사용 레이어 추가 (선택)
- history 압축 전략 (`context_compressor.py`) 적용 시점 명시

---

## 2. mode별 실행 전략 부재

명세는 `PLAN` / `TOOL` 두 모드를 정의하지만, engine에 모드별 분기가 없다.

| 항목 | 현재 상태 | 필요한 것 |
|------|----------|----------|
| `AgentMode.PLAN` 값 | `"Plan"` | 명세는 `"PLAN"` (대소문자 불일치) |
| PLAN 모드 tool set | 전체 허용 | 파일 쓰기 도구 제한 필요 |
| TOOL 모드 tool set | 전체 허용 | 계획 생성 도구 제한 필요 |
| mode별 system prompt | 현재 4-Mode 구조 존재 | Kafka mode 값과 매핑 필요 |

> `AgentMode.PLAN = "Plan"` 불일치는 theseus_engine 내 수정 대상.
> Kafka에서 `"PLAN"`으로 받으면 `AgentMode("PLAN")` 변환 실패.

---

## 3. StreamEvent 출력 포맷 불일치

명세 completed event 기대값:
```json
{
  "rawMarkdown": "전체 생성 결과",
  "structuredPlanJson": { "blocks": [...] },
  "draftSnapshot": "..."
}
```

현재 engine StreamEvent:
- `AssistantTextDelta` — 텍스트 청크
- `AssistantTurnComplete` — 완료 (rawMarkdown 조립 로직 없음)
- `PlanDraftedEvent` — JSON 감지 시 발행 (추가됨)

**영향:** src 레이어가 `rawMarkdown`을 직접 조립해야 한다 (`AssistantTextDelta` 누적).

---

## 4. Kafka payload → setup_engine() 매핑 없음

Kafka payload 필드와 `setup_engine()` 파라미터 간 변환 레이어가 없다.

```
Kafka: mode, runId, toolId, toolDraftId, history, baseDraft, feedbackItems
           ↓ (매핑 레이어 없음)
setup_engine(): sm, cwd, user_level, history_messages, ...
```

**처리 위치:** src 레이어에서 구현 가능. engine 수정 불필요.

---

## 5. feedbackItems 프롬프트 합성 전략 없음

피드백 재생성 시 `feedbackItems`를 어떻게 LLM에 전달하는지 명세와 engine 모두에 없다.

```json
"feedbackItems": [
  { "blockId": "B1", "comment": "에러 처리 추가해줘" }
]
```

**처리 위치:** src 레이어에서 user 메시지로 변환하여 주입 가능.

---

## 6. APPROVED 이후 실행 흐름 미정의

명세에서 `ToolDraft.status = APPROVED` 이후 흐름이 없다.
실제 코드 실행, 파일 적용 등이 누구의 책임인지 불명확하다.

---

## 7. 동시 실행 격리

Kafka consumer가 병렬로 메시지를 처리할 때 같은 workspace에서 충돌 가능.
`worktree_tools.py`로 git worktree 격리가 가능하지만 자동 적용 흐름이 없다.

---

## 8. Hybrid 아키텍처 — 명세의 사각지대

명세는 에이전트가 서버에서 실행된다고 가정하지만,
실제 배포에서는 **에이전트를 사용자 PC에서 실행하는 Hybrid 방식**이 더 현실적이다.

- 사용자 로컬 파일 접근 문제 해결 (no SSH 필요)
- 서버 부하 분산 (LLM 실행이 서버 CPU/메모리 불필요)
- 네트워크 레이턴시 최소화 (Tool 실행이 로컬)

Hybrid 방식에서 백엔드 역할:
- 프로젝트 설정 / 권한 제공 (`/api/agent/project-config`)
- 대화 이력 저장 (`/api/agent/sessions/{id}/history`)
- 과금 집계 (`/internal/billing/usage`)

`theseus_engine/client/project_client.py`의 `TheseusProjectClient`가 이 통신을 담당한다.
`THESEUS_SERVER_URL` 미설정 시 완전한 standalone 모드로 하위 호환된다.

---

## 요약

| 갭 | engine 수정 필요 | src 처리 가능 |
|----|----------------|--------------|
| AgentMode 값 불일치 | ✅ | - |
| StreamEvent 포맷 | △ (PlanDraftedEvent 추가됨) | ✅ rawMarkdown 조립 |
| Kafka payload 매핑 | - | ✅ |
| feedbackItems 합성 | - | ✅ |
| APPROVED 이후 흐름 | - | 명세 보완 필요 |
| 동시 실행 격리 | △ (worktree 존재) | ✅ 자동화 필요 |
| Hybrid 배포 지원 | ✅ (ProjectClient 추가됨) | ✅ CLI/TUI 통합 완료 |
