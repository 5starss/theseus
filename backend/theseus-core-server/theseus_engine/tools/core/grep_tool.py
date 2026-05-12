"""Filesystem grep tool."""

import asyncio
import re
import logging
from pathlib import Path

from pydantic import BaseModel, Field
from theseus_engine.tools.core.base_tools import BaseTool, ToolExecutionContext, ToolResult

from theseus_engine.tools.core.file_utils import _resolve_path, _check_path_security

log = logging.getLogger(__name__)

class GrepInput(BaseModel):
    """Input for searching content."""
    query: str = Field(description="Text or regex pattern to search for")
    path: str = Field(default=".", description="Directory or file to search in")
    recursive: bool = Field(default=True, description="Search sub-directories")
    case_insensitive: bool = Field(default=True, description="Ignore case")

class GrepTool(BaseTool):
    """Searches for text patterns in files."""
    name = "grep"
    description = "Search for a pattern in file contents within the workspace."
    input_model = GrepInput
    permission_level = 1
    is_destructive = False

    def is_read_only(self, arguments) -> bool:
        return True

    async def execute(self, arguments: GrepInput, context: ToolExecutionContext) -> ToolResult:
        search_path = _resolve_path(context.cwd, arguments.path)

        security_err = _check_path_security(search_path, context.cwd)
        if security_err:
            return ToolResult(output=security_err, is_error=True)

        try:
            flags = re.IGNORECASE if arguments.case_insensitive else 0
            pattern = re.compile(arguments.query, flags)
            cwd = context.cwd

            # 파일 목록 수집 + 내용 검색을 executor로 오프로드하여 이벤트 루프 블로킹 방지
            def _sync_grep() -> list[str]:
                results: list[str] = []
                if search_path.is_file():
                    files = [search_path]
                else:
                    glob_pat = "**/*" if arguments.recursive else "*"
                    files = (p for p in search_path.glob(glob_pat) if p.is_file())

                for f_path in files:
                    # 숨김 디렉토리·node_modules·__pycache__ 건너뜀
                    if (
                        any(part.startswith(".") for part in f_path.parts)
                        or "node_modules" in f_path.parts
                        or "__pycache__" in f_path.parts
                    ):
                        continue
                    try:
                        content = f_path.read_text(encoding="utf-8", errors="ignore")
                        for i, line in enumerate(content.splitlines()):
                            if pattern.search(line):
                                try:
                                    rel = f_path.relative_to(cwd)
                                except ValueError:
                                    rel = f_path
                                results.append(f"{rel}:{i + 1}: {line.strip()}")
                                if len(results) >= 300:
                                    return results
                    except Exception:
                        continue
                return results

            loop = asyncio.get_event_loop()
            results = await loop.run_in_executor(None, _sync_grep)

            if not results:
                return ToolResult(output=f"No matches found for '{arguments.query}'")

            truncated = len(results) >= 300
            return ToolResult(
                output=(
                    f"Found {len(results)} matches:\n"
                    + "\n".join(results)
                    + ("\n... (truncated)" if truncated else "")
                )
            )
        except Exception as e:
            return ToolResult(output=f"Grep failed: {e}", is_error=True)
