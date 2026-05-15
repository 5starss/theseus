"""String-based file editing tool."""

import logging
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, Field
from theseus_engine.tools.core.base_tools import BaseTool, ToolExecutionContext, ToolResult

from theseus_engine.tools.core.edit_safety import (
    merge_preserve_patterns,
    render_blocked_message,
    render_success_message,
    validate_text_update,
)
from theseus_engine.tools.core.file_utils import _resolve_path, _check_path_security, _strip_markdown_links

log = logging.getLogger(__name__)

class EditFileInput(BaseModel):
    """Input for editing a file."""
    path: str = Field(description="Path of the file to edit")
    old_str: str = Field(description="Exact string to find and replace")
    new_str: str = Field(description="New string to replace it with")
    replace_all: bool = Field(default=False, description="Replace all occurrences instead of just the first one")
    expected_change: Literal["modify", "add_only", "delete", "repair"] = Field(
        default="modify",
        description=(
            "Expected change shape. Use add_only for comments/new lines that must not "
            "remove existing code; use repair only for explicit recovery work."
        ),
    )
    preserve_patterns: list[str] = Field(
        default_factory=list,
        description="Strings that must remain present after the edit, such as values the user said not to change.",
    )

class EditFileTool(BaseTool):
    """Edits a file by replacing a specific string."""
    name = "edit_file"
    description = "Edit an existing file by replacing a specific text block with new content. Use unique 'old_str' for precision."
    is_destructive = True  # 파일 내용 변경
    input_model = EditFileInput

    def is_read_only(self, arguments) -> bool:
        return False
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
            old_str = arguments.old_str
            new_str = arguments.new_str
            # 코드 파일의 경우 old_str/new_str 입력만 마크다운 링크 제거 후 매칭
            # content 전체를 변환하면 주석·문자열 안의 링크까지 손상되므로 입력값만 정규화
            if path.suffix in (".py", ".ts", ".js", ".tsx", ".jsx", ".sh"):
                old_str = _strip_markdown_links(old_str)
                new_str = _strip_markdown_links(new_str)
            if old_str not in content:
                return ToolResult(output=f"Error: The provided 'old_str' was not found in {arguments.path}. Ensure exact match including whitespace.", is_error=True)
            occurrences = content.count(old_str)
            if occurrences != 1 and not arguments.replace_all:
                return ToolResult(
                    output=(
                        "Error: The provided 'old_str' matched "
                        f"{occurrences} locations in {arguments.path}. "
                        "Use a more specific old_str or set replace_all=true only when all matches are intended."
                    ),
                    is_error=True,
                )

            count = 1 if not arguments.replace_all else -1
            updated = content.replace(old_str, new_str, count)
            preserve_patterns = merge_preserve_patterns(
                arguments.preserve_patterns,
                context.metadata,
            )
            report = validate_text_update(
                path=path,
                old_content=content,
                new_content=updated,
                operation="edit_file",
                expected_change=arguments.expected_change,
                preserve_patterns=preserve_patterns,
            )
            if not report.allowed:
                return ToolResult(
                    output=render_blocked_message(report),
                    is_error=True,
                    metadata={"safetyReport": report.to_metadata()},
                )
            
            path.write_text(updated, encoding="utf-8")
            try:
                written = path.read_text(encoding="utf-8")
                post_report = validate_text_update(
                    path=path,
                    old_content=content,
                    new_content=written,
                    operation="edit_file",
                    expected_change=arguments.expected_change,
                    preserve_patterns=preserve_patterns,
                )
                if not post_report.allowed:
                    path.write_text(content, encoding="utf-8")
                    post_report.mark_rolled_back()
                    return ToolResult(
                        output=render_blocked_message(post_report),
                        is_error=True,
                        metadata={"safetyReport": post_report.to_metadata()},
                    )
                report = post_report
            except Exception as verify_error:
                path.write_text(content, encoding="utf-8")
                report.violations.append(f"post-write verification failed: {verify_error}")
                report.mark_rolled_back()
                return ToolResult(
                    output=render_blocked_message(report),
                    is_error=True,
                    metadata={"safetyReport": report.to_metadata()},
                )

            actual_replaces = occurrences if arguments.replace_all else 1
            return ToolResult(
                output=render_success_message(
                    report=report,
                    action=f"Successfully updated {arguments.path}.",
                    detail=f"Replacements made: {actual_replaces}",
                ),
                metadata={"safetyReport": report.to_metadata()},
            )
        except Exception as e:
            return ToolResult(output=f"Error editing file: {e}", is_error=True)
