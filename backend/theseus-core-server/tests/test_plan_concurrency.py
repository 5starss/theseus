import unittest

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from src.auth.dependencies import get_session_context
from src.auth.schemas import SessionContext
from src.db.models import Base, ToolPlan
from src.db.postgres import get_db
from src.main import app
from src.plan.service import PLAN_STATUS_APPROVED


def mock_session() -> SessionContext:
    return SessionContext(
        user_id="test-user",
        project_id="test-project",
        permission_level=3,
        token="test-token",
    )


class PlanConcurrencyTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from src.config import settings

        cls.engine = create_engine(settings.database_url)
        Base.metadata.create_all(cls.engine)
        cls.SessionLocal = sessionmaker(bind=cls.engine)

    def setUp(self):
        self.db = self.SessionLocal()

        def fake_db():
            try:
                yield self.db
            finally:
                pass

        app.dependency_overrides[get_session_context] = mock_session
        app.dependency_overrides[get_db] = fake_db
        self.client = TestClient(app)

    def tearDown(self):
        self.db.query(ToolPlan).delete()
        self.db.commit()
        self.db.close()
        self.client.close()
        app.dependency_overrides.clear()

    def test_only_one_plan_can_execute_per_chat_session(self):
        plan_a = ToolPlan(
            project_id="test-project",
            chat_session_id=321,
            status=PLAN_STATUS_APPROVED,
            goal="a",
            content={"goal": "a", "overview": [], "approach": "a", "keyDecisions": [], "steps": [], "risks": [], "successCriteria": []},
        )
        plan_b = ToolPlan(
            project_id="test-project",
            chat_session_id=321,
            status=PLAN_STATUS_APPROVED,
            goal="b",
            content={"goal": "b", "overview": [], "approach": "b", "keyDecisions": [], "steps": [], "risks": [], "successCriteria": []},
        )
        self.db.add_all([plan_a, plan_b])
        self.db.commit()
        self.db.refresh(plan_a)
        self.db.refresh(plan_b)

        first = self.client.patch(f"/api/v1/plans/{plan_a.id}/execute")
        self.assertEqual(first.status_code, 200)

        second = self.client.patch(f"/api/v1/plans/{plan_b.id}/execute")
        self.assertEqual(second.status_code, 409)
