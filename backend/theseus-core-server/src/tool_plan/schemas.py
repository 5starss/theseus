from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


class ConversationHistoryItem(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    role: str
    message_type: str | None = Field(default=None, alias="messageType")
    content_type: str | None = Field(default=None, alias="contentType")
    content: str | dict[str, Any] | list[Any] | None = None


class ToolPlanFeedbackItem(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    block_id: str = Field(alias="blockId")
    comment: str


class BaseToolPlanPayload(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    raw_markdown: str = Field(default="", alias="rawMarkdown")
    structured_plan_json: dict[str, Any] = Field(default_factory=dict, alias="structuredPlanJson")
    plan_snapshot: dict[str, Any] = Field(default_factory=dict, alias="planSnapshot")


class ToolPlanRequestedEvent(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    event_type: Literal["TOOL_PLAN_REQUESTED"] = Field(alias="eventType")
    mode: Literal["PLAN"] = "PLAN"
    run_id: str = Field(alias="runId")
    project_id: int = Field(alias="projectId")
    chat_session_id: int = Field(alias="chatSessionId")
    requested_by_user_id: int = Field(alias="requestedByUserId")
    requested_by_project_member_id: int = Field(alias="requestedByProjectMemberId")
    prompt: str
    history: list[ConversationHistoryItem] = Field(default_factory=list)
    remote_workspace_id: int | None = Field(default=None, alias="remoteWorkspaceId")
    requested_at: datetime = Field(alias="requestedAt")


class ToolPlanRegenerationRequestedEvent(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    event_type: Literal["TOOL_PLAN_REGENERATION_REQUESTED"] = Field(alias="eventType")
    mode: Literal["PLAN"] = "PLAN"
    run_id: str = Field(alias="runId")
    project_id: int = Field(alias="projectId")
    chat_session_id: int = Field(alias="chatSessionId")
    base_tool_plan_id: int = Field(alias="baseToolPlanId")
    plan_group_id: int = Field(alias="planGroupId")
    base_plan_version: int = Field(alias="basePlanVersion")
    base_plan: BaseToolPlanPayload = Field(alias="basePlan")
    feedback_items: list[ToolPlanFeedbackItem] = Field(alias="feedbackItems")
    history: list[ConversationHistoryItem] = Field(default_factory=list)
    remote_workspace_id: int | None = Field(default=None, alias="remoteWorkspaceId")
    requested_at: datetime = Field(alias="requestedAt")


ToolPlanRequestEvent = ToolPlanRequestedEvent | ToolPlanRegenerationRequestedEvent


class AssistantMessagePayload(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    message_type: str = Field(alias="messageType")
    content_type: str = Field(alias="contentType")
    content: str


class ToolPlanPayload(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    raw_markdown: str = Field(alias="rawMarkdown")
    structured_plan_json: dict[str, Any] = Field(alias="structuredPlanJson")
    plan_snapshot: dict[str, Any] = Field(alias="planSnapshot")


class GeneratedPlanBlock(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    block_id: str | None = Field(default=None, alias="blockId")
    title: str
    content: str
    order: int | None = None


class GeneratedToolPlan(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    intent: Literal["TOOL_PLAN", "SKIP"]
    skip_message: str | None = Field(default=None, alias="skipMessage")
    title: str | None = None
    summary: str | None = None
    blocks: list[GeneratedPlanBlock] = Field(default_factory=list)
    inputs: list[dict[str, Any]] = Field(default_factory=list)
    outputs: list[dict[str, Any]] = Field(default_factory=list)
    constraints: list[str] = Field(default_factory=list)


class ToolPlanResult(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    raw_markdown: str = Field(alias="rawMarkdown")
    structured_plan_json: dict[str, Any] = Field(alias="structuredPlanJson")
    plan_snapshot: dict[str, Any] = Field(alias="planSnapshot")


class ToolPlanSkippedResult(BaseModel):
    message: str


class ToolPlanProgressEvent(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    event_type: Literal["progress"] = Field(default="progress", alias="eventType")
    run_id: str = Field(alias="runId")
    event_sequence: int = Field(alias="eventSequence")
    project_id: int = Field(alias="projectId")
    chat_session_id: int = Field(alias="chatSessionId")
    message: str
    progress_rate: int | None = Field(default=None, alias="progressRate")


class ToolPlanChunkEvent(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    event_type: Literal["chunk"] = Field(default="chunk", alias="eventType")
    run_id: str = Field(alias="runId")
    event_sequence: int = Field(alias="eventSequence")
    project_id: int = Field(alias="projectId")
    chat_session_id: int = Field(alias="chatSessionId")
    content: str


class ToolPlanCompletedEvent(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    event_type: Literal["TOOL_PLAN_COMPLETED"] = Field(default="TOOL_PLAN_COMPLETED", alias="eventType")
    run_id: str = Field(alias="runId")
    event_sequence: int = Field(alias="eventSequence")
    project_id: int = Field(alias="projectId")
    chat_session_id: int = Field(alias="chatSessionId")
    assistant_message: AssistantMessagePayload = Field(alias="assistantMessage")
    tool_plan: ToolPlanPayload = Field(alias="toolPlan")
    completed_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc), alias="completedAt")


class ToolPlanSkippedEvent(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    event_type: Literal["TOOL_PLAN_SKIPPED"] = Field(default="TOOL_PLAN_SKIPPED", alias="eventType")
    run_id: str = Field(alias="runId")
    event_sequence: int = Field(alias="eventSequence")
    project_id: int = Field(alias="projectId")
    chat_session_id: int = Field(alias="chatSessionId")
    assistant_message: AssistantMessagePayload = Field(alias="assistantMessage")
    completed_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc), alias="completedAt")


class ToolPlanFailedEvent(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    event_type: Literal["TOOL_PLAN_FAILED"] = Field(default="TOOL_PLAN_FAILED", alias="eventType")
    run_id: str = Field(alias="runId")
    event_sequence: int = Field(alias="eventSequence")
    project_id: int = Field(alias="projectId")
    chat_session_id: int = Field(alias="chatSessionId")
    code: str
    message: str
    failed_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc), alias="failedAt")
