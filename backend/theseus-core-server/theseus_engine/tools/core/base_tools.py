"""Theseus Tool Primitives — OpenHarness 완전 독립.

BaseTool, ToolExecutionContext, ToolResult, ToolRegistry를
Theseus 자체 정의로 제공합니다.  모든 theseus_engine 코드는
이 모듈에서 import합니다.
"""

from __future__ import annotations

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


@dataclass(frozen=True)
class ToolResult:
    """Normalized tool execution result."""

    output: str
    is_error: bool = False
    metadata: dict[str, Any] = field(default_factory=dict)


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
