import asyncio
import logging
from typing import ClassVar

import httpx
from bs4 import BeautifulSoup
from markdownify import markdownify
from pydantic import BaseModel, Field

from theseus_engine.tools.core.base_tools import BaseTool, ToolExecutionContext, ToolResult
from theseus_engine.tools.core.web_search_tool import _parse_search_results

log = logging.getLogger(__name__)

class DeepResearchInput(BaseModel):
    """Arguments for deep web research."""

    query: str = Field(description="Search query to perform deep research on.")
    max_links: int = Field(
        default=3, ge=1, le=5,
        description="Number of top search results to fetch and parse.",
    )

class DeepResearchTool(BaseTool):
    """Macro tool that performs search, parallel fetching, and markdown conversion."""

    name = "deep_research"
    description = (
        "Perform a deep web research: searches the web, visits the top links concurrently, "
        "and extracts their contents as clean Markdown. Use this for complex inquiries "
        "to save context turns instead of manually calling search and fetch."
    )
    input_model = DeepResearchInput
    permission_level = 1

    # Class-level memory to prevent infinite loops across executions
    _visited_queries: ClassVar[set[str]] = set()
    _MAX_VISITED: ClassVar[int] = 100

    @classmethod
    def reset_visited(cls) -> None:
        """세션 리셋 시 방문 쿼리 캐시를 초기화합니다."""
        cls._visited_queries.clear()

    async def execute(
        self, arguments: DeepResearchInput, context: ToolExecutionContext
    ) -> ToolResult:
        query = arguments.query.strip().lower()

        # 오래된 캐시 자동 정리 (메모리 누수 방지)
        if len(self._visited_queries) >= self._MAX_VISITED:
            self._visited_queries.clear()

        # 1. Infinite Loop Prevention (State Check)
        if query in self._visited_queries:
            return ToolResult(
                output=f"System Error: You have already searched for '{arguments.query}'. Do not repeat the same query. Try different keywords or a different approach.",
                is_error=True
            )
        self._visited_queries.add(query)

        # 2. Search Web (DuckDuckGo HTML)
        endpoint = "https://html.duckduckgo.com/html/"
        try:
            async with httpx.AsyncClient(follow_redirects=True, timeout=20.0) as client:
                search_res = await client.post(
                    endpoint,
                    data={"q": arguments.query},
                    headers={"User-Agent": "Theseus-DeepResearch/1.0"},
                )
                search_res.raise_for_status()
        except httpx.HTTPError as exc:
            return ToolResult(
                output=f"Search failed: {exc}", is_error=True
            )

        results = _parse_search_results(search_res.text, limit=arguments.max_links)
        if not results:
            return ToolResult(
                output="No search results found.", is_error=True
            )

        # 3. Parallel Fetching
        async def _fetch_and_parse(url: str, title: str) -> str:
            try:
                async with httpx.AsyncClient(follow_redirects=True, timeout=15.0) as c:
                    resp = await c.get(url, headers={"User-Agent": "Mozilla/5.0"})
                    resp.raise_for_status()
                    
                    # 4. Content Extraction (BeautifulSoup + Markdownify)
                    soup = BeautifulSoup(resp.text, "html.parser")
                    # Remove useless tags
                    for tag in soup(["script", "style", "nav", "footer", "header", "noscript"]):
                        tag.decompose()
                    
                    clean_html = str(soup.body if soup.body else soup)
                    md_text = markdownify(clean_html, heading_style="ATX").strip()
                    
                    # Truncate if insanely long (prevent token explosion)
                    if len(md_text) > 8000:
                        md_text = md_text[:8000] + "\n...[TRUNCATED_DUE_TO_LENGTH]..."

                    return f"### Source: {title}\n**URL:** {url}\n\n{md_text}\n\n---\n"
            except Exception as e:
                return f"### Source: {title}\n**URL:** {url}\n\n[Error fetching content: {e}]\n\n---\n"

        fetch_tasks = [
            _fetch_and_parse(r["url"], r["title"]) for r in results
        ]
        
        parsed_contents = await asyncio.gather(*fetch_tasks)

        final_output = f"# Deep Research Results for '{arguments.query}'\n\n" + "".join(parsed_contents)
        
        return ToolResult(output=final_output)
