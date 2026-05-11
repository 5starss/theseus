from __future__ import annotations

import socket
from contextlib import AbstractContextManager
from datetime import datetime, timedelta, timezone
from typing import Any

from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from src.db.models import CoreRunCheckpoint, CoreRunEvent

RUN_STATUS_REQUESTED = "REQUESTED"
RUN_STATUS_RUNNING = "RUNNING"
RUN_STATUS_COMPLETED = "COMPLETED"
RUN_STATUS_FAILED = "FAILED"

EVENT_STATUS_PENDING = "pending"
EVENT_STATUS_SENT = "sent"
EVENT_STATUS_FAILED = "failed"

TERMINAL_STATUSES = {RUN_STATUS_COMPLETED, RUN_STATUS_FAILED, "SKIPPED", "CANCELLED"}


class CoreRunAlreadyFinished(RuntimeError):
    pass


class CoreRunLeaseHeld(RuntimeError):
    pass


class CoreRunRepository:
    def __init__(
        self,
        db: Session,
        *,
        worker_id: str | None = None,
        lease_ttl_seconds: int = 60,
    ) -> None:
        self.db = db
        self.worker_id = worker_id or socket.gethostname()
        self.lease_ttl_seconds = lease_ttl_seconds

    def close(self) -> None:
        self.db.close()

    def begin_run(
        self,
        *,
        run_id: str,
        project_id: int,
        chat_session_id: int,
        request_type: str,
        mode: str,
        requested_at: datetime | None = None,
    ) -> CoreRunCheckpoint:
        now = datetime.now(timezone.utc)
        checkpoint = self._get_checkpoint_for_update(run_id)
        if checkpoint is None:
            checkpoint = CoreRunCheckpoint(
                run_id=run_id,
                project_id=project_id,
                chat_session_id=chat_session_id,
                request_type=request_type,
                mode=mode,
                status=RUN_STATUS_RUNNING,
                state_machine_json={"schemaVersion": 1, "mode": mode},
                conversation_json=[],
                last_event_sequence=0,
                lease_owner=self.worker_id,
                lease_expires_at=now + timedelta(seconds=self.lease_ttl_seconds),
                requested_at=requested_at or now,
                updated_at=now,
            )
            self.db.add(checkpoint)
            try:
                self.db.commit()
            except IntegrityError:
                self.db.rollback()
                return self.begin_run(
                    run_id=run_id,
                    project_id=project_id,
                    chat_session_id=chat_session_id,
                    request_type=request_type,
                    mode=mode,
                    requested_at=requested_at,
                )
            self.db.refresh(checkpoint)
            return checkpoint

        if checkpoint.status in TERMINAL_STATUSES:
            raise CoreRunAlreadyFinished(run_id)
        if checkpoint.lease_expires_at and checkpoint.lease_expires_at > now:
            if checkpoint.lease_owner != self.worker_id:
                raise CoreRunLeaseHeld(run_id)

        checkpoint.status = RUN_STATUS_RUNNING
        checkpoint.lease_owner = self.worker_id
        checkpoint.lease_expires_at = now + timedelta(seconds=self.lease_ttl_seconds)
        checkpoint.updated_at = now
        self.db.commit()
        self.db.refresh(checkpoint)
        return checkpoint

    def heartbeat(self, run_id: str) -> None:
        checkpoint = self.db.get(CoreRunCheckpoint, run_id)
        if checkpoint is None:
            return
        now = datetime.now(timezone.utc)
        checkpoint.lease_owner = self.worker_id
        checkpoint.lease_expires_at = now + timedelta(seconds=self.lease_ttl_seconds)
        checkpoint.updated_at = now
        self.db.commit()

    def get_checkpoint(self, run_id: str) -> CoreRunCheckpoint | None:
        return self.db.get(CoreRunCheckpoint, run_id)

    def update_checkpoint(
        self,
        run_id: str,
        *,
        state_machine_json: dict[str, Any] | None = None,
        conversation_json: list[dict[str, Any]] | None = None,
        tool_trace_json: list[dict[str, Any]] | None = None,
        progress_json: dict[str, Any] | None = None,
    ) -> None:
        checkpoint = self.db.get(CoreRunCheckpoint, run_id)
        if checkpoint is None:
            return
        if state_machine_json is not None:
            checkpoint.state_machine_json = state_machine_json
        if conversation_json is not None:
            checkpoint.conversation_json = conversation_json
        if tool_trace_json is not None:
            checkpoint.tool_trace_json = tool_trace_json
        if progress_json is not None:
            checkpoint.progress_json = progress_json
        checkpoint.updated_at = datetime.now(timezone.utc)
        self.db.commit()

    def next_event_sequence(self, run_id: str) -> int:
        checkpoint = self._get_checkpoint_for_update(run_id)
        if checkpoint is None:
            raise ValueError(f"Core run checkpoint not found: {run_id}")
        checkpoint.last_event_sequence = int(checkpoint.last_event_sequence or 0) + 1
        checkpoint.updated_at = datetime.now(timezone.utc)
        self.db.commit()
        self.db.refresh(checkpoint)
        return checkpoint.last_event_sequence

    def record_event(self, event: BaseModel, *, publish_channel: str | None = None) -> CoreRunEvent:
        payload = event.model_dump(mode="json", by_alias=True)
        record = CoreRunEvent(
            run_id=payload["runId"],
            event_sequence=payload["eventSequence"],
            event_type=payload["eventType"],
            publish_channel=publish_channel,
            payload_json=payload,
            publish_status=EVENT_STATUS_PENDING,
        )
        self.db.add(record)
        self.db.commit()
        self.db.refresh(record)
        return record

    def mark_event_sent(self, event_id: int) -> None:
        record = self.db.get(CoreRunEvent, event_id)
        if record is None:
            return
        record.publish_status = EVENT_STATUS_SENT
        record.published_at = datetime.now(timezone.utc)
        record.last_error = None
        self.db.commit()

    def mark_event_failed(self, event_id: int, error: str) -> None:
        record = self.db.get(CoreRunEvent, event_id)
        if record is None:
            return
        record.publish_status = EVENT_STATUS_FAILED
        record.publish_attempts = int(record.publish_attempts or 0) + 1
        record.last_error = error
        self.db.commit()

    def pending_events(self, limit: int = 50, *, publish_channel: str | None = None) -> list[CoreRunEvent]:
        stmt = (
            select(CoreRunEvent)
            .where(CoreRunEvent.publish_status.in_([EVENT_STATUS_PENDING, EVENT_STATUS_FAILED]))
            .order_by(CoreRunEvent.created_at.asc(), CoreRunEvent.event_sequence.asc())
            .limit(limit)
        )
        if publish_channel is not None:
            stmt = stmt.where(CoreRunEvent.publish_channel == publish_channel)
        return list(self.db.execute(stmt).scalars().all())

    def mark_completed(self, run_id: str) -> None:
        self._mark_terminal(run_id, RUN_STATUS_COMPLETED, None, None)

    def mark_failed(self, run_id: str, code: str, message: str) -> None:
        self._mark_terminal(run_id, RUN_STATUS_FAILED, code, message)

    def _mark_terminal(self, run_id: str, status: str, code: str | None, message: str | None) -> None:
        checkpoint = self.db.get(CoreRunCheckpoint, run_id)
        if checkpoint is None:
            return
        now = datetime.now(timezone.utc)
        checkpoint.status = status
        checkpoint.last_error_code = code
        checkpoint.last_error_message = message
        checkpoint.lease_owner = None
        checkpoint.lease_expires_at = None
        checkpoint.completed_at = now
        checkpoint.updated_at = now
        self.db.commit()

    def _get_checkpoint_for_update(self, run_id: str) -> CoreRunCheckpoint | None:
        stmt = select(CoreRunCheckpoint).where(CoreRunCheckpoint.run_id == run_id).with_for_update()
        return self.db.execute(stmt).scalar_one_or_none()


class CoreRunRepositoryContext(AbstractContextManager[CoreRunRepository]):
    def __init__(self, db_factory, **repo_kwargs: Any) -> None:
        self.db_factory = db_factory
        self.repo_kwargs = repo_kwargs
        self.repo: CoreRunRepository | None = None

    def __enter__(self) -> CoreRunRepository:
        self.repo = CoreRunRepository(self.db_factory(), **self.repo_kwargs)
        return self.repo

    def __exit__(self, exc_type, exc_value, traceback) -> None:
        if self.repo is not None:
            self.repo.close()
