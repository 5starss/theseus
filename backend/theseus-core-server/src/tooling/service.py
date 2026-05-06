from __future__ import annotations

import json
import re
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

DEFAULT_PERMISSION_LEVEL = 1
CUSTOM_TOOLS_DIR = (
    Path(__file__).resolve().parents[2] / "theseus_engine" / "custom_tools"
)
PROJECT_TOOLS_DIR = CUSTOM_TOOLS_DIR / "projects"
TOOL_NAME_PATTERN = re.compile(r"^[a-z][a-z0-9_]{2,63}$")


def _tool_validator_cls():
    from theseus_engine.tools.core.tool_factory import ToolValidator

    return ToolValidator


def _session_local_factory():
    from src.db.postgres import SessionLocal

    return SessionLocal


def _assert_plan_execution_context(*args, **kwargs):
    from src.plan.service import assert_plan_execution_context

    return assert_plan_execution_context(*args, **kwargs)


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

    def to_metadata(self) -> dict[str, Any]:
        return asdict(self)


def _slugify_segment(value: str) -> str:
    slug = re.sub(r"[^a-zA-Z0-9]+", "_", value).strip("_").lower()
    return slug or "default"


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


def validate_tool_source(
    tool_name: str,
    python_code: str,
    permission_level: int,
) -> tuple[str, str]:
    normalized_name = normalize_tool_name(tool_name)
    normalized_code = inject_permission_level(python_code, permission_level)
    is_valid, message = _tool_validator_cls().validate_code(normalized_code)
    if not is_valid:
        raise ToolCreationError("code_validation", message, errors=[message])
    return normalized_name, normalized_code


def persist_tool_source(
    request: ServerToolCreationRequest,
    *,
    storage_root: Path = PROJECT_TOOLS_DIR,
) -> tuple[ServerToolArtifactPaths, str]:
    normalized_name, code = validate_tool_source(
        request.tool_name,
        request.python_code,
        request.permission_level,
    )
    paths = build_tool_paths(request.project_id, normalized_name, storage_root=storage_root)
    paths.project_dir.mkdir(parents=True, exist_ok=True)
    paths.module_path.write_text(code, encoding="utf-8")
    return paths, code


def validate_saved_tool(paths: ServerToolArtifactPaths) -> type[Any]:
    is_valid, message, tool_class = _tool_validator_cls().validate_and_load_module(
        paths.module_name,
        str(paths.module_path),
    )
    if not is_valid or tool_class is None:
        try:
            paths.module_path.unlink(missing_ok=True)
        finally:
            paths.metadata_path.unlink(missing_ok=True)
        raise ToolCreationError("module_validation", message, errors=[message])
    return tool_class


def write_tool_metadata(
    request: ServerToolCreationRequest,
    paths: ServerToolArtifactPaths,
    *,
    tool_class: type[Any],
) -> None:
    metadata = {
        "toolName": getattr(tool_class, "name", request.tool_name),
        "moduleName": paths.module_name,
        "projectId": request.project_id,
        "chatSessionId": request.chat_session_id,
        "creatorUserId": request.creator_user_id,
        "planId": request.plan_id,
        "fileName": paths.module_path.name,
        "createdAt": datetime.now(timezone.utc).isoformat(),
        "permissionLevel": getattr(
            tool_class,
            "permission_level",
            request.permission_level,
        ),
        "approvalHistory": [
            {
                "planId": request.plan_id,
                "status": "approved_for_execution",
                "actorUserId": request.creator_user_id,
                "chatSessionId": request.chat_session_id,
                "recordedAt": datetime.now(timezone.utc).isoformat(),
            }
        ],
    }
    paths.metadata_path.write_text(
        json.dumps(metadata, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def register_tool_artifact(
    *,
    tool_class: type[Any],
    registry: Any | None,
    tool_permissions: dict[str, int] | None,
    requested_permission_level: int,
) -> bool:
    if registry is None:
        return False

    instance = tool_class()
    registry.register(instance)
    if tool_permissions is not None:
        tool_permissions[tool_class.name] = getattr(
            tool_class,
            "permission_level",
            requested_permission_level,
        )
    return True


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


def create_tool_for_server(
    request: ServerToolCreationRequest,
    *,
    registry: Any | None = None,
    tool_permissions: dict[str, int] | None = None,
    storage_root: Path = PROJECT_TOOLS_DIR,
) -> ServerToolCreationResult:
    paths: ServerToolArtifactPaths | None = None
    try:
        _assert_plan_guard(request)
        paths, _ = persist_tool_source(request, storage_root=storage_root)
        tool_class = validate_saved_tool(paths)
        write_tool_metadata(request, paths, tool_class=tool_class)
        registered = register_tool_artifact(
            tool_class=tool_class,
            registry=registry,
            tool_permissions=tool_permissions,
            requested_permission_level=request.permission_level,
        )
        return ServerToolCreationResult(
            status="created",
            stage="completed",
            tool_name=tool_class.name,
            message=(
                f"Tool '{tool_class.name}' created for project '{request.project_id}'. "
                "It will be available on the next server request."
            ),
            module_path=str(paths.module_path),
            metadata_path=str(paths.metadata_path),
            permission_level=getattr(
                tool_class,
                "permission_level",
                request.permission_level,
            ),
            registry_registered=registered,
        )
    except ToolCreationError as exc:
        return ServerToolCreationResult(
            status="rejected",
            stage=exc.stage,
            tool_name=request.tool_name,
            message=exc.message,
            errors=exc.errors,
        )
    except Exception as exc:
        if paths is not None:
            paths.module_path.unlink(missing_ok=True)
            paths.metadata_path.unlink(missing_ok=True)
        return ServerToolCreationResult(
            status="rejected",
            stage="unexpected",
            tool_name=request.tool_name,
            message=f"Unexpected tool creation failure: {exc}",
            errors=[str(exc)],
        )


def load_custom_tools_for_project(
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
    for module_path in sorted(project_dir.glob("*.py")):
        paths = ServerToolArtifactPaths(
            project_dir=project_dir,
            module_path=module_path,
            metadata_path=project_dir / f"{module_path.stem}.meta.json",
            module_name=f"{_slugify_segment(project_id)}__{module_path.stem}",
        )
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
