from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


class ApprovedPlanPayload(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    raw_markdown: str = Field(alias="rawMarkdown")
    structured_plan_json: dict[str, Any] = Field(alias="structuredPlanJson")
    plan_snapshot: dict[str, Any] = Field(alias="planSnapshot")


class ToolBuildRequestedEvent(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    event_type: Literal["TOOL_BUILD_REQUESTED"] = Field(alias="eventType")
    run_id: str = Field(alias="runId")
    project_id: int = Field(alias="projectId")
    chat_session_id: int = Field(alias="chatSessionId")
    tool_plan_id: int = Field(alias="toolPlanId")
    plan_group_id: int = Field(alias="planGroupId")
    approved_by_project_member_id: int = Field(alias="approvedByProjectMemberId")
    approved_plan: ApprovedPlanPayload = Field(alias="approvedPlan")
    requested_at: datetime = Field(alias="requestedAt")


class GeneratedToolSpec(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    tool_name: str = Field(alias="toolName")
    file_name: str | None = Field(default=None, alias="fileName")
    module_name: str | None = Field(default=None, alias="moduleName")
    display_name: str | None = Field(default=None, alias="displayName")
    display_description: str | None = Field(default=None, alias="displayDescription")
    permission_level: int = Field(default=1, alias="permissionLevel")
    python_code: str = Field(alias="pythonCode")
    metadata_json: dict[str, Any] = Field(default_factory=dict, alias="metadataJson")


class ToolArtifactPayload(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    file_name: str = Field(alias="fileName")
    module_name: str | None = Field(default=None, alias="moduleName")
    artifact_path: str | None = Field(default=None, alias="artifactPath")
    code_snapshot: str | None = Field(default=None, alias="codeSnapshot")
    metadata_json: dict[str, Any] | None = Field(default=None, alias="metadataJson")
    display_name: str | None = Field(default=None, alias="displayName")
    display_description: str | None = Field(default=None, alias="displayDescription")
    permission_level: int | None = Field(default=None, alias="permissionLevel")


class ToolBuildProgressEvent(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    event_type: Literal["progress"] = Field(default="progress", alias="eventType")
    run_id: str = Field(alias="runId")
    event_sequence: int = Field(alias="eventSequence")
    project_id: int = Field(alias="projectId")
    chat_session_id: int = Field(alias="chatSessionId")
    tool_plan_id: int = Field(alias="toolPlanId")
    message: str
    progress_rate: int | None = Field(default=None, alias="progressRate")


class ToolBuildChunkEvent(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    event_type: Literal["chunk"] = Field(default="chunk", alias="eventType")
    run_id: str = Field(alias="runId")
    event_sequence: int = Field(alias="eventSequence")
    project_id: int = Field(alias="projectId")
    chat_session_id: int = Field(alias="chatSessionId")
    tool_plan_id: int = Field(alias="toolPlanId")
    content: str


class ToolBuildCompletedEvent(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    event_type: Literal["TOOL_BUILD_COMPLETED"] = Field(default="TOOL_BUILD_COMPLETED", alias="eventType")
    run_id: str = Field(alias="runId")
    event_sequence: int = Field(alias="eventSequence")
    project_id: int = Field(alias="projectId")
    chat_session_id: int = Field(alias="chatSessionId")
    tool_plan_id: int = Field(alias="toolPlanId")
    artifact: ToolArtifactPayload
    completed_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc), alias="completedAt")


class ToolBuildFailedEvent(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    event_type: Literal["TOOL_BUILD_FAILED"] = Field(default="TOOL_BUILD_FAILED", alias="eventType")
    run_id: str = Field(alias="runId")
    event_sequence: int = Field(alias="eventSequence")
    project_id: int = Field(alias="projectId")
    chat_session_id: int = Field(alias="chatSessionId")
    tool_plan_id: int = Field(alias="toolPlanId")
    code: str
    message: str
    failed_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc), alias="failedAt")
