import unittest
from datetime import datetime, timezone
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from src.db.models import Base, BillingOutbox
from src.db.repositories.billing import (
    BillingOutboxRepository,
    OUTBOX_STATUS_PENDING,
    OUTBOX_STATUS_PROCESSING,
    OUTBOX_STATUS_SENT,
    OUTBOX_STATUS_FAILED
)
from src.auth.schemas import UsageMetrics

class BillingRepoTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from src.config import settings
        cls.engine = create_engine(settings.database_url)
        Base.metadata.create_all(cls.engine)
        cls.SessionLocal = sessionmaker(bind=cls.engine)

    def setUp(self):
        self.db = self.SessionLocal()
        self.repo = BillingOutboxRepository(self.db)

    def tearDown(self):
        self.db.query(BillingOutbox).delete()
        self.db.commit()
        self.db.close()

    def test_enqueue_creates_pending_record(self):
        usage = UsageMetrics(prompt_tokens=10, completion_tokens=5, total_tokens=15, model_name="gpt-4")
        record = self.repo.enqueue("user-1", "project-1", usage)
        
        self.assertEqual(record.user_id, "user-1")
        self.assertEqual(record.status, OUTBOX_STATUS_PENDING)
        self.assertEqual(record.usage_data["total_tokens"], 15)
        self.assertEqual(record.retry_count, 0)

    def test_claim_batch_transitions_to_processing(self):
        usage = UsageMetrics(prompt_tokens=1, completion_tokens=1, total_tokens=2, model_name="test")
        self.repo.enqueue("u1", "p1", usage)
        self.repo.enqueue("u2", "p2", usage)
        
        records = self.repo.claim_batch(batch_size=1)
        self.assertEqual(len(records), 1)
        self.assertEqual(records[0].status, OUTBOX_STATUS_PROCESSING)
        
        # Verify second record is still pending
        pending = self.db.query(BillingOutbox).filter(BillingOutbox.status == OUTBOX_STATUS_PENDING).all()
        self.assertEqual(len(pending), 1)

    def test_mark_sent_updates_status(self):
        usage = UsageMetrics(prompt_tokens=1, completion_tokens=1, total_tokens=2, model_name="test")
        record = self.repo.enqueue("u1", "p1", usage)
        
        self.repo.mark_sent(record.id)
        
        updated = self.db.get(BillingOutbox, record.id)
        self.assertEqual(updated.status, OUTBOX_STATUS_SENT)
        self.assertIsNone(updated.last_error)

    def test_mark_failed_updates_retry_and_backoff(self):
        usage = UsageMetrics(prompt_tokens=1, completion_tokens=1, total_tokens=2, model_name="test")
        record = self.repo.enqueue("u1", "p1", usage)
        
        self.repo.mark_failed(record.id, error="Network Error", backoff_minutes=5)
        
        updated = self.db.get(BillingOutbox, record.id)
        self.assertEqual(updated.status, OUTBOX_STATUS_FAILED)
        self.assertEqual(updated.retry_count, 1)
        self.assertEqual(updated.last_error, "Network Error")
        self.assertTrue(updated.next_retry_at > datetime.now(timezone.utc))

if __name__ == "__main__":
    unittest.main()
