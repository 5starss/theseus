import logging

from src.auth.client import billing_client
from src.config import settings
from src.db.postgres import SessionLocal
from src.db.repositories.billing import BillingOutboxRepository, ClaimedBillingOutbox

logger = logging.getLogger(__name__)


def _compute_backoff_minutes(retry_count: int) -> int:
    return min(2 ** max(retry_count, 0), 60)


def _claim_billing_outbox(batch_size: int) -> list[ClaimedBillingOutbox]:
    db = SessionLocal()
    try:
        return BillingOutboxRepository(db).claim_batch(batch_size=batch_size)
    except Exception:
        db.rollback()
        raise
    finally:
        if db.in_transaction():
            db.rollback()
        db.close()


def _mark_billing_outbox_sent(record_id: str) -> None:
    db = SessionLocal()
    try:
        BillingOutboxRepository(db).mark_sent(record_id)
    except Exception:
        db.rollback()
        raise
    finally:
        if db.in_transaction():
            db.rollback()
        db.close()


def _mark_billing_outbox_failed(
    record_id: str,
    *,
    error: str,
    backoff_minutes: int,
) -> None:
    db = SessionLocal()
    try:
        BillingOutboxRepository(db).mark_failed(
            record_id,
            error=error,
            backoff_minutes=backoff_minutes,
        )
    except Exception:
        db.rollback()
        raise
    finally:
        if db.in_transaction():
            db.rollback()
        db.close()


async def process_billing_outbox(batch_size: int = 10) -> int:
    """
    Phase 2.1 manual flush entrypoint.
    Claims a batch of outbox records and attempts delivery.
    """
    records = _claim_billing_outbox(batch_size)
    processed = 0
    for record in records:
        success = await billing_client.report_usage(
            record.report,
            idempotency_key=record.id,
        )
        if success:
            _mark_billing_outbox_sent(record.id)
            logger.info("Billing outbox sent successfully: %s", record.id)
        else:
            _mark_billing_outbox_failed(
                record.id,
                error="Billing API delivery failed",
                backoff_minutes=_compute_backoff_minutes(record.retry_count + 1),
            )
            logger.warning("Billing outbox delivery failed: %s", record.id)
        processed += 1

    return processed


def setup_scheduler():
    """
    Phase 2.2 scheduler bootstrap.
    Returns an AsyncIOScheduler instance, or None if APScheduler is unavailable.
    """
    if not settings.BILLING_OUTBOX_SCHEDULER_ENABLED:
        logger.warning("Billing outbox scheduler is disabled by configuration.")
        return None

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
