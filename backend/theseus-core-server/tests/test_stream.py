import unittest
from dataclasses import dataclass
from unittest.mock import AsyncMock, patch

from fastapi import HTTPException
from fastapi.testclient import TestClient

from src.auth.dependencies import get_sse_session_context
from src.auth.schemas import SessionContext
from src.builder.engine import EngineInitializationError
from src.db.postgres import get_db
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

    def load_messages(self, _messages):
        return None

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


@dataclass
class FakeOutboxRecord:
    id: int = 1


def mock_session() -> SessionContext:
    return SessionContext(
        user_id="test-user",
        project_id="test-project",
        permission_level=1,
        token="test-token",
    )


def fake_db():
    yield object()


class StreamRouteTests(unittest.TestCase):
    def setUp(self):
        app.dependency_overrides[get_sse_session_context] = mock_session
        app.dependency_overrides[get_db] = fake_db
        self.client = TestClient(app)

    def tearDown(self):
        self.client.close()
        app.dependency_overrides.clear()

    def test_stream_endpoint_emits_sse_events(self):
        load_history = AsyncMock(return_value=[])
        persist_user = AsyncMock()
        persist_assistant = AsyncMock()

        def fake_get_query_engine(_context):
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
            with patch("src.routes.stream.load_history_messages", load_history):
                with patch("src.routes.stream.persist_user_message", persist_user):
                    with patch("src.routes.stream.persist_assistant_message", persist_assistant):
                        with patch(
                            "src.routes.stream.BillingOutboxRepository.enqueue",
                            return_value=FakeOutboxRecord(),
                        ):
                            response = self.client.get(
                                "/api/v1/stream",
                                params={"prompt": "Hello", "chat_session_id": 123},
                            )

        self.assertEqual(response.status_code, 200)
        self.assertIn("event: connected", response.text)
        self.assertIn('event: chunk\ndata: {"content": "hello "}', response.text)
        self.assertIn('event: status\ndata: {"message": "Executing tool: glob"}', response.text)
        self.assertIn(
            'event: tool_result\ndata: {"tool_name": "glob", "output": "file_a.py\\nfile_b.py"}',
            response.text,
        )
        self.assertIn("event: completed", response.text)
        self.assertIn('"total_tokens": 18', response.text)
        load_history.assert_awaited_once()
        persist_user.assert_awaited_once()
        persist_assistant.assert_awaited_once()
        self.assertEqual(persist_assistant.await_args.kwargs["content"], "hello world")

    def test_stream_endpoint_emits_error_when_assistant_message_save_fails(self):
        load_history = AsyncMock(return_value=[])
        persist_user = AsyncMock()
        persist_assistant = AsyncMock(return_value=False)

        def fake_get_query_engine(_context):
            events = [FakeAssistantTextDelta(text="hello")]
            return FakeAssembly(
                engine=FakeEngine(events=events, total_usage=FakeUsage()),
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
                        with patch(
                            "src.routes.stream.BillingOutboxRepository.enqueue",
                            return_value=FakeOutboxRecord(),
                        ):
                            response = self.client.get(
                                "/api/v1/stream",
                                params={"prompt": "Hello", "chat_session_id": 123},
                            )

        self.assertEqual(response.status_code, 200)
        self.assertIn(
            'event: error\ndata: {"message": "Assistant message persistence failed"}',
            response.text,
        )
        self.assertNotIn("event: completed", response.text)

    def test_stream_endpoint_returns_422_when_prompt_missing(self):
        load_history = AsyncMock(return_value=[])
        persist_user = AsyncMock()
        persist_assistant = AsyncMock()

        with patch(
            "src.routes.stream.load_history_messages",
            load_history,
        ):
            with patch("src.routes.stream.persist_user_message", persist_user):
                with patch("src.routes.stream.persist_assistant_message", persist_assistant):
                    with patch(
                        "src.routes.stream.BillingOutboxRepository.enqueue",
                        return_value=FakeOutboxRecord(),
                    ):
                        response = self.client.get("/api/v1/stream", params={"chat_session_id": 123})

        self.assertEqual(response.status_code, 422)

    def test_stream_endpoint_returns_422_when_prompt_blank(self):
        load_history = AsyncMock(return_value=[])
        persist_user = AsyncMock()
        persist_assistant = AsyncMock()

        with patch(
            "src.routes.stream.load_history_messages",
            load_history,
        ):
            with patch("src.routes.stream.persist_user_message", persist_user):
                with patch("src.routes.stream.persist_assistant_message", persist_assistant):
                    with patch(
                        "src.routes.stream.BillingOutboxRepository.enqueue",
                        return_value=FakeOutboxRecord(),
                    ):
                        response = self.client.get(
                            "/api/v1/stream",
                            params={"prompt": "   ", "chat_session_id": 123},
                        )

        self.assertEqual(response.status_code, 422)
        self.assertEqual(response.json()["detail"], "Prompt must not be blank")

    def test_stream_endpoint_returns_error_sse_when_engine_init_fails(self):
        permission_lookup = AsyncMock(return_value={"read_file": 1})
        load_history = AsyncMock(return_value=[])
        persist_user = AsyncMock()
        persist_assistant = AsyncMock()
        with patch(
            "src.routes.stream.get_query_engine",
            side_effect=EngineInitializationError("OpenHarness is not available"),
        ):
            with patch(
                "src.routes.stream.get_project_tool_permissions",
                permission_lookup,
            ):
                with patch("src.routes.stream.load_history_messages", load_history):
                    with patch("src.routes.stream.persist_user_message", persist_user):
                        with patch("src.routes.stream.persist_assistant_message", persist_assistant):
                            with patch(
                                "src.routes.stream.BillingOutboxRepository.enqueue",
                                return_value=FakeOutboxRecord(),
                            ):
                                response = self.client.get(
                                    "/api/v1/stream",
                                    params={"prompt": "Hello", "chat_session_id": 123},
                                )

        self.assertEqual(response.status_code, 200)
        self.assertIn("event: connected", response.text)
        self.assertIn(
            'event: error\ndata: {"message": "OpenHarness is not available"}',
            response.text,
        )
        persist_assistant.assert_not_awaited()

    def test_stream_endpoint_allows_empty_permissions_and_emits_engine_error(self):
        permission_lookup = AsyncMock(return_value={})
        load_history = AsyncMock(return_value=[])
        persist_user = AsyncMock()
        persist_assistant = AsyncMock()
        with patch(
            "src.routes.stream.get_query_engine",
            side_effect=EngineInitializationError(
                "No tools are available for the current server session."
            ),
        ):
            with patch(
                "src.routes.stream.get_project_tool_permissions",
                permission_lookup,
            ):
                with patch("src.routes.stream.load_history_messages", load_history):
                    with patch("src.routes.stream.persist_user_message", persist_user):
                        with patch("src.routes.stream.persist_assistant_message", persist_assistant):
                            with patch(
                                "src.routes.stream.BillingOutboxRepository.enqueue",
                                return_value=FakeOutboxRecord(),
                            ):
                                response = self.client.get(
                                    "/api/v1/stream",
                                    params={"prompt": "Hello", "chat_session_id": 123},
                                )

        self.assertEqual(response.status_code, 200)
        self.assertIn(
            'event: error\ndata: {"message": "No tools are available for the current server session."}',
            response.text,
        )
        persist_assistant.assert_not_awaited()

    def test_stream_endpoint_propagates_permission_errors(self):
        scenarios = [
            (403, "Project access denied"),
            (502, "Permission service returned invalid data"),
            (503, "Permission service unavailable"),
        ]

        for status_code, detail in scenarios:
            permission_lookup = AsyncMock(
                side_effect=HTTPException(status_code=status_code, detail=detail)
            )
            load_history = AsyncMock(return_value=[])
            persist_user = AsyncMock()
            persist_assistant = AsyncMock()
            with patch(
                "src.routes.stream.get_project_tool_permissions",
                permission_lookup,
            ):
                with patch("src.routes.stream.load_history_messages", load_history):
                    with patch("src.routes.stream.persist_user_message", persist_user):
                        with patch("src.routes.stream.persist_assistant_message", persist_assistant):
                            response = self.client.get(
                                "/api/v1/stream",
                                params={"prompt": "Hello", "chat_session_id": 123},
                            )

            self.assertEqual(response.status_code, status_code)
            self.assertEqual(response.json()["detail"], detail)

    def test_stream_endpoint_returns_422_when_chat_session_id_missing(self):
        response = self.client.get("/api/v1/stream", params={"prompt": "Hello"})

        self.assertEqual(response.status_code, 422)


if __name__ == "__main__":
    unittest.main()
