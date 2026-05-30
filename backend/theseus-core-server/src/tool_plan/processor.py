from __future__ import annotations

import asyncio
import logging
from contextlib import AbstractContextManager, nullcontext
from typing import Any, Callable

from pydantic import ValidationError

from src.db.repositories.core_runs import CoreRunAlreadyFinished, CoreRunLeaseHeld, CoreRunRepository
from src.demo_replay import (
    build_tool_plan_result_from_replay,
    find_tool_plan_replay,
    plan_replay_chunks,
    plan_replay_progress,
    replay_delay_ms,
)
from src.tool_plan.planner import ToolPlanPlanner, ToolPlanPlannerError
from src.tool_plan.publisher import ToolPlanEventPublisher
from src.tool_plan.schemas import (
    AssistantMessagePayload,
    ToolPlanChunkEvent,
    ToolPlanCompletedEvent,
    ToolPlanFailedEvent,
    ToolPlanPayload,
    ToolPlanProgressEvent,
    ToolPlanRegenerationRequestedEvent,
    ToolPlanRequestEvent,
    ToolPlanRequestedEvent,
    ToolPlanSkippedEvent,
    ToolPlanSkippedResult,
)

logger = logging.getLogger(__name__)


_DEMO_PLAN_PROGRESS_CHUNKS = {
    "REQUEST_RECEIVED": "PLAN 요청을 접수했습니다.\n",
    "PLAN_DRAFTING": "요청 의도와 기존 Tool 정책을 분석하고 있습니다.\n",
    "PLAN_STRUCTURING": "PLAN 구조를 정규화하고 표시 형식으로 정리하고 있습니다.\n",
    "PLAN_VALIDATING": "PLAN 스냅샷과 실행 명세를 검증하고 있습니다.\n",
    "PLAN_COMPLETED": "PLAN 초안이 준비되었습니다.\n",
}


def _demo_plan_progress_chunk(item: dict[str, Any]) -> str:
    for key in ("chunk", "statusChunk", "status_chunk", "content"):
        value = item.get(key)
        if value:
            return str(value)
    return _DEMO_PLAN_PROGRESS_CHUNKS.get(str(item.get("message") or ""), "")


class ToolPlanPublishError(RuntimeError):
    pass


