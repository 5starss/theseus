"""Filesystem grep tool."""

import re
import logging
from pathlib import Path

from pydantic import BaseModel, Field
from openharness.tools.base import BaseTool, ToolExecutionContext, ToolResult

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

    async def execute(self, arguments: GrepInput, context: ToolExecutionContext) -> ToolResult:
        search_path = _resolve_path(context.cwd, arguments.path)
        
        security_err = _check_path_security(search_path, context.cwd)
        if security_err:
            return ToolResult(output=security_err, is_error=True)

        try:
            results = []
            flags = re.IGNORECASE if arguments.case_insensitive else 0
            pattern = re.compile(arguments.query, flags)
            
            files_to_check = []
            if search_path.is_file():
                files_to_check = [search_path]
            else:
                glob_pat = "**/*" if arguments.recursive else "*"
                files_to_check = [p for p in search_path.glob(glob_pat) if p.is_file()]

            for f_path in files_to_check:
                try:
                    # Skip common heavy binary or hidden dirs
                    if any(part.startswith('.') for part in f_path.parts) or "node_modules" in f_path.parts or "__pycache__" in f_path.parts:
                        continue
                        
                    content = f_path.read_text(encoding="utf-8", errors="ignore")
                    for i, line in enumerate(content.splitlines()):
                        if pattern.search(line):
                            rel_path = f_path.relative_to(context.cwd)
                            results.append(f"{rel_path}:{i+1}: {line.strip()}")
                            if len(results) >= 300: break
                except Exception:
                    continue
                if len(results) >= 300: break

            if not results:
                return ToolResult(output=f"No matches found for '{arguments.query}'")
            
            return ToolResult(output=f"Found {len(results)} matches:\n" + "\n".join(results) + ("\n... (truncated)" if len(results) >= 300 else ""))
        except Exception as e:
            return ToolResult(output=f"Grep failed: {e}", is_error=True)
