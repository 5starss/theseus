"""ToolSearchTool: RAG 폴백 전략을 위한 런타임 툴 탐색 및 주입 도구.

RAG(Top-K) 검색이 실패하여 적합한 툴을 찾지 못했을 때 활성화된다.
모델이 이 툴을 호출하면 full_registry에서 시맨틱 검색을 수행하고,
매칭된 툴을 active_registry에 즉시 주입하여 다음 턴부터 사용 가능하게 한다.
"""

from __future__ import annotations

import json
import logging
from typing import Any

from pydantic import BaseModel, Field

from openharness.tools.base import BaseTool, ToolExecutionContext, ToolResult

log = logging.getLogger(__name__)


class ToolSearchInput(BaseModel):
    """ToolSearchTool 입력 모델."""

    query: str = Field(
        description=(
            "찾고 싶은 툴에 대한 자연어 설명. "
            "예: 'URL에서 웹 페이지 내용 가져오기', '파일 내 텍스트 검색', "
            "'git 명령어 실행'"
        )
    )
    top_k: int = Field(
        default=5,
        ge=1,
        le=10,
        description="반환할 최대 툴 수 (1~10, 기본값 5).",
    )


class ToolSearchTool(BaseTool):
    """사용 가능한 툴을 검색하고 현재 세션에 즉시 주입하는 메타 툴.

    RAG 기반 Top-K 선별이 실패했을 때 자동으로 활성화된다.
    모델이 이 툴을 호출하면:
      1. full_registry에서 쿼리와 가장 유사한 툴을 검색한다.
      2. 매칭된 툴을 active_registry에 즉시 등록(주입)한다.
      3. 주입된 툴의 이름, 설명, 입력 스키마를 반환한다.
    이후 턴부터 주입된 툴을 바로 호출할 수 있다.
    """

    name = "tool_search"
    description = (
        "사용 가능한 툴을 자연어로 검색하고 현재 세션에 즉시 추가합니다. "
        "필요한 기능을 수행하는 툴을 찾지 못했을 때 사용하세요. "
        "이 툴로 추가된 툴은 다음 응답부터 즉시 호출 가능합니다. "
        "예시: tool_search(query='웹 페이지 내용 가져오기')"
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
                    "tool_search: full_registry에 접근할 수 없습니다. "
                    "engine_builder의 tool_metadata 설정을 확인하세요."
                ),
                is_error=True,
            )

        # ToolRetriever로 시맨틱 검색 수행
        try:
            from theseus_engine.core.tool_retriever import ToolRetriever

            retriever = ToolRetriever(full_registry)
            matched_tools = retriever.retrieve_top_k(
                arguments.query,
                full_registry,
                k=arguments.top_k,
                adaptive=False,
            )
        except Exception as e:
            log.error("[ToolSearchTool] 검색 중 오류: %s", e)
            return ToolResult(
                output=f"툴 검색 중 오류가 발생했습니다: {e}",
                is_error=True,
            )

        if not matched_tools:
            return ToolResult(
                output=(
                    f"'{arguments.query}'에 매칭되는 툴을 찾지 못했습니다. "
                    "다른 키워드로 다시 검색해보세요."
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
                        "[ToolSearchTool] 툴 '%s'을 active_registry에 주입했습니다.",
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
                param_summary = "(스키마 없음)"

            status = "✅ 새로 추가됨" if tool.name in injected else "ℹ️ 이미 사용 가능"
            tool_details.append(
                f"  {status} **{tool.name}**\n"
                f"    설명: {tool.description}\n"
                f"    입력: {param_summary}"
            )

        lines = [
            f"'{arguments.query}' 검색 결과: {len(matched_tools)}개 툴 발견",
            "",
        ]
        lines.extend(tool_details)

        if injected:
            lines.append("")
            lines.append(
                f"⚡ {len(injected)}개 툴이 현재 세션에 추가되었습니다. "
                f"다음 응답부터 즉시 호출할 수 있습니다."
            )

        return ToolResult(output="\n".join(lines))
