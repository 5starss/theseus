import logging

import httpx
from fastapi import HTTPException, status
from pydantic import TypeAdapter
from pydantic import ValidationError
from src.auth.schemas import UserSession, BillingUsageReport, AgentToolPlanPayload
from src.config import settings

logger = logging.getLogger(__name__)

INTERNAL_API_KEY_HEADER = "X-Internal-Api-Key"


def internal_api_headers() -> dict[str, str]:
    return {INTERNAL_API_KEY_HEADER: settings.SPRING_BOOT_INTERNAL_API_KEY}


def unwrap_api_response(payload: object) -> object:
    if isinstance(payload, dict) and "isSuccess" in payload and "result" in payload:
        return payload["result"]

    return payload


class PermissionClientError(Exception):
    """Base error for project tool permission lookups."""


class PermissionAccessDeniedError(PermissionClientError):
    """Raised when the caller cannot access the project."""


class PermissionInvalidResponseError(PermissionClientError):
    """Raised when the backend returns invalid permission payloads."""


class PermissionBackendUnavailableError(PermissionClientError):
    """Raised when the backend cannot serve permission lookups."""

class AuthClient:
    def __init__(self):
        self.verify_url = settings.SPRING_BOOT_AUTH_VERIFY_URL
        self.timeout = settings.AUTH_TIMEOUT_SECONDS

    async def verify_token(
        self,
        token: str,
        chat_session_id: str | None = None,
        project_id: str | None = None,
    ) -> UserSession:
        """
        Spring Boot 서버에 토큰 검증 요청을 보냅니다.
        """
        payload: dict[str, str] = {"token": token}
        if chat_session_id:
            payload["chatSessionId"] = chat_session_id
        if project_id:
            payload["projectId"] = project_id

        async with httpx.AsyncClient() as client:
            try:
                response = await client.post(
                    self.verify_url,
                    headers=internal_api_headers(),
                    json=payload,
                    timeout=self.timeout
                )
                
                if response.status_code == 200:
                    try:
                        return UserSession(**unwrap_api_response(response.json()))
                    except (TypeError, ValidationError) as exc:
                        logger.error(f"Invalid auth response schema: {exc}")
                        raise HTTPException(
                            status_code=status.HTTP_502_BAD_GATEWAY,
                            detail="Authentication service returned invalid session data"
                        )
                elif response.status_code in [401, 403]:
                    raise HTTPException(
                        status_code=response.status_code,
                        detail="Invalid or expired token"
                    )
                else:
                    logger.error(f"Auth server error: {response.status_code} - {response.text}")
                    raise HTTPException(
                        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                        detail="Authentication service error"
                    )
                    
            except httpx.RequestError as exc:
                logger.error(f"Failed to connect to auth server: {exc}")
                raise HTTPException(
                    status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                    detail="Authentication service unavailable"
                )


class PermissionClient:
    def __init__(self):
        self.permissions_url = settings.SPRING_BOOT_PROJECT_PERMISSIONS_URL
        self.timeout = settings.INTERNAL_API_TIMEOUT_SECONDS
        self._response_adapter = TypeAdapter(dict[str, int])

    async def fetch_project_tool_permissions(
        self,
        project_id: str,
        user_id: str,
    ) -> dict[str, int]:
        async with httpx.AsyncClient() as client:
            try:
                response = await client.post(
                    self.permissions_url,
                    headers=internal_api_headers(),
                    json={"projectId": project_id, "userId": user_id},
                    timeout=self.timeout,
                )
            except httpx.RequestError as exc:
                logger.error(f"Failed to connect to permission server: {exc}")
                raise PermissionBackendUnavailableError from exc

        if response.status_code == 200:
            try:
                return self._response_adapter.validate_python(unwrap_api_response(response.json()))
            except (ValueError, ValidationError) as exc:
                logger.error(f"Invalid permission response schema: {exc}")
                raise PermissionInvalidResponseError from exc

        if response.status_code == 403:
            raise PermissionAccessDeniedError

        logger.error(
            "Permission server error: %s - %s",
            response.status_code,
            response.text,
        )
        raise PermissionBackendUnavailableError

class BillingClient:
    def __init__(self):
        self.usage_url = settings.SPRING_BOOT_BILLING_USAGE_URL
        self.timeout = settings.INTERNAL_API_TIMEOUT_SECONDS

    async def report_usage(
        self,
        report: BillingUsageReport,
        idempotency_key: str | None = None,
    ) -> bool:
        """
        Spring Boot 서버에 사용량(Usage) 보고를 수행합니다.
        BackgroundTasks에서 호출되므로 예외를 직접 발생시키지 않고 로깅만 수행합니다.
        """
        async with httpx.AsyncClient() as client:
            try:
                headers = {}
                if idempotency_key:
                    headers["X-Idempotency-Key"] = idempotency_key
                headers.update(internal_api_headers())

                response = await client.post(
                    self.usage_url,
                    json=report.model_dump(mode="json"),
                    headers=headers,
                    timeout=self.timeout
                )
                
                if response.status_code == 200:
                    logger.info(f"Successfully reported usage for user {report.user_id}")
                    return True
                else:
                    logger.error(f"Failed to report usage: {response.status_code} - {response.text}")
                    return False
                    
            except httpx.RequestError as exc:
                logger.error(f"Failed to connect to billing server: {exc}")
                return False

class AgentClient:
    """
    AI 에이전트의 결과물(Tool Plan 등)을 Backend(Spring)에 전송하는 클라이언트
    """
    def __init__(self):
        self.save_plan_url = settings.SPRING_BOOT_TOOL_PLAN_URL
        self.timeout = settings.INTERNAL_API_TIMEOUT_SECONDS

    async def save_tool_plan(self, payload: AgentToolPlanPayload) -> bool:
        """
        생성된 도구 플랜을 Spring 서버에 저장하도록 요청합니다.
        """
        async with httpx.AsyncClient() as client:
            try:
                response = await client.post(
                    self.save_plan_url,
                    headers=internal_api_headers(),
                    json=payload.model_dump(mode="json"),
                    timeout=self.timeout
                )
                
                if response.status_code in [200, 201]:
                    logger.info(f"Successfully saved tool plan: {payload.toolName}")
                    return True
                else:
                    logger.error(f"Failed to save tool plan: {response.status_code} - {response.text}")
                    return False
                    
            except httpx.RequestError as exc:
                logger.error(f"Failed to connect to backend server for plan storage: {exc}")
                return False

auth_client = AuthClient()
permission_client = PermissionClient()
billing_client = BillingClient()
agent_client = AgentClient()
