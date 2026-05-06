import unittest
from unittest.mock import AsyncMock, patch

import httpx
from fastapi import HTTPException

from src.auth.client import (
    AgentClient,
    AuthClient,
    BillingClient,
    PermissionAccessDeniedError,
    PermissionBackendUnavailableError,
    PermissionClient,
    PermissionInvalidResponseError,
)
from src.auth.schemas import AgentToolPlanPayload, BillingUsageReport, StructuredPlan, UsageMetrics
from src.auth.permissions import (
    MOCK_PROJECT_TOOL_PERMISSIONS,
    PERMISSION_SERVICE_INVALID_DATA,
    PERMISSION_SERVICE_UNAVAILABLE,
    PROJECT_ACCESS_DENIED,
    get_project_tool_permissions,
)
from src.config import settings


class PermissionServiceTests(unittest.IsolatedAsyncioTestCase):
    async def test_get_project_tool_permissions_returns_mock_map_in_mock_mode(self):
        with patch("src.auth.permissions.settings.AUTH_MODE", "mock"):
            permissions = await get_project_tool_permissions("project-1", "user-1")

        self.assertEqual(permissions, MOCK_PROJECT_TOOL_PERMISSIONS)

    async def test_get_project_tool_permissions_returns_spring_result(self):
        permission_lookup = AsyncMock(return_value={"read_file": 1, "bash": 3})
        with patch("src.auth.permissions.settings.AUTH_MODE", "spring"):
            with patch(
                "src.auth.permissions.permission_client.fetch_project_tool_permissions",
                permission_lookup,
            ):
                permissions = await get_project_tool_permissions(123, 456)

        self.assertEqual(permissions, {"read_file": 1, "bash": 3})
        permission_lookup.assert_awaited_once_with(project_id="123", user_id="456")

    async def test_get_project_tool_permissions_raises_403_for_access_denied(self):
        permission_lookup = AsyncMock(side_effect=PermissionAccessDeniedError())
        with patch("src.auth.permissions.settings.AUTH_MODE", "spring"):
            with patch(
                "src.auth.permissions.permission_client.fetch_project_tool_permissions",
                permission_lookup,
            ):
                with self.assertRaises(HTTPException) as context:
                    await get_project_tool_permissions("project-1", "user-1")

        self.assertEqual(context.exception.status_code, 403)
        self.assertEqual(context.exception.detail, PROJECT_ACCESS_DENIED)

    async def test_get_project_tool_permissions_raises_502_for_invalid_data(self):
        permission_lookup = AsyncMock(side_effect=PermissionInvalidResponseError())
        with patch("src.auth.permissions.settings.AUTH_MODE", "spring"):
            with patch(
                "src.auth.permissions.permission_client.fetch_project_tool_permissions",
                permission_lookup,
            ):
                with self.assertRaises(HTTPException) as context:
                    await get_project_tool_permissions("project-1", "user-1")

        self.assertEqual(context.exception.status_code, 502)
        self.assertEqual(context.exception.detail, PERMISSION_SERVICE_INVALID_DATA)

    async def test_get_project_tool_permissions_raises_503_for_backend_failure(self):
        permission_lookup = AsyncMock(side_effect=PermissionBackendUnavailableError())
        with patch("src.auth.permissions.settings.AUTH_MODE", "spring"):
            with patch(
                "src.auth.permissions.permission_client.fetch_project_tool_permissions",
                permission_lookup,
            ):
                with self.assertRaises(HTTPException) as context:
                    await get_project_tool_permissions("project-1", "user-1")

        self.assertEqual(context.exception.status_code, 503)
        self.assertEqual(context.exception.detail, PERMISSION_SERVICE_UNAVAILABLE)


class PermissionClientTests(unittest.IsolatedAsyncioTestCase):
    async def test_permission_client_returns_valid_map(self):
        response = httpx.Response(200, json={"read_file": 1, "bash": 3})
        client = PermissionClient()
        async_client = AsyncMock()
        async_client.__aenter__.return_value = async_client
        async_client.__aexit__.return_value = False
        async_client.post.return_value = response

        with patch("src.auth.client.httpx.AsyncClient", return_value=async_client):
            permissions = await client.fetch_project_tool_permissions("project-1", "user-1")

        self.assertEqual(permissions, {"read_file": 1, "bash": 3})
        async_client.post.assert_awaited_once_with(
            client.permissions_url,
            headers={"X-Internal-Api-Key": settings.SPRING_BOOT_INTERNAL_API_KEY},
            json={"projectId": "project-1", "userId": "user-1"},
            timeout=client.timeout,
        )

    async def test_permission_client_accepts_wrapped_api_response(self):
        response = httpx.Response(
            200,
            json={
                "isSuccess": True,
                "code": "COMMON-200",
                "message": "성공입니다.",
                "result": {"read_file": 1, "bash": 3},
            },
        )
        client = PermissionClient()
        async_client = AsyncMock()
        async_client.__aenter__.return_value = async_client
        async_client.__aexit__.return_value = False
        async_client.post.return_value = response

        with patch("src.auth.client.httpx.AsyncClient", return_value=async_client):
            permissions = await client.fetch_project_tool_permissions("project-1", "user-1")

        self.assertEqual(permissions, {"read_file": 1, "bash": 3})

    async def test_permission_client_raises_invalid_response_for_bad_schema(self):
        response = httpx.Response(200, json={"read_file": "high"})
        client = PermissionClient()
        async_client = AsyncMock()
        async_client.__aenter__.return_value = async_client
        async_client.__aexit__.return_value = False
        async_client.post.return_value = response

        with patch("src.auth.client.httpx.AsyncClient", return_value=async_client):
            with self.assertRaises(PermissionInvalidResponseError):
                await client.fetch_project_tool_permissions("project-1", "user-1")

    async def test_permission_client_raises_access_denied_for_403(self):
        response = httpx.Response(403, text="forbidden")
        client = PermissionClient()
        async_client = AsyncMock()
        async_client.__aenter__.return_value = async_client
        async_client.__aexit__.return_value = False
        async_client.post.return_value = response

        with patch("src.auth.client.httpx.AsyncClient", return_value=async_client):
            with self.assertRaises(PermissionAccessDeniedError):
                await client.fetch_project_tool_permissions("project-1", "user-1")

    async def test_permission_client_raises_backend_unavailable_on_timeout(self):
        request = httpx.Request("POST", "http://localhost")
        client = PermissionClient()
        async_client = AsyncMock()
        async_client.__aenter__.return_value = async_client
        async_client.__aexit__.return_value = False
        async_client.post.side_effect = httpx.ReadTimeout("timeout", request=request)

        with patch("src.auth.client.httpx.AsyncClient", return_value=async_client):
            with self.assertRaises(PermissionBackendUnavailableError):
                await client.fetch_project_tool_permissions("project-1", "user-1")


