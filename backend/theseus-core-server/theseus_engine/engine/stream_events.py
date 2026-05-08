"""Theseus-native stream event types.

QueryEngine(theseus_engine.engine.query_engine)이 yield하는 이벤트 타입입니다.
OpenHarness 의존이 없는 순수 Theseus 정의입니다.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal, Union


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


@dataclass(frozen=True)
class ToolExecutionCompleted:
    tool_name: str
    output: str
    is_error: bool = False


@dataclass(frozen=True)
class ErrorEvent:
    message: str
    recoverable: bool = True


@dataclass(frozen=True)
class StatusEvent:
    message: str


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


StreamEvent = Union[
    AssistantTextDelta,
    AssistantTurnComplete,
    ToolExecutionStarted,
    ToolExecutionCompleted,
    ErrorEvent,
    StatusEvent,
    CompactProgressEvent,
]
