"""File writing tool."""

import logging
from pathlib import Path

from pydantic import BaseModel, Field
from theseus_engine.tools.core.base_tools import BaseTool, ToolExecutionContext, ToolResult

from theseus_engine.tools.core.edit_safety import (
    build_overwrite_rejected_report,
    merge_preserve_patterns,
    render_blocked_message,
    render_success_message,
    validate_text_update,
)
from theseus_engine.tools.core.file_utils import _resolve_path, _check_path_security, _strip_markdown_links

log = logging.getLogger(__name__)

class WriteFileInput(BaseModel):
    """Input for creating/overwriting a file."""
    path: str = Field(description="Path of the file to write")
    content: str = Field(description="Full text content for the file")
    allow_overwrite: bool = Field(
        default=False,
        description="Set true only for explicit full-file replacement or recovery of an existing file.",
    )
    overwrite_reason: str | None = Field(
        default=None,
        description="Required human-readable reason when allow_overwrite=true.",
    )
    preserve_patterns: list[str] = Field(
        default_factory=list,
        description="Strings that must remain present after the write, such as values the user said not to change.",
    )

class WriteFileTool(BaseTool):
    """Creates or overwrites a file in the workspace."""
    name = "write_file"
    description = (
        "Create a new file. Existing file overwrite is blocked unless the user explicitly "
        "requested full replacement or recovery and allow_overwrite=true with overwrite_reason."
    )
    is_destructive = True  # 기존 파일 덮어쓰기 가능
    input_model = WriteFileInput
    permission_level = 2

    def is_read_only(self, arguments) -> bool:
        return False

    async def execute(self, arguments: WriteFileInput, context: ToolExecutionContext) -> ToolResult:
        path = _resolve_path(context.cwd, arguments.path)
        
        security_err = _check_path_security(path, context.cwd)
        if security_err:
            return ToolResult(output=security_err, is_error=True)

        try:
            # 코드 파일(.py 등)의 경우 LLM이 삽입한 마크다운 링크를 제거
            content = arguments.content
            if path.suffix in (".py", ".ts", ".js", ".tsx", ".jsx", ".sh"):
                content = _strip_markdown_links(content)
            preserve_patterns = merge_preserve_patterns(
                arguments.preserve_patterns,
                context.metadata,
            )

            existed_before = path.exists()
            original_content = ""
            if existed_before:
                original_content = path.read_text(encoding="utf-8")
                if not arguments.allow_overwrite or not (arguments.overwrite_reason or "").strip():
                    report = build_overwrite_rejected_report(
                        path=path,
                        old_content=original_content,
                        new_content=content,
                        operation="write_file",
                    )
                    return ToolResult(
                        output=render_blocked_message(report),
                        is_error=True,
                        metadata={"safetyReport": report.to_metadata()},
                    )

            report = validate_text_update(
                path=path,
                old_content=original_content,
                new_content=content,
                operation="write_file",
                expected_change="overwrite" if existed_before else "add_only",
                preserve_patterns=preserve_patterns,
            )
            if not report.allowed:
                return ToolResult(
                    output=render_blocked_message(report),
                    is_error=True,
                    metadata={"safetyReport": report.to_metadata()},
                )

            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(content, encoding="utf-8")
            try:
                written = path.read_text(encoding="utf-8")
                post_report = validate_text_update(
                    path=path,
                    old_content=original_content,
                    new_content=written,
                    operation="write_file",
                    expected_change="overwrite" if existed_before else "add_only",
                    preserve_patterns=preserve_patterns,
                )
                if not post_report.allowed:
                    if existed_before:
                        path.write_text(original_content, encoding="utf-8")
                    else:
                        path.unlink(missing_ok=True)
                    post_report.mark_rolled_back()
                    return ToolResult(
                        output=render_blocked_message(post_report),
                        is_error=True,
                        metadata={"safetyReport": post_report.to_metadata()},
                    )
                report = post_report
            except Exception as verify_error:
                if existed_before:
                    path.write_text(original_content, encoding="utf-8")
                else:
                    path.unlink(missing_ok=True)
                report.violations.append(f"post-write verification failed: {verify_error}")
                report.mark_rolled_back()
                return ToolResult(
                    output=render_blocked_message(report),
                    is_error=True,
                    metadata={"safetyReport": report.to_metadata()},
                )

            return ToolResult(
                output=render_success_message(
                    report=report,
                    action=f"Successfully wrote {len(content)} bytes to {path}",
                    detail="Existing file overwritten." if existed_before else "New file created.",
                ),
                metadata={"safetyReport": report.to_metadata()},
            )
        except Exception as e:
            return ToolResult(output=f"Error writing file: {e}", is_error=True)
