"""File reading tool."""

import logging
from pathlib import Path

from pydantic import BaseModel, Field
from openharness.tools.base import BaseTool, ToolExecutionContext, ToolResult

from theseus_engine.tools.core.file_utils import _resolve_path, _check_path_security

log = logging.getLogger(__name__)

class ReadFileInput(BaseModel):
    """Input for reading a file."""
    path: str = Field(description="Path of the file to read")
    offset: int = Field(default=0, ge=0, description="Zero-based starting line number")
    limit: int = Field(default=500, ge=1, le=2000, description="Maximum number of lines to return")

class ReadFileTool(BaseTool):
    """Reads a text file from the workspace with line numbers."""
    name = "read_file"
    description = "Read a text file from the local repository. Returns content with line numbers."
    input_model = ReadFileInput
    permission_level = 1

    async def execute(self, arguments: ReadFileInput, context: ToolExecutionContext) -> ToolResult:
        path = _resolve_path(context.cwd, arguments.path)
        
        security_err = _check_path_security(path, context.cwd)
        if security_err:
            return ToolResult(output=security_err, is_error=True)

        if not path.exists():
            return ToolResult(output=f"File not found: {arguments.path}", is_error=True)
        if path.is_dir():
            return ToolResult(output=f"Cannot read directory: {arguments.path}", is_error=True)

        try:
            raw = path.read_bytes()
            if b"\x00" in raw:
                return ToolResult(output=f"Binary file detected. Cannot read as text: {arguments.path}", is_error=True)
            
            text = raw.decode("utf-8", errors="replace")
            lines = text.splitlines()
            
            selected = lines[arguments.offset : arguments.offset + arguments.limit]
            numbered = [
                f"{arguments.offset + i + 1:>6}\t{line}"
                for i, line in enumerate(selected)
            ]
            
            if not numbered:
                return ToolResult(output=f"(File is empty or offset out of range: {arguments.path})")
                
            header = f"--- Reading {arguments.path} (Lines {arguments.offset+1}-{arguments.offset+len(numbered)}) ---\n"
            return ToolResult(output=header + "\n".join(numbered))
        except Exception as e:
            return ToolResult(output=f"Error reading file: {e}", is_error=True)
