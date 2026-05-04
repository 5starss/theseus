import unittest
from dataclasses import dataclass
from unittest.mock import AsyncMock, patch

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from src.auth.dependencies import get_sse_session_context
from src.auth.schemas import SessionContext
from src.db.models import Base, ToolPlan
from src.db.postgres import get_db
from src.main import app
from src.plan.service import PLAN_STATUS_EXECUTING


@dataclass
class FakeAssistantTextDelta:
    text: str


@dataclass
class FakeToolExecutionStarted:
    tool_name: str


@dataclass
class FakeToolExecutionCompleted:
    tool_name: str
    output: str


@dataclass
class FakeErrorEvent:
    message: str


class FakeEngine:
    def __init__(self, events):
        self._events = events
        self.total_usage = None

    async def submit_message(self, prompt: str):
        del prompt
        for event in self._events:
            yield event


@dataclass
class FakeAssembly:
    engine: FakeEngine
    model_name: str
    allowed_tools: tuple[str, ...]
    assistant_text_delta_type: type
    tool_execution_started_type: type
    tool_execution_completed_type: type
    error_event_type: type


def mock_session() -> SessionContext:
    return SessionContext(
        user_id="test-user",
        project_id="test-project",
        permission_level=3,
        token="test-token",
    )


class PlanStreamTests(unittest.TestCase):
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

        app.dependency_overrides[get_sse_session_context] = mock_session
        app.dependency_overrides[get_db] = fake_db
        self.client = TestClient(app)

    def tearDown(self):
        self.db.query(ToolPlan).delete()
        self.db.commit()
        self.db.close()
        self.client.close()
        app.dependency_overrides.clear()

    def test_stream_rejects_plan_from_other_session(self):
        plan = ToolPlan(
            project_id="test-project",
            chat_session_id=999,
            status=PLAN_STATUS_EXECUTING,
            goal="a",
            content={"goal": "a", "overview": [], "approach": "a", "keyDecisions": [], "steps": [], "risks": [], "successCriteria": []},
            executing_by_user_id="test-user",
        )
        self.db.add(plan)
        self.db.commit()
        self.db.refresh(plan)

        response = self.client.get(
            "/api/v1/stream",
            params={"prompt": "hello", "chat_session_id": 123, "plan_id": plan.id},
        )
        self.assertEqual(response.status_code, 403)

    def test_stream_restores_plan_to_approved(self):
        plan = ToolPlan(
            project_id="test-project",
            chat_session_id=123,
            status=PLAN_STATUS_EXECUTING,
            goal="a",
            content={"goal": "a", "overview": [], "approach": "a", "keyDecisions": [], "steps": [], "risks": [], "successCriteria": []},
            executing_by_user_id="test-user",
        )
        self.db.add(plan)
        self.db.commit()
        self.db.refresh(plan)

        load_history = AsyncMock(return_value=[])
        persist_user = AsyncMock()
        persist_assistant = AsyncMock(return_value=True)

        def fake_get_query_engine(_context):
            return FakeAssembly(
                engine=FakeEngine([FakeAssistantTextDelta(text="done")]),
                model_name="fake-model",
                allowed_tools=("read_file",),
                assistant_text_delta_type=FakeAssistantTextDelta,
                tool_execution_started_type=FakeToolExecutionStarted,
                tool_execution_completed_type=FakeToolExecutionCompleted,
                error_event_type=FakeErrorEvent,
            )

        with patch("src.routes.stream.get_query_engine", side_effect=fake_get_query_engine):
            with patch("src.routes.stream.load_history_messages", load_history):
                with patch("src.routes.stream.persist_user_message", persist_user):
                    with patch("src.routes.stream.persist_assistant_message", persist_assistant):
                        with patch("src.routes.stream.BillingOutboxRepository.enqueue"):
                            response = self.client.get(
                                "/api/v1/stream",
                                params={"prompt": "hello", "chat_session_id": 123, "plan_id": plan.id},
                            )

        self.assertEqual(response.status_code, 200)
        self.db.refresh(plan)
        self.assertEqual(plan.status, "approved")
