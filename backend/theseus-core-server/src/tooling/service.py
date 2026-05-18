from __future__ import annotations

import ast
import json
import logging
import re
import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from src.config import settings

log = logging.getLogger(__name__)

DEFAULT_PERMISSION_LEVEL = 1


def _sanitize_generated_code(code: str) -> str:
    """LLM 생성 코드의 파싱 오염 패턴을 제거합니다.

    처리 항목:
    - 마크다운 코드펜스(```python ... ```) 벗기기
    - CRLF → LF 정규화
    - NULL 바이트 제거
    - 백슬래시 뒤 후행 공백 제거 (SyntaxError: unexpected character after line continuation)
    """
    # 마크다운 코드펜스 벗기기
    fence_match = re.match(
        r"^\s*```(?:python)?\s*\n(.*?)\n\s*```\s*$", code, re.DOTALL
    )
    if fence_match:
        code = fence_match.group(1)

    code = code.replace("\r\n", "\n").replace("\r", "\n")
    code = code.replace("\x00", "")
    code = re.sub(r"\\ +\n", "\\\n", code)
    return code
_DEFAULT_CUSTOM_TOOLS_DIR = (
    Path(__file__).resolve().parents[2] / "theseus_engine" / "custom_tools"
)


def _configured_path(value: str | None, default: Path) -> Path:
    raw = str(value or "").strip()
    if not raw:
        return default
    return Path(raw).expanduser().resolve()


CUSTOM_TOOLS_DIR = _configured_path(
    settings.THESEUS_CUSTOM_TOOLS_DIR,
    _DEFAULT_CUSTOM_TOOLS_DIR,
)
PROJECT_TOOLS_DIR = _configured_path(
    settings.THESEUS_PROJECT_CUSTOM_TOOLS_DIR,
    CUSTOM_TOOLS_DIR / "projects",
)
TOOL_NAME_PATTERN = re.compile(r"^[a-z][a-z0-9_]{2,63}$")

STATUS_DRAFT_SAVED = "draft_saved"
STATUS_VALIDATED = "validated"
STATUS_VALIDATION_FAILED = "validation_failed"
STATUS_SANDBOX_PASSED = "sandbox_passed"
STATUS_SANDBOX_FAILED = "sandbox_failed"
STATUS_ACTIVE = "active"
FAILED_ARTIFACT_CLEANUP_STATUSES = frozenset(
    {
        STATUS_DRAFT_SAVED,
        STATUS_VALIDATION_FAILED,
        STATUS_VALIDATED,
        STATUS_SANDBOX_FAILED,
        STATUS_SANDBOX_PASSED,
    }
)

SANDBOX_ALLOWED_DEPENDENCIES = frozenset(
    {
        "pydantic",
        "psutil",
        "nvidia-ml-py",
        "markdownify",
        "beautifulsoup4",
        "PyYAML",
        "requests",
        "httpx",
        "numpy",
        "packaging",
        "python-dotenv",
    }
)
SANDBOX_IMPORT_PACKAGE_ALIASES = {
    "pynvml": "nvidia-ml-py",
    "bs4": "beautifulsoup4",
    "yaml": "PyYAML",
    "dotenv": "python-dotenv",
}
MISSING_MODULE_RE = re.compile(r"No module named ['\"]([^'\"]+)['\"]")


def _tool_validator_cls():
    from theseus_engine.tools.core.tool_factory import ToolValidator

    return ToolValidator


def _session_local_factory():
    from src.db.postgres import SessionLocal

    return SessionLocal


def _assert_plan_execution_context(*args, **kwargs):
    from src.plan.service import assert_plan_execution_context

    return assert_plan_execution_context(*args, **kwargs)


async def _run_tool_sandbox_gate(*args, **kwargs):
    from src.tooling.sandbox_gate import run_tool_sandbox_gate

    return await run_tool_sandbox_gate(*args, **kwargs)


class ToolCreationError(RuntimeError):
    """Raised when the server-side create_tool pipeline cannot proceed."""

    def __init__(
        self,
        stage: str,
        message: str,
        *,
        errors: list[str] | None = None,
    ) -> None:
        super().__init__(message)
        self.stage = stage
        self.message = message
        self.errors = errors or []


@dataclass(slots=True)
class ServerToolCreationRequest:
    tool_name: str
    python_code: str
    permission_level: int
    project_id: str
    creator_user_id: str
    chat_session_id: int
    plan_id: str
    run_id: str | None = None


@dataclass(slots=True)
class ServerToolArtifactPaths:
    project_dir: Path
    module_path: Path
    metadata_path: Path
    module_name: str


@dataclass(slots=True)
class ServerToolCreationResult:
    status: str
    stage: str
    tool_name: str
    message: str
    module_path: str | None = None
    metadata_path: str | None = None
    permission_level: int | None = None
    registry_registered: bool = False
    errors: list[str] = field(default_factory=list)
    trace_id: str | None = None

    def to_metadata(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class ServerToolSourceResult:
    status: str
    stage: str
    tool_name: str
    message: str
    project_id: str
    module_name: str
    module_path: str
    metadata_path: str
    host_module_path: str | None = None
    host_metadata_path: str | None = None
    source: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)
    permission_level: int | None = None
    registry_registered: bool = False
    sandbox_verified: bool = False
    errors: list[str] = field(default_factory=list)
    trace_id: str | None = None

    def to_metadata(self) -> dict[str, Any]:
        payload = asdict(self)
        payload.pop("source", None)
        return payload


def _slugify_segment(value: str | int) -> str:
    slug = re.sub(r"[^a-zA-Z0-9]+", "_", str(value)).strip("_").lower()
    return slug or "default"


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _new_trace_id() -> str:
    return uuid.uuid4().hex


def _host_custom_tool_path_hint(path: Path, *, storage_root: Path = PROJECT_TOOLS_DIR) -> str | None:
    host_root = str(settings.THESEUS_CUSTOM_TOOLS_HOST_DIR or "").strip()
    if not host_root:
        return None
    try:
        relative = path.resolve(strict=False).relative_to(storage_root.resolve(strict=False))
    except ValueError:
        return None
    return str((Path(host_root).expanduser() / relative).resolve())


def _coerce_permission_level(value: Any) -> int:
    if isinstance(value, bool):
        raise ToolCreationError(
            "permission_validation",
            "permissionLevel must be an integer from 1 to 5.",
            errors=["permission_level_not_integer"],
        )
    if isinstance(value, int):
        level = value
    elif isinstance(value, str) and value.strip().isdigit():
        level = int(value.strip())
    else:
        raise ToolCreationError(
            "permission_validation",
            "permissionLevel must be an integer from 1 to 5.",
            errors=["permission_level_not_integer"],
        )
    if not 1 <= level <= 5:
        raise ToolCreationError(
            "permission_validation",
            "permissionLevel must be an integer from 1 to 5.",
            errors=["permission_level_out_of_range"],
        )
    return level


def _audit_log(event: str, **payload: Any) -> None:
    log.info("[ToolAudit] %s %s", event, json.dumps(payload, ensure_ascii=False, sort_keys=True))


