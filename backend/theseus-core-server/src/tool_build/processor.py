from __future__ import annotations

import asyncio
import logging
from typing import Any

from pydantic import ValidationError

from src.config import settings
from src.tool_build.builder import ToolBuildError, ToolBuilder
from src.tool_build.publisher import ToolBuildEventPublisher
from src.tool_build.schemas import (
    ToolBuildChunkEvent,
    ToolBuildCompletedEvent,
    ToolBuildFailedEvent,
    ToolBuildProgressEvent,
    ToolBuildRequestedEvent,
)

logger = logging.getLogger(__name__)


class ToolBuildProcessor:
    def __init__(
        self,
        *,
        publisher: ToolBuildEventPublisher,
        builder: ToolBuilder | None = None,
    ) -> None:
        self.publisher = publisher
        self.builder = builder or ToolBuilder()
        self._event_sequences: dict[str, int] = {}
        self._finished_runs: set[str] = set()

    async def process_message(self, payload: dict[str, Any]) -> None:
        event_type = payload.get("eventType")
        if event_type != "TOOL_BUILD_REQUESTED":
            logger.warning("Unsupported Tool build eventType=%s", event_type)
            return

        try:
            await self.process_build(ToolBuildRequestedEvent.model_validate(payload))
        except ValidationError as exc:
            logger.error("Invalid Tool build Kafka payload: %s", exc)

    async def process_build(self, event: ToolBuildRequestedEvent) -> None:
        if event.run_id in self._finished_runs:
            logger.info("Duplicate finished Tool build run skipped. runId=%s", event.run_id)
            return

        try:
            await self.publish_progress(event, "REQUEST_RECEIVED", 5)
            artifact = await asyncio.wait_for(
                self.builder.build(
                    event,
                    progress_callback=lambda message, rate: self.publish_progress(event, message, rate),
                    chunk_callback=lambda content: self.publish_chunk(event, content),
                ),
                timeout=settings.CORE_TOOL_BUILD_RUN_TIMEOUT_SECONDS,
            )
            completed = ToolBuildCompletedEvent(
                runId=event.run_id,
                eventSequence=self.next_sequence(event.run_id),
                projectId=event.project_id,
                chatSessionId=event.chat_session_id,
                toolPlanId=event.tool_plan_id,
                artifact=artifact,
            )
            await self.publisher.publish(event.run_id, completed)
            self._finished_runs.add(event.run_id)
        except ToolBuildError as exc:
            logger.error("Tool build failed. runId=%s code=%s error=%s", event.run_id, exc.code, exc.message)
            await self.publish_failed(event, exc.code, exc.message)
        except TimeoutError:
            logger.error(
                "Tool build timed out. runId=%s timeoutSeconds=%s",
                event.run_id,
                settings.CORE_TOOL_BUILD_RUN_TIMEOUT_SECONDS,
            )
            await self.publish_failed(
                event,
                "TOOL_BUILD_TIMEOUT",
                f"Tool build exceeded {settings.CORE_TOOL_BUILD_RUN_TIMEOUT_SECONDS} seconds.",
            )
        except Exception as exc:
            logger.error("Unexpected Tool build failure. runId=%s error=%s", event.run_id, exc, exc_info=True)
            await self.publish_failed(event, "TOOL_BUILD_FAILED", str(exc))

    async def publish_progress(
        self,
        event: ToolBuildRequestedEvent,
        message: str,
        progress_rate: int | None,
    ) -> None:
        progress = ToolBuildProgressEvent(
            runId=event.run_id,
            eventSequence=self.next_sequence(event.run_id),
            projectId=event.project_id,
            chatSessionId=event.chat_session_id,
            toolPlanId=event.tool_plan_id,
            message=message,
            progressRate=progress_rate,
        )
        await self.publisher.publish(event.run_id, progress)

    async def publish_chunk(self, event: ToolBuildRequestedEvent, content: str) -> None:
        if not content:
            return
        chunk = ToolBuildChunkEvent(
            runId=event.run_id,
            eventSequence=self.next_sequence(event.run_id),
            projectId=event.project_id,
            chatSessionId=event.chat_session_id,
            toolPlanId=event.tool_plan_id,
            content=content,
        )
        await self.publisher.publish(event.run_id, chunk)

    async def publish_failed(self, event: ToolBuildRequestedEvent, code: str, message: str) -> None:
        failed = ToolBuildFailedEvent(
            runId=event.run_id,
            eventSequence=self.next_sequence(event.run_id),
            projectId=event.project_id,
            chatSessionId=event.chat_session_id,
            toolPlanId=event.tool_plan_id,
            code=code,
            message=message,
        )
        await self.publisher.publish(event.run_id, failed)
        self._finished_runs.add(event.run_id)

    def next_sequence(self, run_id: str) -> int:
        next_value = self._event_sequences.get(run_id, 0) + 1
        self._event_sequences[run_id] = next_value
        return next_value
