import logging

from src.auth.client import billing_client
from src.config import settings
from src.db.postgres import SessionLocal
from src.db.repositories.billing import BillingOutboxRepository

logger = logging.getLogger(__name__)


def _compute_backoff_minutes(retry_count: int) -> int:
    return min(2 ** max(retry_count, 0), 60)


async def process_billing_outbox(batch_size: int = 10) -> int:
    """
    Phase 2.1 manual flush entrypoint.
    Claims a batch of outbox records and attempts delivery.
    """
    db = SessionLocal()
    processed = 0
    try:
        repo = BillingOutboxRepository(db)
        records = repo.claim_batch(batch_size=batch_size)

        for record in records:
            report = repo.to_usage_report(record)
            success = await billing_client.report_usage(
                report,
                idempotency_key=record.id,
            )
            if success:
                repo.mark_sent(record.id)
                logger.info("Billing outbox sent successfully: %s", record.id)
            else:
                repo.mark_failed(
                    record.id,
                    error="Billing API delivery failed",
                    backoff_minutes=_compute_backoff_minutes(record.retry_count + 1),
                )
                logger.warning("Billing outbox delivery failed: %s", record.id)
            processed += 1

        return processed
    finally:
        db.close()


def setup_scheduler():
    """
    Phase 2.2 scheduler bootstrap.
    Returns an AsyncIOScheduler instance, or None if APScheduler is unavailable.
    """
    try:
        from apscheduler.schedulers.asyncio import AsyncIOScheduler
    except ImportError:
        logger.warning("APScheduler is not installed; billing outbox scheduler is disabled.")
        return None

    scheduler = AsyncIOScheduler()
    scheduler.add_job(
        process_billing_outbox,
        "interval",
        seconds=settings.BILLING_OUTBOX_FLUSH_INTERVAL_SECONDS,
        kwargs={"batch_size": settings.BILLING_OUTBOX_BATCH_SIZE},
        id="billing-outbox-flush",
        max_instances=1,
        coalesce=True,
        replace_existing=True,
    )
    return scheduler
