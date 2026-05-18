"""Project custom tool source maintenance tools."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field

from theseus_engine.tools.core.base_tools import BaseTool, ToolExecutionContext, ToolResult


def _metadata_project_id(context: ToolExecutionContext, explicit: str | None) -> str | None:
    value = str(explicit or "").strip()
    if value:
        return value
    for key in ("project_id", "projectId"):
        raw = context.metadata.get(key)
        if raw is not None and str(raw).strip():
            return str(raw).strip()
    return None


def _metadata_int(context: ToolExecutionContext, key: str, default: int = 0) -> int:
    try:
        return int(context.metadata.get(key, default) or default)
    except (TypeError, ValueError):
        return default


class CustomToolReadSourceInput(BaseModel):
    project_id: str | None = Field(
        default=None,
        description="Project id. Defaults to the current runtime project context.",
    )
    tool_name: str | None = Field(
        default=None,
        description="Logical tool name such as ram_monitor.",
    )
    module_name: str | None = Field(
        default=None,
        description="Persisted module name such as ram_monitor_tool.",
    )


class CustomToolReadSourceTool(BaseTool):
    name = "custom_tool_read_source"
    description = (
        "Read an existing project custom tool source and metadata by project/tool "
        "identity. Use this instead of read_file for custom tool artifacts."
    )
    input_model = CustomToolReadSourceInput
    permission_level = 2

    def is_read_only(self, arguments: BaseModel) -> bool:
        return True

    async def execute(
        self,
        arguments: CustomToolReadSourceInput,
        context: ToolExecutionContext,
    ) -> ToolResult:
        project_id = _metadata_project_id(context, arguments.project_id)
        if not project_id:
            return ToolResult(
                output="custom_tool_read_source requires project_id or runtime project context.",
                is_error=True,
            )
        if not (arguments.tool_name or arguments.module_name):
            return ToolResult(
                output="custom_tool_read_source requires tool_name or module_name.",
                is_error=True,
            )

        try:
            from src.tooling import read_project_tool_source
        except Exception as exc:
            return ToolResult(
                output=f"Server custom tool source service is unavailable: {exc}",
                is_error=True,
            )

        result = read_project_tool_source(
            project_id=project_id,
            tool_name=arguments.tool_name,
            module_name=arguments.module_name,
        )
        payload = {
            "status": result.status,
            "stage": result.stage,
            "message": result.message,
            "toolName": result.tool_name,
            "projectId": result.project_id,
            "moduleName": result.module_name,
            "modulePath": result.module_path,
            "metadataPath": result.metadata_path,
            "hostModulePath": result.host_module_path,
            "hostMetadataPath": result.host_metadata_path,
            "sandboxVerified": result.sandbox_verified,
            "metadata": result.metadata,
            "source": result.source,
            "errors": result.errors,
        }
        return ToolResult(
            output=payload,
            is_error=result.status == "rejected",
            metadata=result.to_metadata(),
        )


class CustomToolUpdateSourceInput(BaseModel):
    project_id: str | None = Field(
        default=None,
        description="Project id. Defaults to the current runtime project context.",
    )
    tool_name: str | None = Field(
        default=None,
        description="Logical tool name such as ram_monitor.",
    )
    module_name: str | None = Field(
        default=None,
        description="Persisted module name such as ram_monitor_tool.",
    )
    python_code: str = Field(
        description="Complete replacement Python source for the existing custom tool.",
    )
    metadata_json: dict[str, Any] | None = Field(
        default=None,
        description="Optional metadata fields to merge after validation and sandbox success.",
    )


class CustomToolUpdateSourceTool(BaseTool):
    name = "custom_tool_update_source"
    description = (
        "Safely update an existing project custom tool source by project/tool "
        "identity. The replacement is staged, validated, sandbox-verified, then "
        "atomically applied. Use this instead of edit_file for custom tool artifacts."
    )
    input_model = CustomToolUpdateSourceInput
    permission_level = 3
    is_destructive = True

    def is_read_only(self, arguments: BaseModel) -> bool:
        return False

    async def execute(
        self,
        arguments: CustomToolUpdateSourceInput,
        context: ToolExecutionContext,
    ) -> ToolResult:
        project_id = _metadata_project_id(context, arguments.project_id)
        if not project_id:
            return ToolResult(
                output="custom_tool_update_source requires project_id or runtime project context.",
                is_error=True,
            )
        if not (arguments.tool_name or arguments.module_name):
            return ToolResult(
                output="custom_tool_update_source requires tool_name or module_name.",
                is_error=True,
            )

        try:
            from src.tooling import update_project_tool_source
        except Exception as exc:
            return ToolResult(
                output=f"Server custom tool source service is unavailable: {exc}",
                is_error=True,
            )

        result = await update_project_tool_source(
            project_id=project_id,
            tool_name=arguments.tool_name,
            module_name=arguments.module_name,
            python_code=arguments.python_code,
            actor_user_id=str(context.metadata.get("user_id") or "runtime"),
            chat_session_id=_metadata_int(context, "chat_session_id", 0),
            plan_id=str(context.metadata.get("plan_id") or "custom_tool_maintenance"),
            run_id=context.run_id,
            registry=context.metadata.get("tool_registry"),
            active_registry=context.metadata.get("active_registry"),
            tool_permissions=context.metadata.get("tool_permissions"),
            metadata_patch=arguments.metadata_json,
        )
        payload = {
            "status": result.status,
            "stage": result.stage,
            "message": result.message,
            "toolName": result.tool_name,
            "projectId": result.project_id,
            "moduleName": result.module_name,
            "modulePath": result.module_path,
            "metadataPath": result.metadata_path,
            "hostModulePath": result.host_module_path,
            "hostMetadataPath": result.host_metadata_path,
            "sandboxVerified": result.sandbox_verified,
            "registryRegistered": result.registry_registered,
            "metadata": result.metadata,
            "errors": result.errors,
        }
        return ToolResult(
            output=payload,
            is_error=result.status == "rejected",
            metadata=result.to_metadata(),
        )
