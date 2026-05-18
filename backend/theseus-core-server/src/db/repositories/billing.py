from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from src.auth.schemas import BillingUsageReport, UsageMetrics
from src.db.models import BillingOutbox

OUTBOX_STATUS_PENDING = "pending"
OUTBOX_STATUS_PROCESSING = "processing"
OUTBOX_STATUS_SENT = "sent"
OUTBOX_STATUS_FAILED = "failed"


@dataclass(frozen=True, slots=True)
class ClaimedBillingOutbox:
    id: str
    report: BillingUsageReport
    retry_count: int


class BillingOutboxRepository:
    def __init__(self, db: Session):
        self.db = db

    def enqueue(
        self,
        user_id: int,
        project_id: int,
        usage: UsageMetrics,
    ) -> BillingOutbox:
        record = BillingOutbox(
            user_id=str(user_id),
            project_id=str(project_id),
            usage_data=usage.model_dump(mode="json"),
            status=OUTBOX_STATUS_PENDING,
            retry_count=0,
            next_retry_at=datetime.now(timezone.utc),
        )
        self.db.add(record)
        self.db.commit()
        self.db.refresh(record)
        return record

    def claim_batch(self, batch_size: int = 10) -> list[ClaimedBillingOutbox]:
        now = datetime.now(timezone.utc)
        stmt = (
            select(BillingOutbox)
            .where(BillingOutbox.status.in_([OUTBOX_STATUS_PENDING, OUTBOX_STATUS_FAILED]))
            .where(BillingOutbox.next_retry_at <= now)
            .order_by(BillingOutbox.created_at.asc())
            .limit(batch_size)
            .with_for_update(skip_locked=True)
        )
        records = list(self.db.execute(stmt).scalars().all())

        for record in records:
            record.status = OUTBOX_STATUS_PROCESSING
            record.updated_at = now

        claimed = [
            ClaimedBillingOutbox(
                id=record.id,
                report=self.to_usage_report(record),
                retry_count=int(record.retry_count or 0),
            )
            for record in records
        ]

        if records:
            self.db.commit()

        return claimed

    def mark_sent(self, record_id: str) -> None:
        record = self.db.get(BillingOutbox, record_id)
        if not record:
            return

        record.status = OUTBOX_STATUS_SENT
        record.last_error = None
        record.updated_at = datetime.now(timezone.utc)
        self.db.commit()

    def mark_failed(self, record_id: str, error: str, backoff_minutes: int) -> None:
        record = self.db.get(BillingOutbox, record_id)
        if not record:
            return

        record.status = OUTBOX_STATUS_FAILED
        record.retry_count += 1
        record.last_error = error
        record.next_retry_at = datetime.now(timezone.utc) + timedelta(minutes=backoff_minutes)
        record.updated_at = datetime.now(timezone.utc)
        self.db.commit()

    @staticmethod
    def to_usage_report(record: BillingOutbox) -> BillingUsageReport:
        return BillingUsageReport(
            user_id=record.user_id,
            project_id=record.project_id,
            usage=UsageMetrics(**record.usage_data),
        )
