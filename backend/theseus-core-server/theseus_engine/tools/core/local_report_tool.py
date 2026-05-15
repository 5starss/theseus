"""Local report artifact writer for remote-analysis workflows."""

from __future__ import annotations

import os
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
from theseus_engine.tools.core.file_utils import _check_path_security, _strip_markdown_links


_ALLOWED_REPORT_SUFFIXES = {".md", ".json", ".txt"}
_DEFAULT_REPORT_ROOT = "reports"
_SECONDARY_REPORT_ROOT = ".theseus/reports"


class LocalWriteReportInput(BaseModel):
    """Input for writing a local report artifact."""

    path: str = Field(
        description=(
            "Report path. Use a bare file name, reports/<name>, or "
            ".theseus/reports/<name>. Allowed extensions: .md, .json, .txt."
        )
    )
    content: str = Field(description="Full report content to write.")
    allow_overwrite: bool = Field(
        default=False,
        description="Set true only when the user explicitly asked to replace an existing report.",
    )
    overwrite_reason: str | None = Field(
        default=None,
        description="Required reason when allow_overwrite=true.",
    )
    preserve_patterns: list[str] = Field(
        default_factory=list,
        description="Strings that must remain present after the write.",
    )


class LocalWriteReportTool(BaseTool):
    """Writes local report files while remote reads stay scoped to remote tools."""

    name = "local_write_report"
    description = (
        "Write a local report artifact under reports/ or .theseus/reports/. "
        "Use this only for Markdown/JSON/text reports produced from remote_* analysis. "
        "It cannot edit source code, config, or arbitrary workspace files."
    )
    input_model = LocalWriteReportInput
    permission_level = 2
    is_destructive = True

    def is_read_only(self, arguments) -> bool:
        return False

    async def execute(
        self,
        arguments: LocalWriteReportInput,
        context: ToolExecutionContext,
    ) -> ToolResult:
        cwd = Path(context.cwd).resolve()
        configured_root = None
        if isinstance(context.metadata, dict):
            configured_root = context.metadata.get("local_report_root")
        target_result = _resolve_report_path(cwd, arguments.path, configured_root)
        if isinstance(target_result, str):
            return ToolResult(output=target_result, is_error=True)
        path, allowed_roots = target_result

        security_err = _check_path_security(path, cwd)
        if security_err:
            return ToolResult(output=security_err, is_error=True)

        try:
            path.relative_to(cwd)
        except ValueError:
            return ToolResult(
                output=f"로컬 보고서 경로가 workspace 밖입니다: {path}",
                is_error=True,
            )

        if path.suffix.lower() not in _ALLOWED_REPORT_SUFFIXES:
            allowed = ", ".join(sorted(_ALLOWED_REPORT_SUFFIXES))
            return ToolResult(
                output=f"로컬 보고서는 {allowed} 확장자만 허용됩니다: {path.name}",
                is_error=True,
            )

        if not _is_under_any(path, allowed_roots):
            root_text = ", ".join(_relative_to_cwd(root, cwd) for root in allowed_roots)
            return ToolResult(
                output=(
                    "로컬 보고서는 허용된 report 디렉터리 아래에만 저장할 수 있습니다. "
                    f"허용 경로: {root_text}. 요청 경로: {_relative_to_cwd(path, cwd)}"
                ),
                is_error=True,
            )

        try:
            content = arguments.content
            preserve_patterns = merge_preserve_patterns(
                arguments.preserve_patterns,
                context.metadata,
            )

            existed_before = path.exists()
            original_content = path.read_text(encoding="utf-8") if existed_before else ""
            if existed_before and (
                not arguments.allow_overwrite or not (arguments.overwrite_reason or "").strip()
            ):
                report = build_overwrite_rejected_report(
                    path=path,
                    old_content=original_content,
                    new_content=content,
                    operation="local_write_report",
                )
                report.violations = [
                    "local_write_report cannot overwrite an existing report unless "
                    "allow_overwrite=true and overwrite_reason explains the explicit replacement."
                ]
                return ToolResult(
                    output=render_blocked_message(report),
                    is_error=True,
                    metadata={"safetyReport": report.to_metadata()},
                )

            report = validate_text_update(
                path=path,
                old_content=original_content,
                new_content=content,
                operation="local_write_report",
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
                    operation="local_write_report",
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
                    action=f"로컬 보고서 파일을 저장했습니다: {_relative_to_cwd(path, cwd)}",
                    detail="Existing report overwritten." if existed_before else "New report created.",
                ),
                metadata={
                    "reportPath": str(path),
                    "relativePath": _relative_to_cwd(path, cwd),
                    "allowedRoots": [_relative_to_cwd(root, cwd) for root in allowed_roots],
                    "safetyReport": report.to_metadata(),
                },
            )
        except Exception as exc:
            return ToolResult(output=f"로컬 보고서 저장 실패: {exc}", is_error=True)


def _resolve_report_path(
    cwd: Path,
    raw_path: str,
    configured_root: object = None,
) -> tuple[Path, tuple[Path, ...]] | str:
    candidate_text = _strip_markdown_links(raw_path).strip()
    if not candidate_text:
        return "로컬 보고서 파일 경로가 비어 있습니다."

    allowed_roots_result = _allowed_report_roots(cwd, configured_root)
    if isinstance(allowed_roots_result, str):
        return allowed_roots_result
    allowed_roots = allowed_roots_result

    candidate = Path(candidate_text).expanduser()
    if candidate.is_absolute():
        resolved = candidate.resolve()
    else:
        parts = candidate.parts
        if len(parts) == 1:
            resolved = (allowed_roots[0] / candidate).resolve()
        else:
            resolved = (cwd / candidate).resolve()
    return resolved, allowed_roots


def _allowed_report_roots(
    cwd: Path,
    configured_root: object = None,
) -> tuple[Path, ...] | str:
    roots: list[Path] = []
    configured = str(
        configured_root
        if configured_root is not None
        else os.getenv("THESEUS_LOCAL_REPORT_ROOT") or _DEFAULT_REPORT_ROOT
    ).strip()
    for value in (configured, _SECONDARY_REPORT_ROOT):
        if not value:
            continue
        root = Path(value).expanduser()
        if not root.is_absolute():
            root = cwd / root
        root = root.resolve()
        try:
            root.relative_to(cwd)
        except ValueError:
            return (
                "THESEUS_LOCAL_REPORT_ROOT must resolve inside the current workspace. "
                f"Configured root: {root}"
            )
        if root not in roots:
            roots.append(root)
    return tuple(roots)


def _is_under_any(path: Path, roots: tuple[Path, ...]) -> bool:
    for root in roots:
        try:
            path.relative_to(root)
            return True
        except ValueError:
            continue
    return False


def _relative_to_cwd(path: Path, cwd: Path) -> str:
    try:
        return str(path.relative_to(cwd))
    except ValueError:
        return str(path)
