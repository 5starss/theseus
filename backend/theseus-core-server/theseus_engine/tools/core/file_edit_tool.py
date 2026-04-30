"""String-based file editing tool."""

import logging
from pathlib import Path

from pydantic import BaseModel, Field
from openharness.tools.base import BaseTool, ToolExecutionContext, ToolResult

from theseus_engine.tools.core.file_utils import _resolve_path, _check_path_security

log = logging.getLogger(__name__)

class EditFileInput(BaseModel):
    """Input for editing a file."""
    path: str = Field(description="Path of the file to edit")
    old_str: str = Field(description="Exact string to find and replace")
    new_str: str = Field(description="New string to replace it with")
    replace_all: bool = Field(default=False, description="Replace all occurrences instead of just the first one")

class EditFileTool(BaseTool):
    """Edits a file by replacing a specific string."""
    name = "edit_file"
    description = "Edit an existing file by replacing a specific text block with new content. Use unique 'old_str' for precision."
    input_model = EditFileInput
    permission_level = 2

    async def execute(self, arguments: EditFileInput, context: ToolExecutionContext) -> ToolResult:
        path = _resolve_path(context.cwd, arguments.path)
        
        security_err = _check_path_security(path, context.cwd)
        if security_err:
            return ToolResult(output=security_err, is_error=True)

        if not path.exists():
            return ToolResult(output=f"File not found: {arguments.path}", is_error=True)

        try:
            content = path.read_text(encoding="utf-8")
            if arguments.old_str not in content:
                return ToolResult(output=f"Error: The provided 'old_str' was not found in {arguments.path}. Ensure exact match including whitespace.", is_error=True)
            
            count = 1 if not arguments.replace_all else -1
            updated = content.replace(arguments.old_str, arguments.new_str, count)
            
            path.write_text(updated, encoding="utf-8")
            actual_replaces = content.count(arguments.old_str) if arguments.replace_all else 1
            return ToolResult(output=f"Successfully updated {arguments.path} ({actual_replaces} replacements made).")
        except Exception as e:
            return ToolResult(output=f"Error editing file: {e}", is_error=True)