def _format_syntax_error_context(code: str, lineno: int | None, *, radius: int = 5) -> str:
    lines = code.splitlines()
    if not lines:
        return ""
    error_line = max((lineno or 1) - 1, 0)
    start = max(error_line - radius, 0)
    end = min(error_line + radius + 1, len(lines))
    return "\n".join(f"{i + 1}: {lines[i]}" for i in range(start, end))


def _validate_python_syntax_or_raise(code: str, request: ServerToolCreationRequest) -> None:
    try:
        ast.parse(code)
    except SyntaxError as exc:
        context = _format_syntax_error_context(code, exc.lineno)
        log.error(
            "Syntax validation failed. runId=%s projectId=%s planId=%s toolName=%s line=%s error=%s\n%s",
            request.run_id,
            request.project_id,
            request.plan_id,
            request.tool_name,
            exc.lineno,
            exc.msg,
            context,
        )
        message = f"Syntax Error: line {exc.lineno}: {exc.msg}"
        if context:
            message = f"{message}\n{context}"
        raise ToolCreationError("validation_failed", message, errors=[message]) from exc


def normalize_tool_name(tool_name: str) -> str:
    normalized = tool_name.strip().lower().replace("-", "_")
    if not TOOL_NAME_PATTERN.fullmatch(normalized):
        raise ToolCreationError(
            "naming",
            (
                "Tool name must match ^[a-z][a-z0-9_]{2,63}$ and use only "
                "lowercase letters, digits, and underscores."
            ),
            errors=[f"invalid_tool_name:{tool_name}"],
        )
    return normalized


def _safe_tool_name(tool_name: str) -> str:
    try:
        return normalize_tool_name(tool_name)
    except Exception:
        return tool_name.strip().lower().replace("-", "_")


def canonical_tool_module_stem(tool_name: str) -> str:
    """Return the persisted module stem for a logical tool name."""
    normalized = normalize_tool_name(tool_name)
    if normalized.endswith("_tool"):
        return normalized
    return f"{normalized}_tool"


def _safe_tool_file_name(value: Any, *, fallback_stem: str) -> str:
    file_name = Path(str(value or "")).name
    if not file_name.endswith(".py") or file_name.startswith("_"):
        return f"{fallback_stem}.py"
    return file_name


def _paths_from_project_metadata(
    project_dir: Path,
    metadata_path: Path,
) -> tuple[ServerToolArtifactPaths, dict[str, Any]]:
    metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
    fallback_stem = metadata_path.stem.replace(".meta", "")
    file_name = _safe_tool_file_name(
        metadata.get("fileName"),
        fallback_stem=fallback_stem,
    )
    module_path = project_dir / file_name
    module_name = str(metadata.get("moduleName") or module_path.stem).strip()
    if not module_name:
        module_name = module_path.stem
    return (
        ServerToolArtifactPaths(
            project_dir=project_dir,
            module_path=module_path,
            metadata_path=metadata_path,
            module_name=module_name,
        ),
        metadata,
    )


def _project_dir_for_id(
    project_id: str | int,
    *,
    storage_root: Path = PROJECT_TOOLS_DIR,
) -> Path:
    return storage_root / _slugify_segment(project_id)


def build_tool_paths(
    project_id: str,
    tool_name: str,
    *,
    storage_root: Path = PROJECT_TOOLS_DIR,
) -> ServerToolArtifactPaths:
    safe_project_id = _slugify_segment(project_id)
    module_stem = canonical_tool_module_stem(tool_name)
    project_dir = storage_root / safe_project_id
    module_path = project_dir / f"{module_stem}.py"
    metadata_path = project_dir / f"{module_stem}.meta.json"
    return ServerToolArtifactPaths(
        project_dir=project_dir,
        module_path=module_path,
        metadata_path=metadata_path,
        module_name=module_stem,
    )


def _candidate_module_names(
    *,
    tool_name: str | None = None,
    module_name: str | None = None,
) -> set[str]:
    candidates: set[str] = set()
    for value in (tool_name, module_name):
        raw = str(value or "").strip()
        if not raw:
            continue
        normalized = re.sub(r"[^a-zA-Z0-9_]+", "_", raw.lower()).strip("_")
        if normalized:
            candidates.add(normalized)
            candidates.add(canonical_tool_module_stem(normalized))
    return candidates


def _metadata_matches_tool_identifier(
    metadata: dict[str, Any],
    paths: ServerToolArtifactPaths,
    *,
    tool_name: str | None = None,
    module_name: str | None = None,
) -> bool:
    expected_modules = _candidate_module_names(
        tool_name=tool_name,
        module_name=module_name,
    )
    expected_names = {
        str(value or "").strip().lower()
        for value in (tool_name, module_name)
        if str(value or "").strip()
    }
    observed_names = {
        str(metadata.get("toolName") or "").strip().lower(),
        str(metadata.get("moduleName") or "").strip().lower(),
        paths.module_name.lower(),
        paths.module_path.stem.lower(),
    }
    if expected_names & observed_names:
        return True
    if expected_modules and expected_modules & observed_names:
        return True
    return False


def resolve_project_tool_artifact(
    *,
    project_id: str | int,
    tool_name: str | None = None,
    module_name: str | None = None,
    storage_root: Path = PROJECT_TOOLS_DIR,
) -> tuple[ServerToolArtifactPaths, dict[str, Any]]:
    """Resolve a project custom tool by metadata, not by arbitrary path."""

    if not str(tool_name or "").strip() and not str(module_name or "").strip():
        raise ToolCreationError(
            "tool_identifier_missing",
            "custom tool source lookup requires tool_name or module_name.",
            errors=["tool_identifier_missing"],
        )

    project_dir = _project_dir_for_id(project_id, storage_root=storage_root)
    if not project_dir.is_dir():
        raise ToolCreationError(
            "project_tool_root_missing",
            f"Project custom tool directory does not exist: {project_dir}",
            errors=[f"project_dir={project_dir}"],
        )

    for metadata_path in sorted(project_dir.glob("*.meta.json")):
        try:
            paths, metadata = _paths_from_project_metadata(project_dir, metadata_path)
        except Exception:
            continue
        if _metadata_matches_tool_identifier(
            metadata,
            paths,
            tool_name=tool_name,
            module_name=module_name,
        ):
            if not paths.module_path.exists():
                raise ToolCreationError(
                    "module_file_missing",
                    f"Custom tool source file is missing: {paths.module_path}",
                    errors=[f"module_path={paths.module_path}"],
                )
            return paths, metadata

    expected_modules = _candidate_module_names(
        tool_name=tool_name,
        module_name=module_name,
    )
    for stem in sorted(expected_modules):
        orphan_path = project_dir / f"{stem}.py"
        if orphan_path.exists():
            raise ToolCreationError(
                "orphan_artifact",
                (
                    "Custom tool source exists without trusted metadata. "
                    f"Refusing automatic maintenance: {orphan_path}"
                ),
                errors=[f"module_path={orphan_path}", "metadata_missing"],
            )

    raise ToolCreationError(
        "tool_not_found",
        (
            "Project custom tool was not found by toolName/moduleName. "
            f"projectId={project_id}, toolName={tool_name}, moduleName={module_name}."
        ),
        errors=[
            f"projectId={project_id}",
            f"toolName={tool_name}",
            f"moduleName={module_name}",
        ],
    )


