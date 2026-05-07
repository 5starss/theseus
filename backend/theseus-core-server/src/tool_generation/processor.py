from __future__ import annotations

import logging
from inspect import signature
from typing import Any

from pydantic import ValidationError

from src.tool_generation.plan_generator import ToolPlanGenerator
from src.tool_generation.publisher import ToolGenerationEventPublisher
from src.tool_generation.schemas import (
    AssistantMessagePayload,
    PlanAiRequest,
    ToolDraftResultPayload,
    ToolGenerationChunkEvent,
    ToolGenerationCompletedEvent,
    ToolGenerationFailedEvent,
    ToolGenerationProgressEvent,
    ToolGenerationRequestEvent,
    ToolPermissionPayload,
    ToolPlanResult,
    ToolRegenerationRequestEvent,
)

logger = logging.getLogger(__name__)

OUTPUT_CONTRACT = {
    "rawMarkdownRequired": True,
    "structuredPlanJsonRequired": True,
    "blockIdRequired": True,
}


class ToolGenerationProcessor:
    def __init__(
        self,
        *,
        publisher: ToolGenerationEventPublisher,
        generator: ToolPlanGenerator | None = None,
    ) -> None:
        self.publisher = publisher
        self.generator = generator or ToolPlanGenerator()

    async def process_message(self, payload: dict[str, Any]) -> None:
        event_type = payload.get("eventType")
        try:
            if event_type == "TOOL_GENERATION_REQUESTED":
                await self.process_generation(ToolGenerationRequestEvent.model_validate(payload))
            elif event_type == "TOOL_REGENERATION_REQUESTED":
                await self.process_regeneration(ToolRegenerationRequestEvent.model_validate(payload))
            else:
                logger.warning("Unsupported Tool generation eventType=%s", event_type)
        except ValidationError as exc:
            logger.error("Invalid Tool generation Kafka payload: %s", exc)

    async def process_generation(self, event: ToolGenerationRequestEvent) -> None:
        try:
            ai_request = self.build_generation_ai_request(event)
            result = await self.generate_with_callbacks(event, ai_request)
            await self.publish_completed(event, result, assistant_message_type="TOOL_DRAFT_RESPONSE")
        except Exception as exc:
            logger.error("Tool PLAN generation failed. runId=%s error=%s", event.run_id, exc, exc_info=True)
            await self.publish_failed(event, "AI_GENERATION_FAILED", str(exc))

    async def process_regeneration(self, event: ToolRegenerationRequestEvent) -> None:
        try:
            base_draft = event.base_draft
            if base_draft is None:
                raise ValueError("Base draft payload is missing from regeneration request event")
            self.validate_base_draft_version(event, base_draft)
            ai_request = self.build_regeneration_ai_request(event, base_draft)
            result = await self.generate_with_callbacks(event, ai_request)
            await self.publish_completed(event, result, assistant_message_type="TOOL_REGENERATE_RESPONSE")
        except Exception as exc:
            logger.error("Tool PLAN regeneration failed. runId=%s error=%s", event.run_id, exc, exc_info=True)
            await self.publish_failed(event, "AI_REGENERATION_FAILED", str(exc))

    def build_generation_ai_request(self, event: ToolGenerationRequestEvent) -> PlanAiRequest:
        return PlanAiRequest(
            requestType="GENERATE_PLAN",
            metadata=self.build_metadata(event),
            llmInput={
                "user_message": event.prompt,
                "history": [],
            },
            outputContract=OUTPUT_CONTRACT,
            config={"stream": True},
        )

    def build_regeneration_ai_request(
        self,
        event: ToolRegenerationRequestEvent,
        base_draft,
    ) -> PlanAiRequest:
        return PlanAiRequest(
            requestType="REGENERATE_PLAN",
            metadata=self.build_metadata(event),
            llmInput={
                "user_message": "PLAN block feedback has been requested.",
                "history": [],
            },
            baseDraft=base_draft.structured_plan_json,
            feedback={
                "baseDraftVersion": event.base_draft_version,
                "feedbackItems": [
                    item.model_dump(mode="json", by_alias=True)
                    for item in event.feedback_items
                ],
                "instruction": (
                    "Regenerate the full PLAN, focusing on commented blocks, "
                    "and preserve requirements that were not mentioned."
                ),
            },
            outputContract=OUTPUT_CONTRACT,
            config={"stream": True},
        )

    def build_metadata(self, event: ToolGenerationRequestEvent | ToolRegenerationRequestEvent) -> dict[str, Any]:
        return {
            "runId": event.run_id,
            "userId": event.requested_by_user_id,
            "projectId": event.project_id,
            "chatSessionId": event.chat_session_id,
            "toolId": event.tool_id,
            "projectRole": event.project_role,
            "permissions": self.permissions_to_json(event.tool_permission),
        }

    async def generate_with_callbacks(
        self,
        event: ToolGenerationRequestEvent | ToolRegenerationRequestEvent,
        ai_request: PlanAiRequest,
    ) -> ToolPlanResult:
        generator_params = signature(self.generator.generate).parameters
        if "progress_callback" in generator_params or "chunk_callback" in generator_params:
            return await self.generator.generate(
                ai_request,
                progress_callback=lambda message, rate: self.publish_progress(event, message, rate),
                chunk_callback=lambda content: self.publish_chunk(event, content),
            )
        return await self.generator.generate(ai_request)

    def validate_base_draft_version(
        self,
        event: ToolRegenerationRequestEvent,
        base_draft,
    ) -> None:
        if event.base_draft_version is None:
            return
        if base_draft.version != event.base_draft_version:
            raise ValueError(
                f"Base draft version mismatch. requested={event.base_draft_version}, current={base_draft.version}"
            )

    async def publish_progress(
        self,
        event: ToolGenerationRequestEvent | ToolRegenerationRequestEvent,
        message: str,
        progress_rate: int,
    ) -> None:
        progress = ToolGenerationProgressEvent(
            runId=event.run_id,
            projectId=event.project_id,
            chatSessionId=event.chat_session_id,
            toolId=event.tool_id,
            message=message,
            progressRate=max(0, min(progress_rate, 99)),
        )
        await self.publisher.publish(event.run_id, progress)

    async def publish_chunk(
        self,
        event: ToolGenerationRequestEvent | ToolRegenerationRequestEvent,
        content: str,
    ) -> None:
        chunk = ToolGenerationChunkEvent(
            runId=event.run_id,
            projectId=event.project_id,
            chatSessionId=event.chat_session_id,
            toolId=event.tool_id,
            content=content,
        )
        await self.publisher.publish(event.run_id, chunk)

    async def publish_completed(
        self,
        event: ToolGenerationRequestEvent | ToolRegenerationRequestEvent,
        result: ToolPlanResult,
        *,
        assistant_message_type: str,
    ) -> None:
        completed = ToolGenerationCompletedEvent(
            runId=event.run_id,
            projectId=event.project_id,
            chatSessionId=event.chat_session_id,
            toolId=event.tool_id,
            assistantMessage=AssistantMessagePayload(
                messageType=assistant_message_type,
                contentType="MARKDOWN",
                content=result.raw_markdown,
            ),
            toolDraft=ToolDraftResultPayload(
                rawMarkdown=result.raw_markdown,
                structuredPlanJson=result.structured_plan_json,
                draftSnapshot=result.draft_snapshot,
            ),
        )
        await self.publisher.publish(event.run_id, completed)

    async def publish_failed(
        self,
        event: ToolGenerationRequestEvent | ToolRegenerationRequestEvent,
        code: str,
        message: str,
    ) -> None:
        failed = ToolGenerationFailedEvent(
            runId=event.run_id,
            projectId=event.project_id,
            chatSessionId=event.chat_session_id,
            toolId=event.tool_id,
            code=code,
            message=message,
        )
        await self.publisher.publish(event.run_id, failed)

    @staticmethod
    def permissions_to_json(permission: ToolPermissionPayload) -> dict[str, bool]:
        return permission.model_dump(mode="json", by_alias=True)
