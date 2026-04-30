"""MCP client manager for Theseus."""

from __future__ import annotations

import asyncio
import contextlib
import logging
from contextlib import AsyncExitStack
from typing import Any, Dict, List, Optional

import httpx
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
from mcp.client.streamable_http import streamablehttp_client
from mcp.types import CallToolResult, ReadResourceResult

from theseus_engine.mcp.types import (
    McpConnectionStatus,
    McpHttpServerConfig,
    McpResourceInfo,
    McpStdioServerConfig,
    McpToolInfo,
)

logger = logging.getLogger(__name__)


class McpServerNotConnectedError(Exception):
    """Raised when an MCP server is not connected or its session has been lost."""


class McpClientManager:
    """Manage MCP connections and expose tools/resources."""

    def __init__(self, server_configs: Dict[str, Any]) -> None:
        self._server_configs = server_configs
        self._statuses: Dict[str, McpConnectionStatus] = {
            name: McpConnectionStatus(
                name=name,
                state="pending",
                transport=getattr(config, "type", "unknown"),
            )
            for name, config in server_configs.items()
        }
        self._sessions: Dict[str, ClientSession] = {}
        self._stacks: Dict[str, AsyncExitStack] = {}

    async def connect_all(self) -> None:
        """Connect all configured MCP servers."""
        for name, config in self._server_configs.items():
            if isinstance(config, McpStdioServerConfig):
                await self._connect_stdio(name, config)
            elif isinstance(config, McpHttpServerConfig):
                await self._connect_http(name, config)
            else:
                transport = getattr(config, "type", "unknown")
                self._statuses[name] = McpConnectionStatus(
                    name=name,
                    state="failed",
                    transport=transport,
                    detail=f"Unsupported MCP transport: {transport}",
                )

    async def close(self) -> None:
        """Close all active MCP sessions."""
        for stack in list(self._stacks.values()):
            with contextlib.suppress(RuntimeError, asyncio.CancelledError):
                await stack.aclose()
        self._stacks.clear()
        self._sessions.clear()

    def list_statuses(self) -> List[McpConnectionStatus]:
        """Return statuses for all configured servers."""
        return [self._statuses[name] for name in sorted(self._statuses)]

    def list_tools(self) -> List[McpToolInfo]:
        """Return all connected MCP tools."""
        tools: List[McpToolInfo] = []
        for status in self.list_statuses():
            tools.extend(status.tools)
        return tools

    def list_resources(self) -> List[McpResourceInfo]:
        """Return all connected MCP resources."""
        resources: List[McpResourceInfo] = []
        for status in self.list_statuses():
            resources.extend(status.resources)
        return resources

    async def call_tool(self, server_name: str, tool_name: str, arguments: Dict[str, Any]) -> str:
        """Invoke one MCP tool and stringify the result."""
        session = self._sessions.get(server_name)
        if session is None:
            status = self._statuses.get(server_name)
            detail = status.detail if status else "unknown server"
            raise McpServerNotConnectedError(
                f"MCP server '{server_name}' is not connected: {detail}"
            )
        try:
            result: CallToolResult = await session.call_tool(tool_name, arguments)
        except Exception as exc:
            raise McpServerNotConnectedError(
                f"MCP server '{server_name}' call failed: {exc}"
            ) from exc
        
        parts: List[str] = []
        for item in result.content:
            if getattr(item, "type", None) == "text":
                parts.append(getattr(item, "text", ""))
            else:
                parts.append(str(item))
        
        if not parts:
            parts.append("(no output)")
        return "\n".join(parts).strip()

    async def read_resource(self, server_name: str, uri: str) -> str:
        """Read one MCP resource and stringify the response."""
        session = self._sessions.get(server_name)
        if session is None:
            raise McpServerNotConnectedError(f"MCP server '{server_name}' is not connected.")
        
        try:
            result: ReadResourceResult = await session.read_resource(uri)
        except Exception as exc:
            raise McpServerNotConnectedError(
                f"MCP server '{server_name}' resource read failed: {exc}"
            ) from exc
        
        parts: List[str] = []
        for item in result.contents:
            text = getattr(item, "text", None)
            if text is not None:
                parts.append(text)
            else:
                parts.append(str(getattr(item, "blob", "")))
        return "\n".join(parts).strip()

    async def _connect_stdio(self, name: str, config: McpStdioServerConfig) -> None:
        stack = AsyncExitStack()
        try:
            read_stream, write_stream = await stack.enter_async_context(
                stdio_client(
                    StdioServerParameters(
                        command=config.command,
                        args=config.args,
                        env=config.env,
                        cwd=config.cwd,
                    )
                )
            )
            await self._register_connected_session(
                name=name,
                config=config,
                stack=stack,
                read_stream=read_stream,
                write_stream=write_stream,
                auth_configured=bool(config.env),
            )
        except Exception as exc:
            await stack.aclose()
            self._statuses[name] = McpConnectionStatus(
                name=name,
                state="failed",
                transport=config.type,
                detail=str(exc),
            )

    async def _connect_http(self, name: str, config: McpHttpServerConfig) -> None:
        stack = AsyncExitStack()
        try:
            http_client = await stack.enter_async_context(
                httpx.AsyncClient(headers=config.headers or None)
            )
            read_stream, write_stream, _ = await stack.enter_async_context(
                streamablehttp_client(config.url, http_client=http_client)
            )
            await self._register_connected_session(
                name=name,
                config=config,
                stack=stack,
                read_stream=read_stream,
                write_stream=write_stream,
                auth_configured=bool(config.headers),
            )
        except Exception as exc:
            await stack.aclose()
            self._statuses[name] = McpConnectionStatus(
                name=name,
                state="failed",
                transport=config.type,
                detail=str(exc),
            )

    async def _register_connected_session(
        self,
        *,
        name: str,
        config: Any,
        stack: AsyncExitStack,
        read_stream: Any,
        write_stream: Any,
        auth_configured: bool,
    ) -> None:
        session = await stack.enter_async_context(ClientSession(read_stream, write_stream))
        await session.initialize()
        
        tool_result = await session.list_tools()
        resource_result = None
        try:
            resource_result = await session.list_resources()
        except Exception:
            pass

        tools = [
            McpToolInfo(
                server_name=name,
                name=tool.name,
                description=tool.description or "",
                input_schema=dict(tool.inputSchema or {"type": "object", "properties": {}}),
            )
            for tool in tool_result.tools
        ]
        resources = [
            McpResourceInfo(
                server_name=name,
                name=resource.name or str(resource.uri),
                uri=str(resource.uri),
                description=resource.description or "",
            )
            for resource in (resource_result.resources if resource_result is not None else [])
        ]
        
        self._sessions[name] = session
        self._stacks[name] = stack
        self._statuses[name] = McpConnectionStatus(
            name=name,
            state="connected",
            transport=getattr(config, "type", "unknown"),
            auth_configured=auth_configured,
            tools=tools,
            resources=resources,
        )


# --- Singleton for Theseus ---
_mcp_manager: Optional[McpClientManager] = None

def get_mcp_manager() -> McpClientManager:
    """Get the global MCP manager singleton."""
    global _mcp_manager
    if _mcp_manager is None:
        # Theseus에서는 환경 변수나 설정 파일에서 MCP 서버 목록을 로드하도록 확장 가능
        _mcp_manager = McpClientManager({})
    return _mcp_manager
