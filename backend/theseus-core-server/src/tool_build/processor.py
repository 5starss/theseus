from __future__ import annotations

import asyncio
import logging
from contextlib import AbstractContextManager, nullcontext
from typing import Any, Callable

from pydantic import ValidationError

from src.config import settings
from src.db.repositories.core_runs import CoreRunAlreadyFinished, CoreRunLeaseHeld, CoreRunRepository
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


class ToolBuildPublishError(RuntimeError):
    pass


class ToolBuildProcessor:
    def __init__(
        self,
        *,
        publisher: ToolBuildEventPublisher,
        builder: ToolBuilder | None = None,
        checkpoint_repo_factory: Callable[[], AbstractContextManager[CoreRunRepository]] | None = None,
    ) -> None:
        self.publisher = publisher
        self.builder = builder or ToolBuilder()
        self.checkpoint_repo_factory = checkpoint_repo_factory
        self.publish_channel = "tool-build"
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

        with self._checkpoint_repo() as repo:
            if repo is not None:
                try:
                    repo.begin_run(
                        run_id=event.run_id,
                        project_id=event.project_id,
                        chat_session_id=event.chat_session_id,
                        request_type="BUILD_TOOL",
                        mode="BUILD",
                        requested_at=event.requested_at,
                    )
                except CoreRunAlreadyFinished:
                    logger.info("Duplicate terminal Tool build run skipped. runId=%s", event.run_id)
                    return
                except CoreRunLeaseHeld:
                    logger.info("Tool build run lease is held by another worker. runId=%s", event.run_id)
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
            await self.publish_event(event.run_id, completed)
            with self._checkpoint_repo() as repo:
                if repo is not None:
                    repo.mark_completed(event.run_id)
            self._finished_runs.add(event.run_id)
        except ToolBuildError as exc:
            logger.error("Tool build failed. runId=%s code=%s error=%s", event.run_id, exc.code, exc.message)
            message = await self._explain_failure(event, code=exc.code, message=exc.message)
            await self.publish_failed(event, exc.code, message)
        except ToolBuildPublishError:
            logger.error("Tool build event publish failed. runId=%s", event.run_id, exc_info=True)
            raise
        except TimeoutError:
            logger.error(
                "Tool build timed out. runId=%s timeoutSeconds=%s",
                event.run_id,
                settings.CORE_TOOL_BUILD_RUN_TIMEOUT_SECONDS,
            )
            code = "TOOL_BUILD_TIMEOUT"
            message = f"Tool build exceeded {settings.CORE_TOOL_BUILD_RUN_TIMEOUT_SECONDS} seconds."
            message = await self._explain_failure(event, code=code, message=message, stage="timeout")
            await self.publish_failed(event, code, message)
        except Exception as exc:
            logger.error("Unexpected Tool build failure. runId=%s error=%s", event.run_id, exc, exc_info=True)
            code = "TOOL_BUILD_FAILED"
            message = await self._explain_failure(event, code=code, message=str(exc), stage="unexpected")
            await self.publish_failed(event, code, message)

    async def _explain_failure(
        self,
        event: ToolBuildRequestedEvent,
        *,
        code: str,
        message: str,
        stage: str | None = None,
    ) -> str:
        try:
            return await asyncio.wait_for(
                self.builder.explain_failure(
                    event,
                    code=code,
                    message=message,
                    stage=stage,
                ),
                timeout=20,
            )
        except Exception as exc:
            logger.warning(
                "Tool build failure explanation failed. runId=%s code=%s error=%s",
                event.run_id,
                code,
                exc,
                exc_info=True,
            )
            return message

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
        await self.publish_event(event.run_id, progress)

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
        await self.publish_event(event.run_id, chunk)

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
        await self.publish_event(event.run_id, failed)
        with self._checkpoint_repo() as repo:
            if repo is not None:
                repo.mark_failed(event.run_id, code, message)
        self._finished_runs.add(event.run_id)

    async def publish_event(self, key: str, event) -> None:
        with self._checkpoint_repo() as repo:
            record_id = None
            if repo is not None:
                repo.heartbeat(key)
                record = repo.record_event(event, publish_channel=self.publish_channel)
                record_id = record.id
            try:
                await self.publisher.publish(key, event)
            except Exception as exc:
                if repo is not None and record_id is not None:
                    repo.mark_event_failed(record_id, str(exc))
                raise ToolBuildPublishError(str(exc)) from exc
            if repo is not None and record_id is not None:
                repo.mark_event_sent(record_id)

    async def republish_pending_events(self, limit: int = 50) -> int:
        sent = 0
        with self._checkpoint_repo() as repo:
            if repo is None:
                return 0
            for record in repo.pending_events(limit=limit, publish_channel=self.publish_channel):
                try:
                    await self.publisher.publish(record.run_id, record.payload_json)
                except Exception as exc:
                    repo.mark_event_failed(record.id, str(exc))
                    continue
                repo.mark_event_sent(record.id)
                sent += 1
        return sent

    def next_sequence(self, run_id: str) -> int:
        with self._checkpoint_repo() as repo:
            if repo is not None:
                return repo.next_event_sequence(run_id)
        next_value = self._event_sequences.get(run_id, 0) + 1
        self._event_sequences[run_id] = next_value
        return next_value

    def _checkpoint_repo(self):
        if self.checkpoint_repo_factory is None:
            return nullcontext(None)
        return self.checkpoint_repo_factory()
