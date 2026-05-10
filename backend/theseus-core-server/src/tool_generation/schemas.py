from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field


class ToolPermissionPayload(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    can_create_tool: bool = Field(alias="canCreateTool")
    can_use_tool: bool = Field(alias="canUseTool")
    can_update_tool: bool = Field(alias="canUpdateTool")
    can_delete_tool: bool = Field(alias="canDeleteTool")


class ToolFeedbackItem(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    block_id: str = Field(alias="blockId")
    comment: str


class ToolGenerationRequestEvent(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    event_type: Literal["TOOL_GENERATION_REQUESTED"] = Field(alias="eventType")
    run_id: str = Field(alias="runId")
    project_id: int = Field(alias="projectId")
    chat_session_id: int = Field(alias="chatSessionId")
    tool_id: int = Field(alias="toolId")
    requested_by_user_id: int = Field(alias="requestedByUserId")
    requested_by_project_member_id: int = Field(alias="requestedByProjectMemberId")
    prompt: str
    file_name: str = Field(alias="fileName")
    project_role: str = Field(alias="projectRole")
    tool_permission: ToolPermissionPayload = Field(alias="toolPermission")
    requested_at: datetime | None = Field(default=None, alias="requestedAt")


class ToolRegenerationRequestEvent(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    event_type: Literal["TOOL_REGENERATION_REQUESTED"] = Field(alias="eventType")
    run_id: str = Field(alias="runId")
    project_id: int = Field(alias="projectId")
    chat_session_id: int = Field(alias="chatSessionId")
    tool_id: int = Field(alias="toolId")
    requested_by_user_id: int = Field(alias="requestedByUserId")
    requested_by_project_member_id: int = Field(alias="requestedByProjectMemberId")
    base_draft_version: int | None = Field(default=None, alias="baseDraftVersion")
    feedback_items: list[ToolFeedbackItem] = Field(alias="feedbackItems")
    base_draft: Optional["ToolDraftPayload"] = Field(default=None, alias="baseDraft")
    project_role: str = Field(alias="projectRole")
    tool_permission: ToolPermissionPayload = Field(alias="toolPermission")
    requested_at: datetime | None = Field(default=None, alias="requestedAt")


class ToolDraftPayload(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    tool_id: int | None = Field(default=None, alias="toolId")
    project_id: int | None = Field(default=None, alias="projectId")
    chat_session_id: int | None = Field(default=None, alias="chatSessionId")
    raw_markdown: str | None = Field(default=None, alias="rawMarkdown")
    structured_plan_json: dict[str, Any] = Field(alias="structuredPlanJson")
    draft_snapshot: dict[str, Any] | None = Field(default=None, alias="draftSnapshot")
    draft_phase: str = Field(default="REVIEW", alias="draftPhase")

    @property
    def version(self) -> int | None:
        version = self.structured_plan_json.get("version")
        return int(version) if isinstance(version, int | str) and str(version).isdigit() else None


class PlanAiRequest(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    request_type: Literal["GENERATE_PLAN", "REGENERATE_PLAN"] = Field(alias="requestType")
    metadata: dict[str, Any]
    llm_input: dict[str, Any] = Field(alias="llmInput")
    output_contract: dict[str, bool] = Field(alias="outputContract")
    config: dict[str, Any]
    base_draft: dict[str, Any] | None = Field(default=None, alias="baseDraft")
    feedback: dict[str, Any] | None = None


class ToolPlanResult(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    raw_markdown: str = Field(alias="rawMarkdown")
    structured_plan_json: dict[str, Any] = Field(alias="structuredPlanJson")
    draft_snapshot: dict[str, Any] = Field(alias="draftSnapshot")


class AssistantMessagePayload(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    message_type: str = Field(alias="messageType")
    content_type: str = Field(alias="contentType")
    content: str


class ToolDraftResultPayload(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    raw_markdown: str = Field(alias="rawMarkdown")
    structured_plan_json: dict[str, Any] = Field(alias="structuredPlanJson")
    draft_snapshot: dict[str, Any] = Field(alias="draftSnapshot")


class ToolGenerationCompletedEvent(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    event_type: Literal["TOOL_GENERATION_COMPLETED"] = Field(
        default="TOOL_GENERATION_COMPLETED",
        alias="eventType",
    )
    run_id: str = Field(alias="runId")
    project_id: int = Field(alias="projectId")
    chat_session_id: int = Field(alias="chatSessionId")
    tool_id: int = Field(alias="toolId")
    assistant_message: AssistantMessagePayload = Field(alias="assistantMessage")
    tool_draft: ToolDraftResultPayload = Field(alias="toolDraft")
    completed_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc), alias="completedAt")


class ToolGenerationProgressEvent(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    event_type: Literal["progress"] = Field(default="progress", alias="eventType")
    run_id: str = Field(alias="runId")
    project_id: int = Field(alias="projectId")
    chat_session_id: int = Field(alias="chatSessionId")
    tool_id: int = Field(alias="toolId")
    message: str
    progress_rate: int = Field(alias="progressRate")


class ToolGenerationChunkEvent(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    event_type: Literal["chunk"] = Field(default="chunk", alias="eventType")
    run_id: str = Field(alias="runId")
    project_id: int = Field(alias="projectId")
    chat_session_id: int = Field(alias="chatSessionId")
    tool_id: int = Field(alias="toolId")
    content: str


class ToolGenerationFailedEvent(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    event_type: Literal["TOOL_GENERATION_FAILED"] = Field(
        default="TOOL_GENERATION_FAILED",
        alias="eventType",
    )
    run_id: str = Field(alias="runId")
    project_id: int = Field(alias="projectId")
    chat_session_id: int = Field(alias="chatSessionId")
    tool_id: int = Field(alias="toolId")
    code: str
    message: str
    failed_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc), alias="failedAt")
