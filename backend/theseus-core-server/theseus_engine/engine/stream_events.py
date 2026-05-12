"""Theseus-native stream event types.

QueryEngine(theseus_engine.engine.query_engine)이 yield하는 이벤트 타입입니다.
OpenHarness 의존이 없는 순수 Theseus 정의입니다.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from typing import Any, Literal, Union

# PLAN 모드 DRAFTING 단계에서 LLM이 출력하는 ```json ... ``` 블록 감지 패턴
_PLAN_JSON_RE = re.compile(r"```json\s*(\{.*?\})\s*```", re.DOTALL)


def extract_plan_json(text: str) -> dict | None:
    """LLM 응답 텍스트에서 계획 JSON 블록을 추출합니다.

    Returns:
        파싱된 dict, 또는 JSON 블록이 없거나 파싱 실패 시 None.
    """
    m = _PLAN_JSON_RE.search(text)
    if not m:
        return None
    try:
        return json.loads(m.group(1))
    except json.JSONDecodeError:
        return None


@dataclass(frozen=True)
class AssistantTextDelta:
    text: str


@dataclass(frozen=True)
class AssistantTurnComplete:
    message: Any
    usage: Any


@dataclass(frozen=True)
class ToolExecutionStarted:
    tool_name: str
    tool_input: dict[str, Any]
    tool_use_id: str | None = None


@dataclass(frozen=True)
class ToolExecutionCompleted:
    tool_name: str
    output: str
    is_error: bool = False
    tool_use_id: str | None = None
    tool_input: dict[str, Any] | None = None
    metadata: dict[str, Any] | None = None


# 에러 타입 분류 — src에서 재시도 전략을 문자열 파싱 없이 판단할 수 있도록 제공
ErrorType = Literal[
    "llm_api_error",        # LLM API 호출 실패 (rate limit, timeout 등) → 재시도 가능
    "tool_execution_error", # Tool 실행 실패 (파일 없음, 권한 오류 등) → 케이스별 판단
    "security_blocked",     # HookExecutor / Validator 차단 → 재시도 불가
    "context_overflow",     # Context window 초과 → 압축 후 재시도
    "max_turns_exceeded",   # 최대 턴 수 초과 → 재시도 불가
    "unknown",              # 분류 불가
]


# 에러 타입 분류 — src에서 재시도 전략을 문자열 파싱 없이 판단할 수 있도록 제공
ErrorType = Literal[
    "llm_api_error",        # LLM API 호출 실패 (rate limit, timeout 등) → 재시도 가능
    "tool_execution_error", # Tool 실행 실패 (파일 없음, 권한 오류 등) → 케이스별 판단
    "security_blocked",     # HookExecutor / Validator 차단 → 재시도 불가
    "context_overflow",     # Context window 초과 → 압축 후 재시도
    "max_turns_exceeded",   # 최대 턴 수 초과 → 재시도 불가
    "unknown",              # 분류 불가
]


@dataclass(frozen=True)
class ErrorEvent:
    message: str
    recoverable: bool = True
    error_type: ErrorType = "unknown"


@dataclass(frozen=True)
class StatusEvent:
    message: str
    metadata: dict[str, Any] | None = None


@dataclass(frozen=True)
class AgentLoopStatus:
    phase: Literal[
        "model_start",
        "model_complete",
        "tool_start",
        "tool_complete",
        "waiting",
        "complete",
        "error",
    ]
    turn: int | None = None
    message: str | None = None
    tool_name: str | None = None
    tool_use_id: str | None = None
    tool_count: int | None = None
    is_error: bool = False


@dataclass(frozen=True)
class CompactProgressEvent:
    phase: Literal[
        "hooks_start",
        "context_collapse_start",
        "context_collapse_end",
        "session_memory_start",
        "session_memory_end",
        "compact_start",
        "compact_retry",
        "compact_end",
        "compact_failed",
    ]
    trigger: Literal["auto", "manual", "reactive"]
    message: str | None = None
    attempt: int | None = None
    checkpoint: str | None = None
    metadata: dict[str, Any] | None = None


@dataclass(frozen=True)
class PlanDraftedEvent:
    """PLAN 모드 DRAFTING 단계에서 LLM이 계획 JSON을 생성 완료했을 때 발행.

    Core가 이 이벤트를 yield하면:
    - standalone(TUI): TheseusStateMachine을 WAIT_FOR_REVIEW로 전이
    - server(src): DB에 structuredPlanJson 저장 + SSE 전송
    """
    raw_markdown: str
    """LLM의 전체 응답 텍스트 (JSON 블록 포함)."""
    structured_plan: dict
    """파싱된 계획 JSON."""


StreamEvent = Union[
    AssistantTextDelta,
    AssistantTurnComplete,
    ToolExecutionStarted,
    ToolExecutionCompleted,
    ErrorEvent,
    StatusEvent,
    AgentLoopStatus,
    CompactProgressEvent,
    PlanDraftedEvent,
]
