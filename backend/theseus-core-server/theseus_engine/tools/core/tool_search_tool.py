"""ToolSearchTool: Runtime tool discovery and injection for RAG fallback.

Activated when RAG (Top-K) search fails to find suitable tools.
When invoked, performs semantic search on full_registry and injects
matched tools into active_registry for immediate use from the next turn.
"""

from __future__ import annotations

import json
import logging
import re
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
        search_registry = (
            context.metadata.get("tool_search_registry")
            or context.metadata.get("tool_registry")
        )
        active_registry = context.metadata.get("active_registry")
        project_id = context.metadata.get("project_id")
        custom_tool_inventory = context.metadata.get("custom_tool_inventory") or []

        if search_registry is None:
            return ToolResult(
                output=(
                    "tool_search: Cannot access a searchable tool registry. "
                    "Check engine_builder tool_metadata configuration."
                ),
                is_error=True,
            )

        # ToolRetriever로 시맨틱 검색 수행. 임베딩 모델 캐시/권한 문제로
        # 실패하면 이름/설명/example query 기반 fallback으로 검색한다.
        search_mode = "semantic"
        try:
            from theseus_engine.core.tool_retriever import ToolRetriever

            retriever = ToolRetriever(search_registry)
            matched_tools = await retriever.retrieve_top_k(
                arguments.query,
                search_registry,
                k=arguments.top_k,
                adaptive=False,
            )
        except Exception as e:
            log.warning("[ToolSearchTool] Semantic search failed; using lexical fallback: %s", e)
            search_mode = "lexical_fallback"
            matched_tools = self._lexical_search(
                search_registry,
                arguments.query,
                top_k=arguments.top_k,
            )

        unavailable_matches = self._lexical_search_unavailable_inventory(
            custom_tool_inventory,
            arguments.query,
            top_k=arguments.top_k,
        )

        if not matched_tools and not unavailable_matches:
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
            f"Search mode: {search_mode}",
            f"Project scope: {project_id if project_id is not None else 'local/default'}",
            "",
        ]
        lines.extend(tool_details)

        if injected:
            lines.append("")
            lines.append(
                f"⚡ {len(injected)} tools added to current session. "
                f"Available from your next response."
            )

        if unavailable_matches:
            lines.extend(["", "Unavailable custom tool candidates:"])
            for item in unavailable_matches:
                missing = item.get("missingModules") or []
                candidates = item.get("installCandidates") or []
                reason = item.get("importError") or "import failed"
                lines.append(
                    f"  ⚠️ **{item.get('toolName') or item.get('fileName')}** "
                    f"is present but not callable yet."
                )
                if missing:
                    lines.append(f"    Missing modules: {', '.join(map(str, missing))}")
                if candidates:
                    lines.append(f"    Install candidates: {', '.join(map(str, candidates))}")
                lines.append(f"    Reason: {reason}")
            lines.append(
                "Use the extension Custom Tools panel to install approved dependencies "
                "and retry loading before calling these tools."
            )

        return ToolResult(output="\n".join(lines))

    @staticmethod
    def _lexical_search(registry: Any, query: str, *, top_k: int) -> list[BaseTool]:
        query_tokens = _tokenize_tool_search_text(query)
        scored: list[tuple[int, str, BaseTool]] = []
        for tool in registry.list_tools():
            haystack_parts = [
                getattr(tool, "name", ""),
                getattr(tool, "description", ""),
            ]
            examples = getattr(tool, "example_queries", None)
            if isinstance(examples, (list, tuple)):
                haystack_parts.extend(str(item) for item in examples)
            haystack = " ".join(haystack_parts)
            haystack_tokens = _tokenize_tool_search_text(haystack)
            overlap = len(query_tokens & haystack_tokens)
            substring_bonus = 2 if query.strip().lower() in haystack.lower() else 0
            name_bonus = 3 if any(token in str(getattr(tool, "name", "")).lower() for token in query_tokens) else 0
            score = overlap + substring_bonus + name_bonus
            if score > 0:
                scored.append((score, getattr(tool, "name", ""), tool))
        scored.sort(key=lambda item: (-item[0], item[1]))
        return [tool for _, _, tool in scored[:top_k]]

    @staticmethod
    def _lexical_search_unavailable_inventory(
        inventory: Any,
        query: str,
        *,
        top_k: int,
    ) -> list[dict[str, Any]]:
        if not isinstance(inventory, list):
            return []
        query_tokens = _tokenize_tool_search_text(query)
        scored: list[tuple[int, str, dict[str, Any]]] = []
        for item in inventory:
            if not isinstance(item, dict):
                continue
            if item.get("loadState") != "unavailable":
                continue
            haystack_parts = [
                item.get("toolName", ""),
                item.get("fileName", ""),
                item.get("moduleName", ""),
                item.get("importError", ""),
                " ".join(str(value) for value in item.get("missingModules", []) or []),
            ]
            haystack = " ".join(str(part) for part in haystack_parts if part)
            haystack_tokens = _tokenize_tool_search_text(haystack)
            overlap = len(query_tokens & haystack_tokens)
            substring_bonus = 2 if query.strip().lower() in haystack.lower() else 0
            score = overlap + substring_bonus
            if score > 0:
                scored.append((score, str(item.get("toolName") or item.get("fileName") or ""), item))
        scored.sort(key=lambda value: (-value[0], value[1]))
        return [item for _, _, item in scored[:top_k]]


def _tokenize_tool_search_text(text: str) -> set[str]:
    aliases = {
        "시스템": {"system"},
        "환경": {"environment", "resource", "monitor"},
        "상태": {"status", "health", "monitor"},
        "리소스": {"resource", "cpu", "memory", "ram"},
        "자원": {"resource", "cpu", "memory", "ram"},
        "조회": {"check", "monitor", "inspect", "read"},
        "점검": {"check", "health", "inspect"},
        "모니터링": {"monitor", "metric", "metrics"},
        "메모리": {"memory", "ram"},
        "날씨": {"weather"},
        "시간": {"time"},
        "툴": {"tool"},
        "도구": {"tool"},
        "커스텀": {"custom"},
    }
    tokens = {
        token.lower()
        for token in re.findall(r"[a-zA-Z0-9_가-힣]+", text)
        if len(token) >= 2
    }
    expanded = set(tokens)
    for token in tokens:
        expanded.update(part for part in token.split("_") if len(part) >= 2)
        expanded.update(aliases.get(token, set()))
        for alias_key, alias_values in aliases.items():
            if alias_key in token:
                expanded.update(alias_values)
    return expanded
