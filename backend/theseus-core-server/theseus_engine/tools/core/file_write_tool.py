"""File writing tool."""

import logging
from pathlib import Path

from pydantic import BaseModel, Field
from theseus_engine.tools.core.base_tools import BaseTool, ToolExecutionContext, ToolResult

from theseus_engine.tools.core.file_utils import _resolve_path, _check_path_security, _strip_markdown_links

log = logging.getLogger(__name__)

class WriteFileInput(BaseModel):
    """Input for creating/overwriting a file."""
    path: str = Field(description="Path of the file to write")
    content: str = Field(description="Full text content for the file")

class WriteFileTool(BaseTool):
    """Creates or overwrites a file in the workspace."""
    name = "write_file"
    description = "Create a new file or completely overwrite an existing one."
    is_destructive = True  # 기존 파일 덮어쓰기 가능
    input_model = WriteFileInput

    def is_read_only(self, arguments) -> bool:
        return False
    permission_level = 2

    async def execute(self, arguments: WriteFileInput, context: ToolExecutionContext) -> ToolResult:
        path = _resolve_path(context.cwd, arguments.path)
        
        security_err = _check_path_security(path, context.cwd)
        if security_err:
            return ToolResult(output=security_err, is_error=True)

        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            # 코드 파일(.py 등)의 경우 LLM이 삽입한 마크다운 링크를 제거
            content = arguments.content
            if path.suffix in (".py", ".ts", ".js", ".tsx", ".jsx", ".sh"):
                content = _strip_markdown_links(content)
            path.write_text(content, encoding="utf-8")
            return ToolResult(output=f"Successfully wrote {len(content)} bytes to {path}")
        except Exception as e:
            return ToolResult(output=f"Error writing file: {e}", is_error=True)
