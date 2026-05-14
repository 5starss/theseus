"""Theseus-native LLM API 타입.

LLM wrapper clients가 사용하는 공통 타입을 Theseus 자체 정의로 제공합니다.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, AsyncIterator, Protocol

from pydantic import BaseModel

from theseus_engine.models.messages import ConversationMessage


# ── Usage ─────────────────────────────────────────────────────


class UsageSnapshot(BaseModel):
    """Token usage returned by the model provider."""
    input_tokens: int = 0
    output_tokens: int = 0

    @property
    def total_tokens(self) -> int:
        return self.input_tokens + self.output_tokens

    @property
    def prompt_tokens(self) -> int:
        """Compatibility alias for server/TUI usage readers."""
        return self.input_tokens

    @property
    def completion_tokens(self) -> int:
        """Compatibility alias for server/TUI usage readers."""
        return self.output_tokens


# ── Request ───────────────────────────────────────────────────


@dataclass(frozen=True)
class ApiMessageRequest:
    """Input parameters for a model invocation."""
    model: str
    messages: list[ConversationMessage]
    system_prompt: str | None = None
    max_tokens: int = 4096
    tools: list[dict[str, Any]] = field(default_factory=list)
    debug_context: dict[str, Any] = field(default_factory=dict)


# ── Stream Events ─────────────────────────────────────────────


@dataclass(frozen=True)
class ApiTextDeltaEvent:
    """Incremental text produced by the model."""
    text: str


@dataclass(frozen=True)
class ApiMessageCompleteEvent:
    """Terminal event containing the full assistant message."""
    message: ConversationMessage
    usage: UsageSnapshot
    stop_reason: str | None = None


@dataclass(frozen=True)
class ApiRetryEvent:
    """A recoverable upstream failure that will be retried automatically."""
    message: str
    attempt: int
    max_attempts: int
    delay_seconds: float


ApiStreamEvent = ApiTextDeltaEvent | ApiMessageCompleteEvent | ApiRetryEvent


# ── Protocol ──────────────────────────────────────────────────


class SupportsStreamingMessages(Protocol):
    """Protocol used by the LLM router in tests and production."""

    async def stream_message(
        self, request: ApiMessageRequest
    ) -> AsyncIterator[ApiStreamEvent]:
        """Yield streamed events for the request."""


# ── Errors ────────────────────────────────────────────────────


class TheseusApiError(RuntimeError):
    """Base class for Theseus LLM API errors."""


class AuthenticationFailure(TheseusApiError):
    """Invalid API key or token."""


class RateLimitFailure(TheseusApiError):
    """Provider rate limit hit."""


class RequestFailure(TheseusApiError):
    """Generic request failure."""
