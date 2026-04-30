import unittest
from unittest.mock import AsyncMock, patch

from fastapi.testclient import TestClient

from src.auth.dependencies import get_session_context
from src.auth.schemas import SessionContext
from src.main import app
from src.sandbox.base import SandboxUnavailableError


def admin_session() -> SessionContext:
    return SessionContext(
        user_id="admin-user",
        project_id="project-1",
        permission_level=3,
        token="admin-token",
    )


def low_permission_session() -> SessionContext:
    return SessionContext(
        user_id="basic-user",
        project_id="project-1",
        permission_level=1,
        token="basic-token",
    )


class SandboxRouteTests(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(app)

    def tearDown(self):
        self.client.close()
        app.dependency_overrides.clear()

    def test_sandbox_route_rejects_low_permission_user(self):
        app.dependency_overrides[get_session_context] = low_permission_session

        response = self.client.post(
            "/api/v1/sandbox/execute",
            json={
                "tool_name": "arithmetic",
                "tool_code": "def main(payload):\n    return payload\n",
                "payload": {"a": 1},
                "timeout_seconds": 5,
            },
        )

        self.assertEqual(response.status_code, 403)
        self.assertEqual(
            response.json()["detail"],
            "Sandbox execution requires elevated permissions",
        )

    def test_sandbox_route_returns_503_when_sandbox_unavailable(self):
        app.dependency_overrides[get_session_context] = admin_session

        with patch(
            "src.routes.sandbox.executor.execute",
            new=AsyncMock(side_effect=SandboxUnavailableError("Docker daemon is unavailable")),
        ):
            response = self.client.post(
                "/api/v1/sandbox/execute",
                json={
                    "tool_name": "arithmetic",
                    "tool_code": "def main(payload):\n    return payload\n",
                    "payload": {"a": 1},
                    "timeout_seconds": 5,
                },
            )

        self.assertEqual(response.status_code, 503)
        self.assertEqual(response.json()["detail"], "Docker daemon is unavailable")

    def test_sandbox_route_returns_executor_output(self):
        app.dependency_overrides[get_session_context] = admin_session

        with patch(
            "src.routes.sandbox.executor.execute",
            new=AsyncMock(
                return_value={
                    "success": True,
                    "result": {"sum": 3},
                    "stdout": "",
                    "stderr": "",
                    "error_message": None,
                    "exit_code": 0,
                    "timed_out": False,
                    "resource_limited": False,
                    "execution_time_ms": 12,
                }
            ),
        ):
            response = self.client.post(
                "/api/v1/sandbox/execute",
                json={
                    "tool_name": "arithmetic",
                    "tool_code": "def main(payload):\n    return {'sum': payload['a'] + payload['b']}\n",
                    "payload": {"a": 1, "b": 2},
                    "timeout_seconds": 5,
                },
            )

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()["success"])
        self.assertEqual(response.json()["result"], {"sum": 3})


if __name__ == "__main__":
    unittest.main()
