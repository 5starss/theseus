"""ToolSearchTool: Runtime tool discovery and injection for RAG fallback.

Activated when RAG (Top-K) search fails to find suitable tools.
When invoked, performs semantic search on full_registry and injects
matched tools into active_registry for immediate use from the next turn.
"""

from __future__ import annotations

import json
import logging
from typing import Any

from pydantic import BaseModel, Field

from theseus_engine.tools.core.base_tools import BaseTool, ToolExecutionContext, ToolResult

log = logging.getLogger(__name__)


class ToolSearchInput(BaseModel):
    """Input model for ToolSearchTool."""

    query: str = Field(
        description=(
            "Natural language description of the tool you need. "
            "e.g., 'fetch web page content from URL', 'search text in files', "
            "'execute git commands'"
        )
    )
    top_k: int = Field(
        default=5,
        ge=1,
        le=10,
        description="Maximum number of tools to return (1-10, default 5).",
    )


class ToolSearchTool(BaseTool):
    """Meta-tool that searches available tools and injects them into the current session.

    Automatically activated when RAG-based Top-K selection fails.
    When invoked:
      1. Searches full_registry for tools most similar to the query.
      2. Immediately registers (injects) matched tools into active_registry.
      3. Returns names, descriptions, and input schemas of injected tools.
    Injected tools are callable from the next turn onward.
    """

    name = "tool_search"
    description = (
        "Search for available tools using natural language and add them to the "
        "current session. Use this when you cannot find a tool for the needed "
        "functionality. Tools added via this tool are immediately callable "
        "from your next response. Example: tool_search(query='fetch web page content')"
    )
    input_model = ToolSearchInput
    permission_level = 1
    is_destructive = False

    def is_read_only(self, arguments) -> bool:
        return True

    example_queries = [
        "사용 가능한 툴 찾아줘",
        "어떤 도구가 있어?",
        "이 기능을 할 수 있는 툴 검색",
        "툴 목록 보여줘",
        "find available tools",
        "search for tools",
        "what tools can do web scraping",
    ]

    async def execute(
        self, arguments: ToolSearchInput, context: ToolExecutionContext
    ) -> ToolResult:
        full_registry = context.metadata.get("tool_registry")
        active_registry = context.metadata.get("active_registry")

        if full_registry is None:
            return ToolResult(
                output=(
                    "tool_search: Cannot access full_registry. "
                    "Check engine_builder tool_metadata configuration."
                ),
                is_error=True,
            )

        # ToolRetriever로 시맨틱 검색 수행
        try:
            from theseus_engine.core.tool_retriever import ToolRetriever

            retriever = ToolRetriever(full_registry)
            matched_tools = await retriever.retrieve_top_k(
                arguments.query,
                full_registry,
                k=arguments.top_k,
                adaptive=False,
            )
        except Exception as e:
            log.error("[ToolSearchTool] Search error: %s", e)
            return ToolResult(
                output=f"Error during tool search: {e}",
                is_error=True,
            )

        if not matched_tools:
            return ToolResult(
                output=(
                    f"No tools matching '{arguments.query}' found. "
                    "Try searching with different keywords."
                )
            )

        # active_registry에 주입 (없는 툴만)
        injected: list[str] = []
        already_available: list[str] = []

        for tool in matched_tools:
            if active_registry is not None:
                existing = active_registry.get(tool.name)
                if existing is None:
                    active_registry.register(tool)
                    injected.append(tool.name)
                    log.info(
                        "[ToolSearchTool] Injected tool '%s' into active_registry.",
                        tool.name,
                    )
                else:
                    already_available.append(tool.name)
            else:
                # active_registry가 없으면 목록만 반환
                already_available.append(tool.name)

        # 결과 포맷 — 각 툴의 이름, 설명, 입력 스키마 포함
        tool_details = []
        for tool in matched_tools:
            try:
                schema = tool.input_model.model_json_schema()
                props = schema.get("properties", {})
                param_summary = ", ".join(
                    f"{k}: {v.get('description', v.get('type', '?'))}"
                    for k, v in props.items()
                )
            except Exception:
                param_summary = "(no schema)"

            status = "✅ Newly added" if tool.name in injected else "ℹ️ Already available"
            tool_details.append(
                f"  {status} **{tool.name}**\n"
                f"    Description: {tool.description}\n"
                f"    Input: {param_summary}"
            )

        lines = [
            f"Search results for '{arguments.query}': {len(matched_tools)} tools found",
            "",
        ]
        lines.extend(tool_details)

        if injected:
            lines.append("")
            lines.append(
                f"⚡ {len(injected)} tools added to current session. "
                f"Available from your next response."
            )

        return ToolResult(output="\n".join(lines))
