"""Filesystem globbing tool."""

import logging
from pathlib import Path

from pydantic import BaseModel, Field
from openharness.tools.base import BaseTool, ToolExecutionContext, ToolResult

from theseus_engine.tools.core.file_utils import _resolve_path, _check_path_security

log = logging.getLogger(__name__)

class GlobInput(BaseModel):
    """Input for globbing files."""
    pattern: str = Field(description="Glob pattern (e.g., 'src/**/*.py' or '*.md')")
    root: str = Field(default=".", description="Optional sub-directory to start searching from")

class GlobTool(BaseTool):
    """Lists files matching a pattern."""
    name = "glob"
    description = "Find files in the workspace matching a glob pattern. Recursive search supported with '**'."
    input_model = GlobInput
    permission_level = 1

    async def execute(self, arguments: GlobInput, context: ToolExecutionContext) -> ToolResult:
        search_root = _resolve_path(context.cwd, arguments.root)
        
        security_err = _check_path_security(search_root, context.cwd)
        if security_err:
            return ToolResult(output=security_err, is_error=True)

        try:
            # Use Path.glob for native python globbing
            matches = list(search_root.rglob(arguments.pattern) if "**" in arguments.pattern else search_root.glob(arguments.pattern))
            
            # Filter directories and convert to relative paths
            files = [str(p.relative_to(context.cwd)) for p in matches if p.is_file()]
            files.sort()
            
            if not files:
                return ToolResult(output=f"No matches found for pattern '{arguments.pattern}' in '{arguments.root}'")
            
            return ToolResult(output=f"Found {len(files)} matches:\n" + "\n".join(files[:500]) + ("\n... (truncated)" if len(files) > 500 else ""))
        except Exception as e:
            return ToolResult(output=f"Glob failed: {e}", is_error=True)