class ToolPlanProcessor:
    def __init__(
        self,
        *,
        publisher: ToolPlanEventPublisher,
        planner: ToolPlanPlanner | None = None,
        checkpoint_repo_factory: Callable[[], AbstractContextManager[CoreRunRepository]] | None = None,
    ) -> None:
        self.publisher = publisher
        self.planner = planner or ToolPlanPlanner()
        self.checkpoint_repo_factory = checkpoint_repo_factory
        self.publish_channel = "tool-plan"
        self._event_sequences: dict[str, int] = {}
        self._finished_runs: set[str] = set()

    async def process_message(self, payload: dict[str, Any]) -> None:
        event_type = payload.get("eventType")
        try:
            if event_type == "TOOL_PLAN_REQUESTED":
                await self.process_plan(ToolPlanRequestedEvent.model_validate(payload), request_type="GENERATE_PLAN")
            elif event_type == "TOOL_PLAN_REGENERATION_REQUESTED":
                await self.process_plan(
                    ToolPlanRegenerationRequestedEvent.model_validate(payload),
                    request_type="REGENERATE_PLAN",
                )
            else:
                logger.warning("Unsupported ToolPlan eventType=%s", event_type)
        except ValidationError as exc:
            logger.error("Invalid ToolPlan Kafka payload: %s", exc)

    async def process_plan(self, event: ToolPlanRequestEvent, *, request_type: str) -> None:
        if event.run_id in self._finished_runs:
            logger.info("Duplicate finished ToolPlan run skipped. runId=%s", event.run_id)
            return

        if not self._begin_run(event, request_type=request_type):
            return

        demo_replay = find_tool_plan_replay(event)
        if demo_replay is not None:
            await self.publish_demo_plan(event, demo_replay)
            return

        try:
            await self.publish_progress(event, "REQUEST_RECEIVED", 5)
            await self.publish_chunk(event, "PLAN 요청을 접수했습니다.\n")
            result = await self.planner.plan(
                event,
                progress_callback=lambda message, rate: self.publish_progress(event, message, rate),
                # Stream only the normalized Markdown plan, not raw PLAN draft deltas.
                chunk_callback=None,
                status_chunk_callback=lambda content: self.publish_chunk(event, content),
                checkpoint=self.load_agent_checkpoint(event.run_id),
                checkpoint_callback=lambda checkpoint: self.save_agent_checkpoint(event.run_id, checkpoint),
            )
            if isinstance(result, ToolPlanSkippedResult):
                await self.publish_skipped(event, result.message)
                return
            await self.publish_markdown_chunks(event, result.raw_markdown)
            await self.publish_completed(event, result)
        except ToolPlanPublishError:
            logger.error("ToolPlan event publish failed. runId=%s", event.run_id, exc_info=True)
            raise
        except ToolPlanPlannerError as exc:
            logger.error("ToolPlan generation failed. runId=%s error=%s", event.run_id, exc, exc_info=True)
            code = "TOOL_PLAN_GENERATION_FAILED"
            message = await self._explain_failure(event, code=code, message=str(exc), stage="planner")
            await self.publish_failed(event, code, message)
        except Exception as exc:
            logger.error("Unexpected ToolPlan failure. runId=%s error=%s", event.run_id, exc, exc_info=True)
            code = "TOOL_PLAN_FAILED"
            message = await self._explain_failure(event, code=code, message=str(exc), stage="unexpected")
            await self.publish_failed(event, code, message)

    async def publish_demo_plan(
        self,
        event: ToolPlanRequestEvent,
        replay: dict[str, Any],
    ) -> None:
        logger.info(
            "Publishing demo ToolPlan replay. runId=%s replayId=%s",
            event.run_id,
            replay.get("id"),
        )
        result = build_tool_plan_result_from_replay(replay)
        for item in plan_replay_progress(replay):
            delay_ms = replay_delay_ms(item)
            if delay_ms:
                await asyncio.sleep(max(0, delay_ms) / 1000)
            await self.publish_progress(
                event,
                str(item.get("message") or "PLAN_DRAFTING"),
                item.get("progress_rate", item.get("progressRate")),
            )
            await self.publish_chunk(event, _demo_plan_progress_chunk(item))
        chunks = plan_replay_chunks(replay)
        if chunks:
            for chunk in chunks:
                await self.publish_chunk(event, chunk)
        else:
            await self.publish_markdown_chunks(event, result.raw_markdown)
        await self.publish_completed(event, result)

    async def _explain_failure(
        self,
        event: ToolPlanRequestEvent,
        *,
        code: str,
        message: str,
        stage: str | None = None,
    ) -> str:
        try:
            return await asyncio.wait_for(
                self.planner.explain_failure(
                    event,
                    code=code,
                    message=message,
                    stage=stage,
                ),
                timeout=20,
            )
        except Exception as exc:
            logger.warning(
                "ToolPlan failure explanation failed. runId=%s code=%s error=%s",
                event.run_id,
                code,
                exc,
                exc_info=True,
            )
            return message

    def _begin_run(self, event: ToolPlanRequestEvent, *, request_type: str) -> bool:
        with self._checkpoint_repo() as repo:
            if repo is None:
                return True
            try:
                repo.begin_run(
                    run_id=event.run_id,
                    project_id=event.project_id,
                    chat_session_id=event.chat_session_id,
                    request_type=request_type,
                    mode="PLAN",
                    requested_at=event.requested_at,
                )
            except CoreRunAlreadyFinished:
                logger.info("Duplicate terminal ToolPlan run skipped. runId=%s", event.run_id)
                return False
            except CoreRunLeaseHeld:
                logger.info("ToolPlan run lease is held by another worker. runId=%s", event.run_id)
                return False
        return True

    def load_agent_checkpoint(self, run_id: str) -> dict | None:
        with self._checkpoint_repo() as repo:
            if repo is None or not hasattr(repo, "get_checkpoint"):
                return None
            checkpoint = repo.get_checkpoint(run_id)
            if checkpoint is None:
                return None
            return {
                "stateMachine": checkpoint.state_machine_json or None,
                "conversation": checkpoint.conversation_json or None,
                "toolTrace": checkpoint.tool_trace_json or None,
                "progress": checkpoint.progress_json or None,
            }

    def save_agent_checkpoint(self, run_id: str, checkpoint: dict) -> None:
        with self._checkpoint_repo() as repo:
            if repo is None or not hasattr(repo, "update_checkpoint"):
                return
            repo.update_checkpoint(
                run_id,
                state_machine_json=checkpoint.get("stateMachine"),
                conversation_json=checkpoint.get("conversation"),
                tool_trace_json=checkpoint.get("toolTrace"),
                progress_json=checkpoint.get("progress"),
            )

    async def publish_progress(self, event: ToolPlanRequestEvent, message: str, progress_rate: int | None) -> None:
        progress = ToolPlanProgressEvent(
            runId=event.run_id,
            eventSequence=self.next_sequence(event.run_id),
            projectId=event.project_id,
            chatSessionId=event.chat_session_id,
            message=message,
            progressRate=progress_rate,
        )
        await self.publish_event(event.run_id, progress)

    async def publish_chunk(self, event: ToolPlanRequestEvent, content: str) -> None:
        if not content:
            return
        chunk = ToolPlanChunkEvent(
            runId=event.run_id,
            eventSequence=self.next_sequence(event.run_id),
            projectId=event.project_id,
            chatSessionId=event.chat_session_id,
            content=content,
        )
        await self.publish_event(event.run_id, chunk)

    async def publish_markdown_chunks(self, event: ToolPlanRequestEvent, content: str) -> None:
        for chunk in self._split_markdown_chunks(content):
            await self.publish_chunk(event, chunk)

    @staticmethod
    def _split_markdown_chunks(content: str) -> list[str]:
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

    async def publish_completed(self, event: ToolPlanRequestEvent, result) -> None:
        completed = ToolPlanCompletedEvent(
            runId=event.run_id,
            eventSequence=self.next_sequence(event.run_id),
            projectId=event.project_id,
            chatSessionId=event.chat_session_id,
            assistantMessage=AssistantMessagePayload(
                messageType="TOOL_PLAN_RESPONSE",
                contentType="MARKDOWN",
                content=result.raw_markdown,
            ),
            toolPlan=ToolPlanPayload(
                rawMarkdown=result.raw_markdown,
                structuredPlanJson=result.structured_plan_json,
                planSnapshot=result.plan_snapshot,
            ),
        )
        await self.publish_event(event.run_id, completed)
        self._mark_completed(event.run_id)

    async def publish_skipped(self, event: ToolPlanRequestEvent, message: str) -> None:
        skipped = ToolPlanSkippedEvent(
            runId=event.run_id,
            eventSequence=self.next_sequence(event.run_id),
            projectId=event.project_id,
            chatSessionId=event.chat_session_id,
            assistantMessage=AssistantMessagePayload(
                messageType="CHAT",
                contentType="TEXT",
                content=message,
            ),
        )
        await self.publish_event(event.run_id, skipped)
        self._mark_skipped(event.run_id)

    async def publish_failed(self, event: ToolPlanRequestEvent, code: str, message: str) -> None:
        failed = ToolPlanFailedEvent(
            runId=event.run_id,
            eventSequence=self.next_sequence(event.run_id),
            projectId=event.project_id,
            chatSessionId=event.chat_session_id,
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
                raise ToolPlanPublishError(str(exc)) from exc
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

    def _mark_completed(self, run_id: str) -> None:
        with self._checkpoint_repo() as repo:
            if repo is not None:
                repo.mark_completed(run_id)
        self._finished_runs.add(run_id)

    def _mark_skipped(self, run_id: str) -> None:
        with self._checkpoint_repo() as repo:
            if repo is not None and hasattr(repo, "mark_skipped"):
                repo.mark_skipped(run_id)
        self._finished_runs.add(run_id)

    def _checkpoint_repo(self):
        if self.checkpoint_repo_factory is None:
            return nullcontext(None)
        return self.checkpoint_repo_factory()
