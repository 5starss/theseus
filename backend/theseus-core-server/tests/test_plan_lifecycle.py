import unittest

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from src.auth.dependencies import get_session_context
from src.auth.schemas import SessionContext
from src.db.models import Base, ToolPlan
from src.db.postgres import get_db
from src.main import app


def mock_session() -> SessionContext:
    return SessionContext(
        user_id="test-user",
        project_id="test-project",
        permission_level=3,
        token="test-token",
    )


class PlanLifecycleTests(unittest.TestCase):
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

    def test_plan_lifecycle_transitions(self):
        payload = {
            "chat_session_id": 123,
            "goal": "build tool",
            "content": {
                "goal": "build tool",
                "overview": ["a"],
                "approach": "ship it",
                "keyDecisions": ["x"],
                "steps": [{
                    "stepNumber": 1,
                    "title": "draft",
                    "description": "do work",
                    "subTasks": ["a"],
                    "dependencies": [],
                    "estimatedComplexity": "low",
                    "outputArtifacts": ["plan"],
                }],
                "risks": ["risk"],
                "successCriteria": ["done"],
            },
        }
        create_response = self.client.post("/api/v1/plans", json=payload)
        self.assertEqual(create_response.status_code, 200)
        plan_id = create_response.json()["id"]
        self.assertEqual(create_response.json()["status"], "drafting")

        submit_response = self.client.patch(f"/api/v1/plans/{plan_id}/submit")
        self.assertEqual(submit_response.status_code, 200)
        self.assertEqual(submit_response.json()["status"], "wait_for_review")

        approve_response = self.client.patch(f"/api/v1/plans/{plan_id}/approve")
        self.assertEqual(approve_response.status_code, 200)
        self.assertEqual(approve_response.json()["status"], "approved")

        execute_response = self.client.patch(f"/api/v1/plans/{plan_id}/execute")
        self.assertEqual(execute_response.status_code, 200)
        self.assertEqual(execute_response.json()["status"], "executing")

        invalid_reject = self.client.patch(
            f"/api/v1/plans/{plan_id}/reject",
            json={"feedback": "nope"},
        )
        self.assertEqual(invalid_reject.status_code, 400)
