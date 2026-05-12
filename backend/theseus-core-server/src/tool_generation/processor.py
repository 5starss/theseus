from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any

from pydantic import ValidationError

from src.tool_generation.publisher import ToolGenerationEventPublisher
from src.tool_generation.schemas import (
    AssistantMessagePayload,
    LegacyToolGenerationRequestEvent,
    ToolDraftResultPayload,
    ToolGenerationChunkEvent,
    ToolGenerationCompletedEvent,
    ToolGenerationFailedEvent,
    ToolGenerationProgressEvent,
    ToolGenerationRequestEvent,
    ToolRegenerationRequestEvent,
)
from src.tool_plan.planner import ToolPlanPlanner, ToolPlanPlannerError
from src.tool_plan.schemas import (
    BaseToolPlanPayload,
    ToolPlanFeedbackItem,
    ToolPlanRegenerationRequestedEvent,
    ToolPlanRequestedEvent,
    ToolPlanResult,
    ToolPlanSkippedResult,
)

logger = logging.getLogger(__name__)

class ToolGenerationProcessor:
    """Compatibility adapter for the legacy ToolGeneration Kafka contract.

    Legacy API Server flows still publish TOOL_GENERATION_* messages keyed by
    toolId. Internally, Core now routes those requests through ToolPlanPlanner so
    the active system prompt comes from theseus_engine.models.state.
    """

    def __init__(
        self,
        *,
        publisher: ToolGenerationEventPublisher,
        planner: ToolPlanPlanner | None = None,
    ) -> None:
        self.publisher = publisher
        self.planner = planner or ToolPlanPlanner()

    async def process_message(self, payload: dict[str, Any]) -> None:
        event_type = payload.get("eventType")
        try:
            if event_type == "TOOL_GENERATION_REQUESTED":
                await self.process_generation(ToolGenerationRequestEvent.model_validate(payload))
            elif event_type == "TOOL_REGENERATION_REQUESTED":
                await self.process_regeneration(ToolRegenerationRequestEvent.model_validate(payload))
            else:
                logger.warning("Unsupported legacy ToolGeneration eventType=%s", event_type)
        except ValidationError as exc:
            logger.error("Invalid legacy ToolGeneration Kafka payload: %s", exc)

    async def process_generation(self, event: ToolGenerationRequestEvent) -> None:
        try:
            result = await self.planner.plan(
                self._to_tool_plan_requested_event(event),
                progress_callback=lambda message, rate: self.publish_progress(event, message, rate),
                # The planner streams JSON contract deltas. Legacy UI expects
                # markdown-like chunks, so keep live chunks off this temporary
                # path and publish the rendered markdown once it is available.
                chunk_callback=None,
            )
            if isinstance(result, ToolPlanSkippedResult):
                await self.publish_failed(event, "TOOL_PLAN_SKIPPED", result.message)
                return
            await self.publish_markdown_chunks(event, result.raw_markdown)
            await self.publish_completed(event, result, assistant_message_type="TOOL_DRAFT_RESPONSE")
        except ToolPlanPlannerError as exc:
            logger.error("Legacy Tool PLAN generation failed. runId=%s error=%s", event.run_id, exc, exc_info=True)
            await self.publish_failed(event, "AI_GENERATION_FAILED", str(exc))
        except Exception as exc:
            logger.error("Unexpected legacy Tool generation failure. runId=%s error=%s", event.run_id, exc, exc_info=True)
            await self.publish_failed(event, "AI_GENERATION_FAILED", str(exc))

    async def process_regeneration(self, event: ToolRegenerationRequestEvent) -> None:
        try:
            if event.base_draft is None:
                await self.publish_failed(
                    event,
                    "AI_REGENERATION_FAILED",
                    "Base draft payload is missing from regeneration request event",
                )
                return
            if event.base_draft_version is not None and event.base_draft.version != event.base_draft_version:
                await self.publish_failed(
                    event,
                    "AI_REGENERATION_FAILED",
                    "Base draft version mismatch. "
                    f"requested={event.base_draft_version}, current={event.base_draft.version}",
                )
                return

            result = await self.planner.plan(
                self._to_tool_plan_regeneration_requested_event(event),
                progress_callback=lambda message, rate: self.publish_progress(event, message, rate),
                chunk_callback=None,
            )
            if isinstance(result, ToolPlanSkippedResult):
                await self.publish_failed(event, "TOOL_PLAN_SKIPPED", result.message)
                return
            await self.publish_markdown_chunks(event, result.raw_markdown)
            await self.publish_completed(event, result, assistant_message_type="TOOL_REGENERATE_RESPONSE")
        except ToolPlanPlannerError as exc:
            logger.error("Legacy Tool PLAN regeneration failed. runId=%s error=%s", event.run_id, exc, exc_info=True)
            await self.publish_failed(event, "AI_REGENERATION_FAILED", str(exc))
        except Exception as exc:
            logger.error("Unexpected legacy Tool regeneration failure. runId=%s error=%s", event.run_id, exc, exc_info=True)
            await self.publish_failed(event, "AI_REGENERATION_FAILED", str(exc))

    def _to_tool_plan_requested_event(self, event: ToolGenerationRequestEvent) -> ToolPlanRequestedEvent:
        return ToolPlanRequestedEvent(
            eventType="TOOL_PLAN_REQUESTED",
            mode="PLAN",
            runId=event.run_id,
            projectId=event.project_id,
            chatSessionId=event.chat_session_id,
            requestedByUserId=event.requested_by_user_id,
            requestedByProjectMemberId=event.requested_by_project_member_id,
            prompt=event.prompt,
            history=[],
            requestedAt=self._requested_at(event),
        )

    def _to_tool_plan_regeneration_requested_event(
        self,
        event: ToolRegenerationRequestEvent,
    ) -> ToolPlanRegenerationRequestedEvent:
        assert event.base_draft is not None
        base_plan_version = event.base_draft_version or event.base_draft.version or 1
        return ToolPlanRegenerationRequestedEvent(
            eventType="TOOL_PLAN_REGENERATION_REQUESTED",
            mode="PLAN",
            runId=event.run_id,
            projectId=event.project_id,
            chatSessionId=event.chat_session_id,
            baseToolPlanId=event.tool_id,
            planGroupId=event.tool_id,
            basePlanVersion=base_plan_version,
            basePlan=BaseToolPlanPayload(
                rawMarkdown=event.base_draft.raw_markdown or "",
                structuredPlanJson=event.base_draft.structured_plan_json,
                planSnapshot=event.base_draft.draft_snapshot or event.base_draft.structured_plan_json,
            ),
            feedbackItems=[
                ToolPlanFeedbackItem(blockId=item.block_id, comment=item.comment)
                for item in event.feedback_items
            ],
            history=[],
            requestedAt=self._requested_at(event),
        )

    async def publish_progress(
        self,
        event: LegacyToolGenerationRequestEvent,
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

    async def publish_chunk(self, event: LegacyToolGenerationRequestEvent, content: str) -> None:
        if not content:
            return
        chunk = ToolGenerationChunkEvent(
            runId=event.run_id,
            projectId=event.project_id,
            chatSessionId=event.chat_session_id,
            toolId=event.tool_id,
            content=content,
        )
        await self.publisher.publish(event.run_id, chunk)

    async def publish_markdown_chunks(self, event: LegacyToolGenerationRequestEvent, content: str) -> None:
        for chunk in self._split_legacy_chunks(content):
            await self.publish_chunk(event, chunk)

    async def publish_completed(
        self,
        event: LegacyToolGenerationRequestEvent,
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
                draftSnapshot=result.plan_snapshot,
            ),
        )
        await self.publisher.publish(event.run_id, completed)

    async def publish_failed(
        self,
        event: LegacyToolGenerationRequestEvent,
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
    def _requested_at(event: LegacyToolGenerationRequestEvent) -> datetime:
        return event.requested_at or datetime.now(timezone.utc)

    @staticmethod
    def _split_legacy_chunks(content: str) -> list[str]:
        lines = content.splitlines(keepends=True)
        if len(lines) <= 4:
            return [content] if content else []

        chunks: list[str] = []
        step = max(4, len(lines) // 3)
        for start in range(0, len(lines), step):
            chunk = "".join(lines[start : start + step])
            if chunk:
                chunks.append(chunk)
        return chunks
