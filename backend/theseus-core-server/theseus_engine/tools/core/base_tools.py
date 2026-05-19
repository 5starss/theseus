"""Theseus Tool Primitives.

BaseTool, ToolExecutionContext, ToolResult, ToolRegistry를
Theseus 자체 정의로 제공합니다.  모든 theseus_engine 코드는
이 모듈에서 import합니다.
"""

from __future__ import annotations

import json
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field


# ── Tool Primitives ───────────────────────────────────────────


@dataclass
class ToolExecutionContext:
    """Shared execution context for tool invocations."""

    cwd: Path
    metadata: dict[str, Any] = field(default_factory=dict)
    hook_executor: Any | None = None
    run_id: str | None = None
    """Kafka runId — 실행 중 로깅·트레이싱에 사용. src에서 주입."""
    tool_draft_id: str | None = None
    """Kafka toolDraftId — 실행 결과를 특정 draft와 연결할 때 사용. src에서 주입."""
    tool_invoker: Any | None = None
    """Optional runtime callback used by tools to call another active tool."""

    async def call_tool(
        self,
        tool_name: str,
        arguments: dict[str, Any] | BaseModel | None = None,
    ) -> "ToolResult":
        """Call another active tool through the runtime's normal execution path."""

        if self.tool_invoker is None:
            return ToolResult(
                output=(
                    "Nested tool calls are not available in this execution "
                    "context."
                ),
                is_error=True,
            )
        if arguments is None:
            payload: dict[str, Any] = {}
        elif isinstance(arguments, BaseModel):
            payload = arguments.model_dump()
        elif isinstance(arguments, dict):
            payload = dict(arguments)
        else:
            return ToolResult(
                output=(
                    "Nested tool call arguments must be a dict, Pydantic "
                    "BaseModel, or None."
                ),
                is_error=True,
            )

        try:
            result = self.tool_invoker(tool_name, payload)
            if hasattr(result, "__await__"):
                result = await result
            if isinstance(result, ToolResult):
                return result
            return ToolResult(output=result)
        except Exception as exc:
            return ToolResult(
                output=f"Nested tool call failed: {tool_name}: {type(exc).__name__}: {exc}",
                is_error=True,
            )


@dataclass
class ToolResult:
    """Normalized tool execution result."""

    output: Any
    is_error: bool = False
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        self.output = stringify_tool_output(self.output)


def stringify_tool_output(output: Any) -> str:
    """Convert a tool output payload into provider-safe text.

    Tool authors often return dict/list payloads for structured evidence. The
    LLM message schema still requires tool_result.content to be a string, so the
    runtime normalizes JSON-serializable values here instead of failing after a
    tool already executed successfully.
    """

    if isinstance(output, str):
        return output
    if output is None:
        return ""
    if isinstance(output, bytes):
        return output.decode("utf-8", errors="replace")
    try:
        return json.dumps(output, ensure_ascii=False, indent=2, default=str)
    except TypeError:
        return str(output)


class BaseTool(ABC):
    """Base class for all Theseus tools."""

    name: str
    description: str
    input_model: type[BaseModel]

    @abstractmethod
    async def execute(self, arguments: BaseModel, context: ToolExecutionContext) -> ToolResult:
        """Execute the tool."""

    def is_read_only(self, arguments: BaseModel) -> bool:
        """Return whether the invocation is read-only."""
        del arguments
        return False

    def to_api_schema(self) -> dict[str, Any]:
        """Return the tool schema expected by the LLM API."""
        return {
            "name": self.name,
            "description": self.description,
            "input_schema": self.input_model.model_json_schema(),
        }


class ToolRegistry:
    """Map tool names to implementations."""

    def __init__(self) -> None:
        self._tools: dict[str, BaseTool] = {}

    def register(self, tool: BaseTool) -> None:
        """Register a tool instance."""
        self._tools[tool.name] = tool

    def unregister(self, name: str) -> bool:
        """Remove a registered tool by name."""
        return self._tools.pop(name, None) is not None

    def get(self, name: str) -> BaseTool | None:
        """Return a registered tool by name."""
        return self._tools.get(name)

    def list_tools(self) -> list[BaseTool]:
        """Return all registered tools."""
        return list(self._tools.values())

    def to_api_schema(self) -> list[dict[str, Any]]:
        """Return all tool schemas in API format."""
        return [tool.to_api_schema() for tool in self._tools.values()]


# ── System Test Tools ─────────────────────────────────────────


class DummyInput(BaseModel):
    """Input for the dummy_echo tool."""
    message: str = Field(description="The message to echo back.")


class DummyTool(BaseTool):
    """A simple tool that echoes back the input message. Used for connectivity testing."""
    name = "dummy_echo"
    description = "Echoes back the provided message to verify tool execution pipeline."
    input_model = DummyInput

    async def execute(self, arguments: DummyInput, context: ToolExecutionContext) -> ToolResult:
        return ToolResult(output=f"Echo: {arguments.message}")


class SystemRebootInput(BaseModel):
    """Input for the system_reboot tool."""
    reason: str = Field(description="Reason for the reboot.")


class SystemRebootTool(BaseTool):
    """A mock tool that simulates a system reboot. (Restricted RBAC)"""
    name = "system_reboot"
    description = "Simulates a system reboot for testing high-privilege RBAC tools."
    input_model = SystemRebootInput
    permission_level = 5

    async def execute(self, arguments: SystemRebootInput, context: ToolExecutionContext) -> ToolResult:
        return ToolResult(output=f"System reboot initiated. Reason: {arguments.reason}")
