"""MCP resource tools for Theseus."""

from __future__ import annotations

import logging
from pydantic import BaseModel, Field
from openharness.tools.base import BaseTool, ToolExecutionContext, ToolResult

from theseus_engine.mcp.client import get_mcp_manager, McpServerNotConnectedError

log = logging.getLogger(__name__)


class ListMcpResourcesInput(BaseModel):
    """Input for listing MCP resources."""


class ListMcpResourcesTool(BaseTool):
    """List all available resources from connected MCP servers."""

    name = "list_mcp_resources"
    description = "List all available resources (files, documentation, data) from connected MCP servers."
    input_model = ListMcpResourcesInput
    permission_level = 1

    async def execute(
        self, arguments: ListMcpResourcesInput, context: ToolExecutionContext
    ) -> ToolResult:
        manager = get_mcp_manager()
        resources = manager.list_resources()
        if not resources:
            return ToolResult(output="(No connected MCP resources)")
        
        lines = [
            f"{r.server_name} | {r.uri} | {r.description}"
            for r in resources
        ]
        return ToolResult(output="\n".join(lines))


class ReadMcpResourceInput(BaseModel):
    """Arguments for reading an MCP resource."""

    server: str = Field(description="Name of the MCP server")
    uri: str = Field(description="URI of the resource to read")


class ReadMcpResourceTool(BaseTool):
    """Read the content of a specific resource from an MCP server."""

    name = "read_mcp_resource"
    description = "Read the content of a specific resource (e.g. a documentation page or file) from an MCP server."
    input_model = ReadMcpResourceInput
    permission_level = 1

    async def execute(
        self, arguments: ReadMcpResourceInput, context: ToolExecutionContext
    ) -> ToolResult:
        manager = get_mcp_manager()
        try:
            content = await manager.read_resource(arguments.server, arguments.uri)
            return ToolResult(output=content)
        except McpServerNotConnectedError as exc:
            return ToolResult(output=str(exc), is_error=True)
        except Exception as exc:
            return ToolResult(output=f"Failed to read resource: {exc}", is_error=True)
