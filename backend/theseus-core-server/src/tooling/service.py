from __future__ import annotations

import json
import logging
import re
import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

log = logging.getLogger(__name__)

DEFAULT_PERMISSION_LEVEL = 1
CUSTOM_TOOLS_DIR = (
    Path(__file__).resolve().parents[2] / "theseus_engine" / "custom_tools"
)
PROJECT_TOOLS_DIR = CUSTOM_TOOLS_DIR / "projects"
TOOL_NAME_PATTERN = re.compile(r"^[a-z][a-z0-9_]{2,63}$")

STATUS_DRAFT_SAVED = "draft_saved"
STATUS_VALIDATED = "validated"
STATUS_VALIDATION_FAILED = "validation_failed"
STATUS_SANDBOX_PASSED = "sandbox_passed"
STATUS_SANDBOX_FAILED = "sandbox_failed"
STATUS_ACTIVE = "active"


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


def _slugify_segment(value: str) -> str:
    slug = re.sub(r"[^a-zA-Z0-9]+", "_", value).strip("_").lower()
    return slug or "default"


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _new_trace_id() -> str:
    return uuid.uuid4().hex


def _audit_log(event: str, **payload: Any) -> None:
    log.info("[ToolAudit] %s %s", event, json.dumps(payload, ensure_ascii=False, sort_keys=True))


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


def build_tool_paths(
    project_id: str,
    tool_name: str,
    *,
    storage_root: Path = PROJECT_TOOLS_DIR,
) -> ServerToolArtifactPaths:
    safe_project_id = _slugify_segment(project_id)
    project_dir = storage_root / safe_project_id
    module_path = project_dir / f"{tool_name}.py"
    metadata_path = project_dir / f"{tool_name}.meta.json"
    module_name = f"{safe_project_id}__{tool_name}"
    return ServerToolArtifactPaths(
        project_dir=project_dir,
        module_path=module_path,
        metadata_path=metadata_path,
        module_name=module_name,
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
    normalized_name = normalize_tool_name(request.tool_name)
    code = inject_permission_level(request.python_code, request.permission_level)
    paths = build_tool_paths(request.project_id, normalized_name, storage_root=storage_root)
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
    status = STATUS_SANDBOX_PASSED if result["success"] else STATUS_SANDBOX_FAILED
    _record_stage_metadata(
        paths,
        status=status,
        trace_id=trace_id,
        metadata_patch=_sandbox_metadata(result),
    )
    if not result["success"]:
        raise ToolCreationError(
            "sandbox_failed",
            result.get("error") or "Sandbox gate failed.",
            errors=[result.get("error") or "Sandbox gate failed."],
        )
    return result


def activate_tool_artifact(
    request: ServerToolCreationRequest,
    paths: ServerToolArtifactPaths,
    *,
    tool_class: type[Any],
    registry: Any | None,
    tool_permissions: dict[str, int] | None,
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
        return ServerToolCreationResult(
            status="rejected",
            stage=exc.stage,
            tool_name=_safe_tool_name(request.tool_name),
            message=exc.message,
            module_path=str(paths.module_path) if paths is not None else None,
            metadata_path=str(paths.metadata_path) if paths is not None else None,
            errors=exc.errors,
            trace_id=read_tool_metadata(paths).get("latestTraceId")
            if paths is not None and paths.metadata_path.exists()
            else None,
        )
    except Exception as exc:
        if paths is not None and paths.metadata_path.exists():
            metadata = read_tool_metadata(paths)
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
        return ServerToolCreationResult(
            status="rejected",
            stage="unexpected",
            tool_name=_safe_tool_name(request.tool_name),
            message=f"Unexpected tool creation failure: {exc}",
            module_path=str(paths.module_path) if paths is not None else None,
            metadata_path=str(paths.metadata_path) if paths is not None else None,
            errors=[str(exc)],
            trace_id=read_tool_metadata(paths).get("latestTraceId")
            if paths is not None and paths.metadata_path.exists()
            else None,
        )


def load_active_tools_for_project(
    registry: Any,
    *,
    project_id: str,
    tool_permissions: dict[str, int] | None = None,
    storage_root: Path = PROJECT_TOOLS_DIR,
) -> list[str]:
    project_dir = storage_root / _slugify_segment(project_id)
    if not project_dir.is_dir():
        return []

    loaded: list[str] = []
    for metadata_path in sorted(project_dir.glob("*.meta.json")):
        tool_name = metadata_path.stem.replace(".meta", "")
        paths = ServerToolArtifactPaths(
            project_dir=project_dir,
            module_path=project_dir / f"{tool_name}.py",
            metadata_path=metadata_path,
            module_name=f"{_slugify_segment(project_id)}__{tool_name}",
        )
        if not paths.module_path.exists():
            continue
        try:
            metadata = read_tool_metadata(paths)
        except Exception:
            continue
        if not _is_tool_active_metadata(metadata):
            continue
        is_valid, _, tool_class = _tool_validator_cls().validate_and_load_module(
            paths.module_name,
            str(paths.module_path),
        )
        if not is_valid or tool_class is None:
            continue
        try:
            registry.register(tool_class())
            loaded.append(tool_class.name)
            if tool_permissions is not None:
                tool_permissions[tool_class.name] = getattr(
                    tool_class,
                    "permission_level",
                    DEFAULT_PERMISSION_LEVEL,
                )
        except Exception:
            continue
    return loaded


def load_custom_tools_for_project(
    registry: Any,
    *,
    project_id: str,
    tool_permissions: dict[str, int] | None = None,
    storage_root: Path = PROJECT_TOOLS_DIR,
) -> list[str]:
    return load_active_tools_for_project(
        registry,
        project_id=project_id,
        tool_permissions=tool_permissions,
        storage_root=storage_root,
    )
