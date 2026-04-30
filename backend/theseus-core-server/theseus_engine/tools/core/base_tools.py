"""Theseus Base Tools: Standard built-in tools for testing and system control."""

from pydantic import BaseModel, Field
from openharness.tools.base import BaseTool, ToolExecutionContext, ToolResult


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
    permission_level = 5  # High privilege

    async def execute(self, arguments: SystemRebootInput, context: ToolExecutionContext) -> ToolResult:
        return ToolResult(output=f"System reboot initiated. Reason: {arguments.reason}")
