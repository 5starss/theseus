"""Web search tool — searches DuckDuckGo HTML and returns compact results."""

from __future__ import annotations

import html
import re
import logging
from urllib.parse import parse_qs, unquote, urlparse

import httpx
from pydantic import BaseModel, Field

from theseus_engine.tools.core.base_tools import BaseTool, ToolExecutionContext, ToolResult

log = logging.getLogger(__name__)


class WebSearchInput(BaseModel):
    """Arguments for a web search."""

    query: str = Field(description="Search query")
    max_results: int = Field(
        default=5, ge=1, le=10,
        description="Maximum number of results to return",
    )


class WebSearchTool(BaseTool):
    """Run a web search and return compact top results."""

    name = "web_search"
    description = (
        "Search the web using DuckDuckGo and return the top results "
        "with titles, URLs, and snippets."
    )
    input_model = WebSearchInput
    permission_level = 1

    async def execute(
        self, arguments: WebSearchInput, context: ToolExecutionContext
    ) -> ToolResult:
        endpoint = "https://html.duckduckgo.com/html/"
        try:
            async with httpx.AsyncClient(
                follow_redirects=True, timeout=20.0
            ) as client:
                response = await client.post(
                    endpoint,
                    data={"q": arguments.query},
                    headers={"User-Agent": "Theseus/1.0"},
                )
                response.raise_for_status()
        except httpx.HTTPError as exc:
            return ToolResult(
                output=f"web_search failed: {exc}", is_error=True
            )

        results = _parse_search_results(
            response.text, limit=arguments.max_results
        )
        if not results:
            return ToolResult(
                output="No search results found.", is_error=True
            )

        lines = [f"Search results for: {arguments.query}"]
        for idx, r in enumerate(results, 1):
            lines.append(f"{idx}. {r['title']}")
            lines.append(f"   URL: {r['url']}")
            if r["snippet"]:
                lines.append(f"   {r['snippet']}")
        return ToolResult(output="\n".join(lines))


# ── DuckDuckGo HTML parser helpers ──────────────────────────────


def _parse_search_results(
    body: str, *, limit: int
) -> list[dict[str, str]]:
    snippets = [
        _clean_html(m.group("snippet"))
        for m in re.finditer(
            r'<(?:a|div|span)[^>]+class="[^"]*'
            r"(?:result__snippet|result-snippet)"
            r'[^"]*"[^>]*>(?P<snippet>.*?)</(?:a|div|span)>',
            body,
            flags=re.IGNORECASE | re.DOTALL,
        )
    ]

    results: list[dict[str, str]] = []
    anchor_matches = re.finditer(
        r"<a(?P<attrs>[^>]+)>(?P<title>.*?)</a>",
        body,
        flags=re.IGNORECASE | re.DOTALL,
    )
    for index, match in enumerate(anchor_matches):
        attrs = match.group("attrs")
        class_m = re.search(
            r'class="(?P<cls>[^"]+)"', attrs, flags=re.IGNORECASE
        )
        if class_m is None:
            continue
        cls = class_m.group("cls")
        if "result__a" not in cls and "result-link" not in cls:
            continue
        href_m = re.search(
            r'href="(?P<href>[^"]+)"', attrs, flags=re.IGNORECASE
        )
        if href_m is None:
            continue
        title = _clean_html(match.group("title"))
        url = _normalize_ddg_url(href_m.group("href"))
        snippet = snippets[index] if index < len(snippets) else ""
        if title and url:
            results.append(
                {"title": title, "url": url, "snippet": snippet}
            )
        if len(results) >= limit:
            break
    return results


def _normalize_ddg_url(raw_url: str) -> str:
    parsed = urlparse(raw_url)
    if parsed.netloc.endswith("duckduckgo.com") and parsed.path.startswith(
        "/l/"
    ):
        target = parse_qs(parsed.query).get("uddg", [""])[0]
        return unquote(target) if target else raw_url
    return raw_url


def _clean_html(fragment: str) -> str:
    text = re.sub(r"(?s)<[^>]+>", " ", fragment)
    text = html.unescape(text)
    return re.sub(r"\s+", " ", text).strip()