def _path_is_within(path: Path, root: Path) -> bool:
    try:
        path.resolve(strict=False).relative_to(root.resolve(strict=False))
        return True
    except ValueError:
        return False


def _artifact_paths_are_guarded(
    paths: ServerToolArtifactPaths,
    *,
    storage_root: Path,
) -> bool:
    return (
        _path_is_within(paths.project_dir, storage_root)
        and _path_is_within(paths.module_path, paths.project_dir)
        and _path_is_within(paths.metadata_path, paths.project_dir)
    )


def _read_metadata_for_cleanup(paths: ServerToolArtifactPaths) -> dict[str, Any]:
    try:
        return json.loads(paths.metadata_path.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _metadata_marks_active(metadata: dict[str, Any]) -> bool:
    return (
        str(metadata.get("status") or "").lower() == STATUS_ACTIVE
        or metadata.get("isActive") is True
    )


def cleanup_report_line(report: dict[str, Any] | None) -> str:
    if not report:
        return "cleanup=not_attempted"
    if report.get("cleanupSucceeded"):
        deleted = ",".join(report.get("deletedFiles") or [])
        return f"cleanup=deleted_failed_artifact({deleted})"
    reason = report.get("skippedReason") or report.get("cleanupError") or "unknown"
    return f"cleanup=skipped({reason})"


def cleanup_failed_tool_artifact(
    paths: ServerToolArtifactPaths,
    *,
    request: ServerToolCreationRequest | None = None,
    failure_stage: str = "",
    failure_code: str = "",
    failure_message: str = "",
    storage_root: Path = PROJECT_TOOLS_DIR,
    require_request_match: bool = True,
) -> dict[str, Any]:
    """Delete inactive failed build artifacts after preserving failure context."""

    report: dict[str, Any] = {
        "cleanupAttempted": False,
        "cleanupSucceeded": False,
        "deletedFiles": [],
        "skippedReason": None,
        "failureStage": failure_stage,
        "failureCode": failure_code or failure_stage,
        "message": failure_message,
        "moduleName": paths.module_name,
        "fileName": paths.module_path.name,
        "modulePath": str(paths.module_path),
        "metadataPath": str(paths.metadata_path),
    }

    try:
        if not paths.metadata_path.exists():
            report["skippedReason"] = "metadata_missing"
            return report

        if not _artifact_paths_are_guarded(paths, storage_root=storage_root):
            report["skippedReason"] = "outside_project_tool_root"
            return report

        metadata = _read_metadata_for_cleanup(paths)
        status = str(metadata.get("status") or "").lower()
        is_active = _metadata_marks_active(metadata)
        report.update(
            {
                "toolName": metadata.get("toolName"),
                "projectId": metadata.get("projectId"),
                "planId": metadata.get("planId"),
                "metadataStatus": status,
                "isActive": is_active,
                "latestTraceId": metadata.get("latestTraceId"),
            }
        )

        if is_active:
            report["skippedReason"] = "active_artifact"
            return report
        if status not in FAILED_ARTIFACT_CLEANUP_STATUSES:
            report["skippedReason"] = "untrusted_status"
            return report
        if require_request_match and request is not None:
            mismatches: list[str] = []
            if str(metadata.get("projectId") or "") != str(request.project_id):
                mismatches.append("projectId")
            if str(metadata.get("planId") or "") != str(request.plan_id):
                mismatches.append("planId")
            if str(metadata.get("moduleName") or "") != str(paths.module_name):
                mismatches.append("moduleName")
            if mismatches:
                report["skippedReason"] = "request_mismatch:" + ",".join(mismatches)
                return report

        report["cleanupAttempted"] = True
        for file_path in (paths.module_path, paths.metadata_path):
            if file_path.exists():
                file_path.unlink()
                report["deletedFiles"].append(file_path.name)
        report["cleanupSucceeded"] = (
            not paths.module_path.exists() and not paths.metadata_path.exists()
        )
        if not report["cleanupSucceeded"]:
            report["skippedReason"] = "delete_incomplete"
        return report
    except Exception as exc:
        report["cleanupError"] = str(exc)
        return report


def _assert_no_conflicting_tool_artifact(
    request: ServerToolCreationRequest,
    paths: ServerToolArtifactPaths,
    *,
    storage_root: Path = PROJECT_TOOLS_DIR,
) -> None:
    if not paths.module_path.exists() and not paths.metadata_path.exists():
        return

    existing_metadata: dict[str, Any] = {}
    if paths.metadata_path.exists():
        try:
            existing_metadata = json.loads(paths.metadata_path.read_text(encoding="utf-8"))
        except Exception:
            existing_metadata = {}

    status = str(existing_metadata.get("status") or "").lower()
    if (
        existing_metadata
        and not _metadata_marks_active(existing_metadata)
        and status in FAILED_ARTIFACT_CLEANUP_STATUSES
    ):
        cleanup_report = cleanup_failed_tool_artifact(
            paths,
            request=None,
            failure_stage="stale_artifact_conflict",
            failure_code="stale_inactive_artifact",
            failure_message="Inactive generated tool artifact blocked a new build.",
            storage_root=storage_root,
            require_request_match=False,
        )
        if cleanup_report.get("cleanupSucceeded"):
            return
        if not paths.module_path.exists() and not paths.metadata_path.exists():
            return
        cleanup_line = cleanup_report_line(cleanup_report)
    else:
        cleanup_line = "cleanup=not_attempted"

    existing_name = existing_metadata.get("toolName") or request.tool_name
    raise ToolCreationError(
        "tool_name_conflict",
        (
            "이미 존재하는 Tool 파일명입니다. "
            f"toolName={existing_name}, moduleName={paths.module_name}, fileName={paths.module_path.name}. "
            "recoverable=true. retry_policy=do_not_retry_same_input. "
            f"{cleanup_line}. "
            "active Tool은 삭제하지 않습니다. metadata가 없거나 상태를 신뢰할 수 없는 artifact는 수동 확인이 필요합니다. "
            "기존 Tool 재사용, 기존 Tool 확장, 새 이름 제안, 또는 교체 승인 요청 중 하나를 선택해야 합니다."
        ),
        errors=[
            "tool_name_conflict",
            f"moduleName={paths.module_name}",
            f"fileName={paths.module_path.name}",
            "retry_policy=do_not_retry_same_input",
            cleanup_line,
        ],
    )


def inject_permission_level(python_code: str, permission_level: int) -> str:
    if "permission_level" in python_code:
        return python_code

    pattern = r'(\n\s+)name\s*=\s*(["\'][^"\']+["\'])'
    replacement = (
        r"\g<1>permission_level = "
        + str(permission_level)
        + r"\g<1>name = \2"
    )
    updated = re.sub(pattern, replacement, python_code, count=1)
    if updated == python_code:
        raise ToolCreationError(
            "permission_injection",
            (
                "Could not inject permission_level automatically. "
                "Declare permission_level explicitly in the tool class."
            ),
        )
    return updated


def _base_metadata(
    request: ServerToolCreationRequest,
    paths: ServerToolArtifactPaths,
    *,
    tool_name: str,
) -> dict[str, Any]:
    now = _now_iso()
    return {
        "toolName": tool_name,
        "moduleName": paths.module_name,
        "projectId": request.project_id,
        "chatSessionId": request.chat_session_id,
        "creatorUserId": request.creator_user_id,
        "planId": request.plan_id,
        "fileName": paths.module_path.name,
        "createdAt": now,
        "updatedAt": now,
        "permissionLevel": request.permission_level,
        "status": STATUS_DRAFT_SAVED,
        "isActive": False,
        "sandboxVerified": False,
        "activationSource": None,
        "latestTraceId": None,
        "validationResult": {
            "success": False,
            "status": "pending",
            "message": None,
            "checkedAt": None,
        },
        "sandboxResult": {
            "success": False,
            "status": "pending",
            "logs": "",
            "error": None,
            "checkedAt": None,
            "executionTimeMs": None,
            "exitCode": None,
            "timedOut": False,
        },
        "approvalHistory": [
            {
                "planId": request.plan_id,
                "status": "approved_for_execution",
                "actorUserId": request.creator_user_id,
                "chatSessionId": request.chat_session_id,
                "recordedAt": now,
            }
        ],
    }


def read_tool_metadata(paths: ServerToolArtifactPaths) -> dict[str, Any]:
    if not paths.metadata_path.exists():
        raise ToolCreationError(
            "metadata_missing",
            f"Tool metadata file does not exist: {paths.metadata_path}",
        )
    return json.loads(paths.metadata_path.read_text(encoding="utf-8"))


def write_tool_metadata(paths: ServerToolArtifactPaths, metadata: dict[str, Any]) -> dict[str, Any]:
    metadata["updatedAt"] = _now_iso()
    paths.metadata_path.write_text(
        json.dumps(metadata, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return metadata


def _record_stage_metadata(
    paths: ServerToolArtifactPaths,
    *,
    status: str,
    trace_id: str,
    metadata_patch: dict[str, Any] | None = None,
) -> dict[str, Any]:
    metadata = read_tool_metadata(paths)
    metadata["status"] = status
    metadata["latestTraceId"] = trace_id
    if metadata_patch:
        metadata.update(metadata_patch)
    return write_tool_metadata(paths, metadata)


def _validated_metadata(
    *,
    success: bool,
    message: str,
    checked_at: str,
) -> dict[str, Any]:
    return {
        "validationResult": {
            "success": success,
            "status": STATUS_VALIDATED if success else STATUS_VALIDATION_FAILED,
            "message": message,
            "checkedAt": checked_at,
        }
    }


def _sandbox_metadata(result: dict[str, Any]) -> dict[str, Any]:
    return {"sandboxResult": result}


def _sandbox_failure_text(result: dict[str, Any]) -> str:
    metadata = result.get("metadata") if isinstance(result.get("metadata"), dict) else {}
    candidates = [
        result.get("error"),
        result.get("logs"),
        metadata.get("error"),
        metadata.get("stdout"),
        metadata.get("stderr"),
    ]
    return "\n".join(str(item) for item in candidates if item)


def _missing_modules_from_sandbox_result(result: dict[str, Any]) -> list[str]:
    found: list[str] = []
    for module_name in MISSING_MODULE_RE.findall(_sandbox_failure_text(result)):
        if module_name not in found:
            found.append(module_name)
    return found


def _sandbox_install_candidates(module_names: list[str]) -> list[str]:
    candidates: list[str] = []
    for module_name in module_names:
        package_name = SANDBOX_IMPORT_PACKAGE_ALIASES.get(module_name, module_name)
        if package_name not in candidates:
            candidates.append(package_name)
    return candidates


def _metadata_dependencies(metadata: dict[str, Any]) -> list[str]:
    dependencies = metadata.get("dependencies") or []
    if not isinstance(dependencies, list):
        return []
    result: list[str] = []
    for item in dependencies:
        name = str(item.get("name") if isinstance(item, dict) else item or "").strip()
        if name and name not in result:
            result.append(name)
    return result


def _project_tool_inventory_item(
    *,
    project_id: str,
    paths: ServerToolArtifactPaths,
    metadata: dict[str, Any],
) -> dict[str, Any]:
    sandbox_result = metadata.get("sandboxResult") or {}
    validation_result = metadata.get("validationResult") or {}
    sandbox_verified = bool(sandbox_result.get("success"))
    item: dict[str, Any] = {
        "toolName": str(metadata.get("toolName") or paths.module_name),
        "fileName": paths.module_path.name,
        "moduleName": paths.module_name,
        "modulePath": str(paths.module_path.resolve()),
        "metadataPath": str(paths.metadata_path.resolve()),
        "projectId": project_id,
        "displayName": metadata.get("displayName"),
        "displayDescription": metadata.get("displayDescription") or metadata.get("description"),
        "permissionLevel": metadata.get("permissionLevel", DEFAULT_PERMISSION_LEVEL),
        "status": str(metadata.get("status") or "unknown"),
        "isActive": bool(metadata.get("isActive", True)),
        "dependencies": _metadata_dependencies(metadata),
        "validationSuccess": bool(validation_result.get("success")),
        "sandboxVerified": sandbox_verified,
        "sandboxResult": sandbox_result,
        "activationSource": metadata.get("activationSource"),
        "missingModules": [],
        "installCandidates": [],
        "importError": "",
        "loadState": "available",
        "canInstall": False,
        "canRegister": False,
        "canEditSource": False,
    }

    if not paths.module_path.exists():
        item["loadState"] = "unavailable"
        item["importError"] = f"Missing module file: {paths.module_path.name}"
        return item
    if not _is_tool_active_metadata(metadata):
        item["loadState"] = "inactive"
        return item

    is_valid, message, tool_class = _tool_validator_cls().validate_and_load_module(
        paths.module_name,
        str(paths.module_path),
    )
    if not is_valid or tool_class is None:
        missing_modules = MISSING_MODULE_RE.findall(str(message or ""))
        item["loadState"] = "unavailable"
        item["importError"] = str(message or "import failed")
        item["missingModules"] = missing_modules
        item["installCandidates"] = _sandbox_install_candidates(missing_modules)
        item["canInstall"] = bool(item["installCandidates"])
        return item

    item["toolName"] = getattr(tool_class, "name", item["toolName"])
    item["permissionLevel"] = getattr(
        tool_class,
        "permission_level",
        item["permissionLevel"],
    )
    item["canRegister"] = True
    item["canEditSource"] = True
    return item


def _classify_sandbox_dependency_failure(result: dict[str, Any]) -> dict[str, Any]:
    missing_modules = _missing_modules_from_sandbox_result(result)
    if not missing_modules:
        return result

    enriched = dict(result)
    metadata = dict(enriched.get("metadata") or {})
    candidates = _sandbox_install_candidates(missing_modules)
    metadata.update(
        {
            "errorType": "sandbox_missing_dependency",
            "missingModules": missing_modules,
            "installCandidates": candidates,
            "allowedSandboxDependencies": sorted(SANDBOX_ALLOWED_DEPENDENCIES),
            "sandboxImage": settings.SANDBOX_IMAGE,
        }
    )
    enriched["metadata"] = metadata
    enriched["errorType"] = "sandbox_missing_dependency"
    return enriched


def _format_sandbox_failure_message(result: dict[str, Any]) -> str:
    message = result.get("error") or "Sandbox gate failed."
    metadata = result.get("metadata") or {}
    error_type = result.get("errorType") or metadata.get("errorType")
    exit_code = result.get("exitCode")
    if exit_code is None:
        exit_code = metadata.get("containerExitCode")

    summary = {
        "errorType": error_type,
        "exitCode": exit_code,
        "timedOut": result.get("timedOut", False),
        "resourceLimited": result.get("resourceLimited", False),
    }
    if error_type == "sandbox_missing_dependency":
        missing_modules = metadata.get("missingModules") or []
        install_candidates = metadata.get("installCandidates") or []
        dependency_details = (
            f"sandbox 원인=sandbox_missing_dependency, "
            f"누락 모듈={missing_modules}, 설치 후보={install_candidates}, "
            f"sandboxImage={metadata.get('sandboxImage') or settings.SANDBOX_IMAGE}. "
            "requirements-sandbox.txt에 허용된 의존성을 추가하고 "
            "Dockerfile.sandbox로 sandbox image를 수동 rebuild한 뒤 Core를 재시작해야 합니다. "
            "ToolBuild 중에는 pip install이나 Docker build를 수행하지 않습니다. "
        )
    else:
        dependency_details = ""
    details = ", ".join(f"{key}={value}" for key, value in summary.items())
    return (
        "생성된 Tool 파일을 직접 실행하지 않고 Core sandbox gate에서 "
        "컴파일/import/구조를 검증하는 중 실패했습니다. "
        f"{dependency_details}{message} ({details})"
    )


def _is_tool_active_metadata(metadata: dict[str, Any]) -> bool:
    validation = metadata.get("validationResult") or {}
    sandbox = metadata.get("sandboxResult") or {}
    return (
        metadata.get("status") == STATUS_ACTIVE
        and bool(metadata.get("isActive"))
        and bool(validation.get("success"))
        and bool(sandbox.get("success"))
    )


def _assert_plan_guard(request: ServerToolCreationRequest) -> None:
    db = _session_local_factory()()
    try:
        _assert_plan_execution_context(
            db,
            plan_id=request.plan_id,
            project_id=request.project_id,
            chat_session_id=request.chat_session_id,
            executing_user_id=request.creator_user_id,
        )
    except RuntimeError as exc:
        raise ToolCreationError("plan_guard", str(exc), errors=[str(exc)]) from exc
    finally:
        db.close()


def persist_draft_tool(
    request: ServerToolCreationRequest,
    *,
    storage_root: Path = PROJECT_TOOLS_DIR,
) -> tuple[ServerToolArtifactPaths, dict[str, Any]]:
    request.permission_level = _coerce_permission_level(request.permission_level)
    normalized_name = normalize_tool_name(request.tool_name)
    code = inject_permission_level(request.python_code, request.permission_level)
    code = _sanitize_generated_code(code)
    _validate_python_syntax_or_raise(code, request)
    paths = build_tool_paths(request.project_id, normalized_name, storage_root=storage_root)
    _assert_no_conflicting_tool_artifact(request, paths, storage_root=storage_root)
    paths.project_dir.mkdir(parents=True, exist_ok=True)
    paths.module_path.write_text(code, encoding="utf-8")
    metadata = _base_metadata(request, paths, tool_name=normalized_name)
    return paths, write_tool_metadata(paths, metadata)


def validate_draft_tool(paths: ServerToolArtifactPaths) -> type[Any]:
    code = paths.module_path.read_text(encoding="utf-8")
    checked_at = _now_iso()
    trace_id = _new_trace_id()
    is_valid, message = _tool_validator_cls().validate_code(code)
    if not is_valid:
        _record_stage_metadata(
            paths,
            status=STATUS_VALIDATION_FAILED,
            trace_id=trace_id,
            metadata_patch=_validated_metadata(
                success=False,
                message=message,
                checked_at=checked_at,
            ),
        )
        raise ToolCreationError("validation_failed", message, errors=[message])

    is_valid_module, module_message, tool_class = _tool_validator_cls().validate_and_load_module(
        paths.module_name,
        str(paths.module_path),
    )
    if not is_valid_module or tool_class is None:
        _record_stage_metadata(
            paths,
            status=STATUS_VALIDATION_FAILED,
            trace_id=trace_id,
            metadata_patch=_validated_metadata(
                success=False,
                message=module_message,
                checked_at=checked_at,
            ),
        )
        raise ToolCreationError("validation_failed", module_message, errors=[module_message])

    _record_stage_metadata(
        paths,
        status=STATUS_VALIDATED,
        trace_id=trace_id,
        metadata_patch=_validated_metadata(
            success=True,
            message="ToolValidator validation passed and metadata recorded.",
            checked_at=checked_at,
        ),
    )
    return tool_class


async def run_tool_sandbox_gate_for_artifact(
    request: ServerToolCreationRequest,
    paths: ServerToolArtifactPaths,
) -> dict[str, Any]:
    trace_id = _new_trace_id()
    result = await _run_tool_sandbox_gate(
        project_id=request.project_id,
        tool_name=normalize_tool_name(request.tool_name),
        tool_code=paths.module_path.read_text(encoding="utf-8"),
    )
    result = _classify_sandbox_dependency_failure(result)
    status = STATUS_SANDBOX_PASSED if result["success"] else STATUS_SANDBOX_FAILED
    _record_stage_metadata(
        paths,
        status=status,
        trace_id=trace_id,
        metadata_patch=_sandbox_metadata(result),
    )
    if not result["success"]:
        error_message = _format_sandbox_failure_message(result)
        raise ToolCreationError(
            "sandbox_failed",
            error_message,
            errors=[error_message],
        )
    return result


def activate_tool_artifact(
    request: ServerToolCreationRequest,
    paths: ServerToolArtifactPaths,
    *,
    tool_class: type[Any],
    registry: Any | None,
    tool_permissions: dict[str, int] | None,
    activation_source: str = "create_tool_server",
) -> bool:
    metadata = read_tool_metadata(paths)
    if not (
        metadata.get("status") == STATUS_SANDBOX_PASSED
        and metadata.get("validationResult", {}).get("success") is True
        and metadata.get("sandboxResult", {}).get("success") is True
        and paths.module_path.exists()
        and paths.metadata_path.exists()
    ):
        raise ToolCreationError(
            "activation_guard",
            "Tool activation requires validated code, sandbox success, and persisted artifacts.",
        )

    registered = False
    if registry is not None:
        try:
            registry.register(tool_class())
            registered = True
        except Exception as exc:
            log.warning("Active tool persisted but runtime registration failed: %s", exc)
    if tool_permissions is not None:
        tool_permissions[tool_class.name] = getattr(
            tool_class,
            "permission_level",
            request.permission_level,
        )

    _record_stage_metadata(
        paths,
        status=STATUS_ACTIVE,
        trace_id=_new_trace_id(),
        metadata_patch={
            "isActive": True,
            "activatedAt": _now_iso(),
            "activationSource": activation_source,
            "sandboxVerified": True,
            "toolName": tool_class.name,
            "permissionLevel": getattr(
                tool_class,
                "permission_level",
                request.permission_level,
            ),
        },
    )
    return registered


async def create_tool_for_server(
    request: ServerToolCreationRequest,
    *,
    registry: Any | None = None,
    tool_permissions: dict[str, int] | None = None,
    storage_root: Path = PROJECT_TOOLS_DIR,
) -> ServerToolCreationResult:
    paths: ServerToolArtifactPaths | None = None
    tool_class: type[Any] | None = None
    try:
        _assert_plan_guard(request)
        paths, metadata = persist_draft_tool(request, storage_root=storage_root)
        draft_trace_id = _new_trace_id()
        _record_stage_metadata(
            paths,
            status=STATUS_DRAFT_SAVED,
            trace_id=draft_trace_id,
        )
        _audit_log(
            "tool_creation_draft_saved",
            trace_id=draft_trace_id,
            tool_name=metadata["toolName"],
            project_id=request.project_id,
            plan_id=request.plan_id,
            user_id=request.creator_user_id,
            chat_session_id=request.chat_session_id,
        )

        tool_class = validate_draft_tool(paths)
        validation_metadata = read_tool_metadata(paths)
        _audit_log(
            "tool_creation_validated",
            trace_id=validation_metadata.get("latestTraceId"),
            tool_name=tool_class.name,
            project_id=request.project_id,
            plan_id=request.plan_id,
            user_id=request.creator_user_id,
            chat_session_id=request.chat_session_id,
            validation_result=validation_metadata.get("validationResult"),
        )

        sandbox_result = await run_tool_sandbox_gate_for_artifact(request, paths)
        sandbox_metadata = read_tool_metadata(paths)
        _audit_log(
            "tool_creation_sandbox_passed",
            trace_id=sandbox_metadata.get("latestTraceId"),
            tool_name=tool_class.name,
            project_id=request.project_id,
            plan_id=request.plan_id,
            user_id=request.creator_user_id,
            chat_session_id=request.chat_session_id,
            sandbox_result=sandbox_result,
        )

        registered = activate_tool_artifact(
            request,
            paths,
            tool_class=tool_class,
            registry=registry,
            tool_permissions=tool_permissions,
            activation_source="create_tool_server",
        )
        active_metadata = read_tool_metadata(paths)
        _audit_log(
            "tool_creation_activated",
            trace_id=active_metadata.get("latestTraceId"),
            tool_name=tool_class.name,
            project_id=request.project_id,
            plan_id=request.plan_id,
            user_id=request.creator_user_id,
            chat_session_id=request.chat_session_id,
            registry_registered=registered,
        )

        return ServerToolCreationResult(
            status="created",
            stage="completed",
            tool_name=tool_class.name,
            message=(
                f"Tool '{tool_class.name}' created for project '{request.project_id}' "
                "and activated after sandbox verification."
            ),
            module_path=str(paths.module_path),
            metadata_path=str(paths.metadata_path),
            permission_level=getattr(
                tool_class,
                "permission_level",
                request.permission_level,
            ),
            registry_registered=registered,
            trace_id=active_metadata.get("latestTraceId"),
        )
    except ToolCreationError as exc:
        failed_metadata: dict[str, Any] = {}
        cleanup_result: dict[str, Any] | None = None
        if paths is not None and paths.metadata_path.exists():
            failed_metadata = read_tool_metadata(paths)
            _audit_log(
                "tool_creation_failed",
                trace_id=failed_metadata.get("latestTraceId"),
                tool_name=failed_metadata.get("toolName", request.tool_name),
                project_id=request.project_id,
                plan_id=request.plan_id,
                user_id=request.creator_user_id,
                chat_session_id=request.chat_session_id,
                stage=exc.stage,
                errors=exc.errors,
            )
            cleanup_result = cleanup_failed_tool_artifact(
                paths,
                request=request,
                failure_stage=exc.stage,
                failure_code=exc.stage,
                failure_message=exc.message,
                storage_root=storage_root,
                require_request_match=True,
            )
            _audit_log(
                "tool_creation_failed_artifact_cleanup",
                trace_id=failed_metadata.get("latestTraceId"),
                tool_name=failed_metadata.get("toolName", request.tool_name),
                project_id=request.project_id,
                plan_id=request.plan_id,
                user_id=request.creator_user_id,
                chat_session_id=request.chat_session_id,
                stage=exc.stage,
                cleanup=cleanup_result,
            )
        errors = list(exc.errors)
        if cleanup_result is not None:
            errors.append(cleanup_report_line(cleanup_result))
        return ServerToolCreationResult(
            status="rejected",
            stage=exc.stage,
            tool_name=_safe_tool_name(request.tool_name),
            message=exc.message,
            module_path=str(paths.module_path) if paths is not None and paths.module_path.exists() else None,
            metadata_path=str(paths.metadata_path)
            if paths is not None and paths.metadata_path.exists()
            else None,
            errors=errors,
            trace_id=failed_metadata.get("latestTraceId"),
        )
    except Exception as exc:
        failed_metadata: dict[str, Any] = {}
        cleanup_result: dict[str, Any] | None = None
        if paths is not None and paths.metadata_path.exists():
            metadata = read_tool_metadata(paths)
            failed_metadata = metadata
            _audit_log(
                "tool_creation_unexpected_failure",
                trace_id=metadata.get("latestTraceId"),
                tool_name=metadata.get("toolName", request.tool_name),
                project_id=request.project_id,
                plan_id=request.plan_id,
                user_id=request.creator_user_id,
                chat_session_id=request.chat_session_id,
                error=str(exc),
            )
            cleanup_result = cleanup_failed_tool_artifact(
                paths,
                request=request,
                failure_stage="unexpected",
                failure_code="unexpected",
                failure_message=str(exc),
                storage_root=storage_root,
                require_request_match=True,
            )
            _audit_log(
                "tool_creation_unexpected_artifact_cleanup",
                trace_id=metadata.get("latestTraceId"),
                tool_name=metadata.get("toolName", request.tool_name),
                project_id=request.project_id,
                plan_id=request.plan_id,
                user_id=request.creator_user_id,
                chat_session_id=request.chat_session_id,
                cleanup=cleanup_result,
            )
        errors = [str(exc)]
        if cleanup_result is not None:
            errors.append(cleanup_report_line(cleanup_result))
        return ServerToolCreationResult(
            status="rejected",
            stage="unexpected",
            tool_name=_safe_tool_name(request.tool_name),
            message=f"Unexpected tool creation failure: {exc}",
            module_path=str(paths.module_path) if paths is not None and paths.module_path.exists() else None,
            metadata_path=str(paths.metadata_path)
            if paths is not None and paths.metadata_path.exists()
            else None,
            errors=errors,
            trace_id=failed_metadata.get("latestTraceId"),
        )


def read_project_tool_source(
    *,
    project_id: str | int,
    tool_name: str | None = None,
    module_name: str | None = None,
    storage_root: Path = PROJECT_TOOLS_DIR,
) -> ServerToolSourceResult:
    try:
        paths, metadata = resolve_project_tool_artifact(
            project_id=project_id,
            tool_name=tool_name,
            module_name=module_name,
            storage_root=storage_root,
        )
        source = paths.module_path.read_text(encoding="utf-8")
        sandbox_verified = bool((metadata.get("sandboxResult") or {}).get("success"))
        return ServerToolSourceResult(
            status="read",
            stage="completed",
            tool_name=str(metadata.get("toolName") or paths.module_name),
            message="Custom tool source loaded.",
            project_id=str(project_id),
            module_name=paths.module_name,
            module_path=str(paths.module_path),
            metadata_path=str(paths.metadata_path),
            host_module_path=_host_custom_tool_path_hint(paths.module_path, storage_root=storage_root),
            host_metadata_path=_host_custom_tool_path_hint(paths.metadata_path, storage_root=storage_root),
            source=source,
            metadata=metadata,
            permission_level=metadata.get("permissionLevel"),
            sandbox_verified=sandbox_verified,
            trace_id=metadata.get("latestTraceId"),
        )
    except ToolCreationError as exc:
        return ServerToolSourceResult(
            status="rejected",
            stage=exc.stage,
            tool_name=_safe_tool_name(tool_name or module_name or "custom_tool"),
            message=exc.message,
            project_id=str(project_id),
            module_name=str(module_name or ""),
            module_path="",
            metadata_path="",
            errors=list(exc.errors),
        )
    except Exception as exc:
        return ServerToolSourceResult(
            status="rejected",
            stage="unexpected",
            tool_name=_safe_tool_name(tool_name or module_name or "custom_tool"),
            message=f"Unexpected custom tool source read failure: {exc}",
            project_id=str(project_id),
            module_name=str(module_name or ""),
            module_path="",
            metadata_path="",
            errors=[str(exc)],
        )


async def update_project_tool_source(
    *,
    project_id: str | int,
    python_code: str,
    tool_name: str | None = None,
    module_name: str | None = None,
    actor_user_id: str = "system",
    chat_session_id: int = 0,
    plan_id: str = "custom_tool_maintenance",
    run_id: str | None = None,
    registry: Any | None = None,
    active_registry: Any | None = None,
    tool_permissions: dict[str, int] | None = None,
    metadata_patch: dict[str, Any] | None = None,
    storage_root: Path = PROJECT_TOOLS_DIR,
) -> ServerToolSourceResult:
    paths: ServerToolArtifactPaths | None = None
    staged_paths: ServerToolArtifactPaths | None = None
    cleanup_result: dict[str, Any] | None = None
    try:
        paths, current_metadata = resolve_project_tool_artifact(
            project_id=project_id,
            tool_name=tool_name,
            module_name=module_name,
            storage_root=storage_root,
        )
        if not _artifact_paths_are_guarded(paths, storage_root=storage_root):
            raise ToolCreationError(
                "outside_project_tool_root",
                f"Resolved custom tool artifact is outside the project tool root: {paths.module_path}",
                errors=["outside_project_tool_root"],
            )
        if not _is_tool_active_metadata(current_metadata):
            raise ToolCreationError(
                "inactive_or_unverified_tool",
                (
                    "Only active sandbox-verified project custom tools can be updated "
                    "through custom_tool_update_source."
                ),
                errors=[
                    f"status={current_metadata.get('status')}",
                    f"isActive={current_metadata.get('isActive')}",
                    f"validationSuccess={(current_metadata.get('validationResult') or {}).get('success')}",
                    f"sandboxSuccess={(current_metadata.get('sandboxResult') or {}).get('success')}",
                ],
            )

        existing_tool_name = str(current_metadata.get("toolName") or paths.module_name)
        permission_level = _coerce_permission_level(
            current_metadata.get("permissionLevel", DEFAULT_PERMISSION_LEVEL)
        )
        sanitized_code = _sanitize_generated_code(python_code)
        _validate_python_syntax_or_raise(
            sanitized_code,
            ServerToolCreationRequest(
                tool_name=existing_tool_name,
                python_code=sanitized_code,
                permission_level=permission_level,
                project_id=str(project_id),
                creator_user_id=actor_user_id,
                chat_session_id=chat_session_id,
                plan_id=plan_id,
                run_id=run_id,
            ),
        )

        trace_id = _new_trace_id()
        staging_dir = paths.project_dir / ".staging" / trace_id
        staged_paths = ServerToolArtifactPaths(
            project_dir=staging_dir,
            module_path=staging_dir / paths.module_path.name,
            metadata_path=staging_dir / paths.metadata_path.name,
            module_name=paths.module_name,
        )
        staged_request = ServerToolCreationRequest(
            tool_name=existing_tool_name,
            python_code=sanitized_code,
            permission_level=permission_level,
            project_id=str(project_id),
            creator_user_id=actor_user_id,
            chat_session_id=chat_session_id,
            plan_id=plan_id,
            run_id=run_id,
        )
        staged_paths.project_dir.mkdir(parents=True, exist_ok=True)
        staged_paths.module_path.write_text(sanitized_code, encoding="utf-8")
        write_tool_metadata(
            staged_paths,
            _base_metadata(staged_request, staged_paths, tool_name=existing_tool_name),
        )

        tool_class = validate_draft_tool(staged_paths)
        if getattr(tool_class, "name", existing_tool_name) != existing_tool_name:
            message = (
                "custom_tool_update_source cannot rename a tool. "
                f"existing={existing_tool_name}, new={getattr(tool_class, 'name', None)}"
            )
            _record_stage_metadata(
                staged_paths,
                status=STATUS_VALIDATION_FAILED,
                trace_id=_new_trace_id(),
                metadata_patch=_validated_metadata(
                    success=False,
                    message=message,
                    checked_at=_now_iso(),
                ),
            )
            raise ToolCreationError("validation_failed", message, errors=[message])

        sandbox_result = await run_tool_sandbox_gate_for_artifact(staged_request, staged_paths)
        staged_metadata = read_tool_metadata(staged_paths)

        old_source = paths.module_path.read_text(encoding="utf-8")
        old_metadata = read_tool_metadata(paths)
        new_metadata = dict(old_metadata)
        new_metadata.update(metadata_patch or {})
        new_metadata.update(
            {
                "toolName": existing_tool_name,
                "moduleName": paths.module_name,
                "fileName": paths.module_path.name,
                "projectId": str(project_id),
                "permissionLevel": getattr(tool_class, "permission_level", permission_level),
                "status": STATUS_ACTIVE,
                "isActive": True,
                "validationResult": staged_metadata.get("validationResult"),
                "sandboxResult": sandbox_result,
                "sandboxVerified": True,
                "activationSource": "custom_tool_update_source",
                "latestTraceId": staged_metadata.get("latestTraceId"),
                "lastMaintainedAt": _now_iso(),
                "lastMaintainedBy": actor_user_id,
            }
        )

        try:
            paths.module_path.write_text(sanitized_code, encoding="utf-8")
            write_tool_metadata(paths, new_metadata)
        except Exception:
            paths.module_path.write_text(old_source, encoding="utf-8")
            write_tool_metadata(paths, old_metadata)
            raise

        registered = False
        for candidate_registry in (registry, active_registry):
            if candidate_registry is None:
                continue
            try:
                candidate_registry.register(tool_class())
                registered = True
            except Exception as exc:
                log.warning("Custom tool source updated but registry refresh failed: %s", exc)
        if tool_permissions is not None:
            tool_permissions[existing_tool_name] = getattr(
                tool_class,
                "permission_level",
                permission_level,
            )

        cleanup_result = cleanup_failed_tool_artifact(
            staged_paths,
            request=staged_request,
            failure_stage="maintenance_success_cleanup",
            failure_code="maintenance_success_cleanup",
            failure_message="Remove staged custom tool maintenance artifact after successful update.",
            storage_root=storage_root,
            require_request_match=True,
        )
        updated_metadata = read_tool_metadata(paths)
        return ServerToolSourceResult(
            status="updated",
            stage="completed",
            tool_name=existing_tool_name,
            message=(
                f"Custom tool '{existing_tool_name}' updated after ToolValidator "
                "and Core sandbox verification."
            ),
            project_id=str(project_id),
            module_name=paths.module_name,
            module_path=str(paths.module_path),
            metadata_path=str(paths.metadata_path),
            host_module_path=_host_custom_tool_path_hint(paths.module_path, storage_root=storage_root),
            host_metadata_path=_host_custom_tool_path_hint(paths.metadata_path, storage_root=storage_root),
            source=sanitized_code,
            metadata=updated_metadata,
            permission_level=getattr(tool_class, "permission_level", permission_level),
            registry_registered=registered,
            sandbox_verified=True,
            errors=[cleanup_report_line(cleanup_result)],
            trace_id=updated_metadata.get("latestTraceId"),
        )
    except ToolCreationError as exc:
        if staged_paths is not None:
            cleanup_result = cleanup_failed_tool_artifact(
                staged_paths,
                request=None,
                failure_stage=exc.stage,
                failure_code=exc.stage,
                failure_message=exc.message,
                storage_root=storage_root,
                require_request_match=False,
            )
        errors = list(exc.errors)
        if cleanup_result is not None:
            errors.append(cleanup_report_line(cleanup_result))
        return ServerToolSourceResult(
            status="rejected",
            stage=exc.stage,
            tool_name=_safe_tool_name(tool_name or module_name or "custom_tool"),
            message=exc.message,
            project_id=str(project_id),
            module_name=paths.module_name if paths is not None else str(module_name or ""),
            module_path=str(paths.module_path) if paths is not None else "",
            metadata_path=str(paths.metadata_path) if paths is not None else "",
            metadata=read_tool_metadata(paths) if paths is not None and paths.metadata_path.exists() else {},
            errors=errors,
            sandbox_verified=False,
        )
    except Exception as exc:
        if staged_paths is not None:
            cleanup_result = cleanup_failed_tool_artifact(
                staged_paths,
                request=None,
                failure_stage="unexpected",
                failure_code="unexpected",
                failure_message=str(exc),
                storage_root=storage_root,
                require_request_match=False,
            )
        errors = [str(exc)]
        if cleanup_result is not None:
            errors.append(cleanup_report_line(cleanup_result))
        return ServerToolSourceResult(
            status="rejected",
            stage="unexpected",
            tool_name=_safe_tool_name(tool_name or module_name or "custom_tool"),
            message=f"Unexpected custom tool source update failure: {exc}",
            project_id=str(project_id),
            module_name=paths.module_name if paths is not None else str(module_name or ""),
            module_path=str(paths.module_path) if paths is not None else "",
            metadata_path=str(paths.metadata_path) if paths is not None else "",
            metadata=read_tool_metadata(paths) if paths is not None and paths.metadata_path.exists() else {},
            errors=errors,
            sandbox_verified=False,
        )


def load_active_tools_for_project(
    registry: Any,
    *,
    project_id: str,
    tool_permissions: dict[str, int] | None = None,
    storage_root: Path = PROJECT_TOOLS_DIR,
    load_report: list[dict[str, Any]] | None = None,
) -> list[str]:
    project_dir = storage_root / _slugify_segment(project_id)
    if not project_dir.is_dir():
        log.info(
            "Project custom tools directory not found. projectId=%s dir=%s",
            project_id,
            project_dir,
        )
        return []

    loaded: list[str] = []
    for metadata_path in sorted(project_dir.glob("*.meta.json")):
        try:
            paths, metadata = _paths_from_project_metadata(project_dir, metadata_path)
        except Exception as exc:
            log.warning("Failed to read project tool metadata. meta=%s error=%s", metadata_path, exc)
            continue
        inventory_item = _project_tool_inventory_item(
            project_id=project_id,
            paths=paths,
            metadata=metadata,
        )
        if load_report is not None:
            load_report.append(inventory_item)
        if not paths.module_path.exists():
            log.warning(
                "Skipped project tool because module file is missing. projectId=%s meta=%s module=%s",
                project_id,
                metadata_path,
                paths.module_path,
            )
            continue
        if not _is_tool_active_metadata(metadata):
            log.info(
                "Skipped inactive or unverified project tool. projectId=%s toolName=%s status=%s isActive=%s",
                project_id,
                metadata.get("toolName"),
                metadata.get("status"),
                metadata.get("isActive"),
            )
            continue
        is_valid, _, tool_class = _tool_validator_cls().validate_and_load_module(
            paths.module_name,
            str(paths.module_path),
        )
        if not is_valid or tool_class is None:
            log.warning(
                "Skipped invalid project tool. projectId=%s module=%s file=%s",
                project_id,
                paths.module_name,
                paths.module_path,
            )
            continue
        try:
            instance = tool_class()
            setattr(instance, "_theseus_custom_tool", True)
            setattr(instance, "_theseus_project_id", project_id)
            registry.register(instance)
            loaded.append(tool_class.name)
            if tool_permissions is not None:
                tool_permissions[tool_class.name] = getattr(
                    tool_class,
                    "permission_level",
                    DEFAULT_PERMISSION_LEVEL,
                )
            log.info(
                "Loaded project custom tool. projectId=%s toolName=%s module=%s file=%s",
                project_id,
                tool_class.name,
                paths.module_name,
                paths.module_path,
            )
        except Exception as exc:
            log.warning(
                "Failed to instantiate project tool. projectId=%s module=%s error=%s",
                project_id,
                paths.module_name,
                exc,
            )
            continue
    return loaded


def load_custom_tools_for_project(
    registry: Any,
    *,
    project_id: str,
    tool_permissions: dict[str, int] | None = None,
    storage_root: Path = PROJECT_TOOLS_DIR,
    load_report: list[dict[str, Any]] | None = None,
) -> list[str]:
    return load_active_tools_for_project(
        registry,
        project_id=project_id,
        tool_permissions=tool_permissions,
        storage_root=storage_root,
        load_report=load_report,
    )