class AuthClientTests(unittest.IsolatedAsyncioTestCase):
    async def test_auth_client_sends_internal_key_and_context(self):
        response = httpx.Response(
            200,
            json={
                "isSuccess": True,
                "code": "COMMON-200",
                "message": "성공입니다.",
                "result": {
                    "user_id": "3",
                    "project_id": "1",
                    "permission_level": 2,
                },
            },
        )
        client = AuthClient()
        async_client = AsyncMock()
        async_client.__aenter__.return_value = async_client
        async_client.__aexit__.return_value = False
        async_client.post.return_value = response

        with patch("src.auth.client.httpx.AsyncClient", return_value=async_client):
            session = await client.verify_token(
                "access-token",
                chat_session_id="10",
                project_id="1",
            )

        self.assertEqual(session.user_id, 3)
        self.assertEqual(session.project_id, 1)
        self.assertEqual(session.permission_level, 2)
        async_client.post.assert_awaited_once_with(
            client.verify_url,
            headers={"X-Internal-Api-Key": settings.SPRING_BOOT_INTERNAL_API_KEY},
            json={
                "token": "access-token",
                "chatSessionId": "10",
                "projectId": "1",
            },
            timeout=client.timeout,
        )

    async def test_auth_client_returns_502_for_non_numeric_identifier_response(self):
        response = httpx.Response(
            200,
            json={
                "isSuccess": True,
                "code": "COMMON-200",
                "message": "성공입니다.",
                "result": {
                    "user_id": "abc",
                    "project_id": "1",
                    "permission_level": 2,
                },
            },
        )
        client = AuthClient()
        async_client = AsyncMock()
        async_client.__aenter__.return_value = async_client
        async_client.__aexit__.return_value = False
        async_client.post.return_value = response

        with patch("src.auth.client.httpx.AsyncClient", return_value=async_client):
            with self.assertRaises(HTTPException) as context:
                await client.verify_token("access-token")

        self.assertEqual(context.exception.status_code, 502)
        self.assertEqual(
            context.exception.detail,
            "Authentication service returned invalid session data",
        )


class InternalClientHeaderTests(unittest.IsolatedAsyncioTestCase):
    async def test_billing_client_sends_internal_key_and_idempotency_key(self):
        response = httpx.Response(200, json={"ok": True})
        client = BillingClient()
        async_client = AsyncMock()
        async_client.__aenter__.return_value = async_client
        async_client.__aexit__.return_value = False
        async_client.post.return_value = response
        report = BillingUsageReport(
            user_id=3,
            project_id=1,
            usage=UsageMetrics(prompt_tokens=1, completion_tokens=2, total_tokens=3, model_name="gpt"),
        )

        with patch("src.auth.client.httpx.AsyncClient", return_value=async_client):
            ok = await client.report_usage(report, idempotency_key="idem-1")

        self.assertTrue(ok)
        async_client.post.assert_awaited_once_with(
            client.usage_url,
            json=report.model_dump(mode="json"),
            headers={
                "X-Internal-Api-Key": settings.SPRING_BOOT_INTERNAL_API_KEY,
                "X-Idempotency-Key": "idem-1",
            },
            timeout=client.timeout,
        )

    async def test_agent_client_sends_internal_key(self):
        response = httpx.Response(201, json={"ok": True})
        client = AgentClient()
        async_client = AsyncMock()
        async_client.__aenter__.return_value = async_client
        async_client.__aexit__.return_value = False
        async_client.post.return_value = response
        payload = AgentToolPlanPayload(
            projectMemberId=1,
            chatSessionId=10,
            toolName="weather_tool",
            rawMarkdown="## Plan",
            structuredPlan=StructuredPlan(
                goal="goal",
                overview=["a"],
                approach="approach",
                keyDecisions=["x"],
                steps=[],
                risks=["r"],
                successCriteria=["done"],
            ),
        )

        with patch("src.auth.client.httpx.AsyncClient", return_value=async_client):
            ok = await client.save_tool_plan(payload)

        self.assertTrue(ok)
        async_client.post.assert_awaited_once_with(
            client.save_plan_url,
            headers={"X-Internal-Api-Key": settings.SPRING_BOOT_INTERNAL_API_KEY},
            json=payload.model_dump(mode="json"),
            timeout=client.timeout,
        )


if __name__ == "__main__":
    unittest.main()
