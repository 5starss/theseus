from __future__ import annotations

from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from src.auth.schemas import BillingUsageReport, UsageMetrics
from src.db.models import BillingOutbox

OUTBOX_STATUS_PENDING = "pending"
OUTBOX_STATUS_PROCESSING = "processing"
OUTBOX_STATUS_SENT = "sent"
OUTBOX_STATUS_FAILED = "failed"


class BillingOutboxRepository:
    def __init__(self, db: Session):
        self.db = db

    def enqueue(
        self,
        user_id: str,
        project_id: str,
        usage: UsageMetrics,
    ) -> BillingOutbox:
        record = BillingOutbox(
            user_id=user_id,
            project_id=project_id,
            usage_data=usage.model_dump(mode="json"),
            status=OUTBOX_STATUS_PENDING,
            retry_count=0,
            next_retry_at=datetime.now(timezone.utc),
        )
        self.db.add(record)
        self.db.commit()
        self.db.refresh(record)
        return record

    def claim_batch(self, batch_size: int = 10) -> list[BillingOutbox]:
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

        if records:
            self.db.commit()
            for record in records:
                self.db.refresh(record)

        return records

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
