import unittest
from dataclasses import dataclass
from unittest.mock import AsyncMock, patch

from fastapi.testclient import TestClient

from src.auth.dependencies import get_sse_session_context
from src.auth.schemas import SessionContext
from src.builder.engine import EngineInitializationError
from src.main import app


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
    def __init__(self, events, total_usage=None):
        self._events = events
        self.total_usage = total_usage

    async def submit_message(self, prompt: str):
        for event in self._events:
            yield event


@dataclass
class FakeUsage:
    prompt_tokens: int = 11
    completion_tokens: int = 7
    total_tokens: int = 18


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
        permission_level=1,
        token="test-token",
    )


class StreamRouteTests(unittest.TestCase):
    def setUp(self):
        app.dependency_overrides[get_sse_session_context] = mock_session
        self.client = TestClient(app)

    def tearDown(self):
        self.client.close()
        app.dependency_overrides.clear()

    def test_stream_endpoint_emits_sse_events(self):
        def fake_get_query_engine(_session):
            events = [
                FakeAssistantTextDelta(text="hello "),
                FakeToolExecutionStarted(tool_name="glob"),
                FakeToolExecutionCompleted(tool_name="glob", output="file_a.py\nfile_b.py"),
                FakeAssistantTextDelta(text="world"),
            ]
            return FakeAssembly(
                engine=FakeEngine(events=events, total_usage=FakeUsage()),
                model_name="fake-model",
                allowed_tools=("read_file", "glob", "grep"),
                assistant_text_delta_type=FakeAssistantTextDelta,
                tool_execution_started_type=FakeToolExecutionStarted,
                tool_execution_completed_type=FakeToolExecutionCompleted,
                error_event_type=FakeErrorEvent,
            )

        with patch("src.routes.stream.get_query_engine", side_effect=fake_get_query_engine):
            with patch("src.routes.stream.billing_client.report_usage", new=AsyncMock(return_value=True)):
                response = self.client.get("/api/v1/stream", params={"prompt": "Hello"})

        self.assertEqual(response.status_code, 200)
        self.assertIn("event: connected", response.text)
        self.assertIn('event: chunk\ndata: {"content": "hello "}', response.text)
        self.assertIn('event: status\ndata: {"message": "Executing tool: glob"}', response.text)
        self.assertIn(
            'event: tool_result\ndata: {"tool_name": "glob", "output": "file_a.py\\nfile_b.py"}',
            response.text,
        )
        self.assertIn("event: complete", response.text)
        self.assertIn('"total_tokens": 18', response.text)

    def test_stream_endpoint_returns_422_when_prompt_missing(self):
        with patch("src.routes.stream.billing_client.report_usage", new=AsyncMock(return_value=True)):
            response = self.client.get("/api/v1/stream")

        self.assertEqual(response.status_code, 422)

    def test_stream_endpoint_returns_422_when_prompt_blank(self):
        with patch("src.routes.stream.billing_client.report_usage", new=AsyncMock(return_value=True)):
            response = self.client.get("/api/v1/stream", params={"prompt": "   "})

        self.assertEqual(response.status_code, 422)
        self.assertEqual(response.json()["detail"], "Prompt must not be blank")

    def test_stream_endpoint_returns_error_sse_when_engine_init_fails(self):
        with patch(
            "src.routes.stream.get_query_engine",
            side_effect=EngineInitializationError("OpenHarness is not available"),
        ):
            with patch("src.routes.stream.billing_client.report_usage", new=AsyncMock(return_value=True)):
                response = self.client.get("/api/v1/stream", params={"prompt": "Hello"})

        self.assertEqual(response.status_code, 200)
        self.assertIn("event: connected", response.text)
        self.assertIn(
            'event: error\ndata: {"message": "OpenHarness is not available"}',
            response.text,
        )


if __name__ == "__main__":
    unittest.main()
