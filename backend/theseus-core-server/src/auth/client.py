import httpx
from fastapi import HTTPException, status
from pydantic import ValidationError
from src.config import settings
from src.auth.schemas import UserSession, BillingUsageReport, AgentToolPlanPayload
import logging

logger = logging.getLogger(__name__)

class AuthClient:
    def __init__(self):
        self.verify_url = settings.SPRING_BOOT_AUTH_VERIFY_URL
        self.timeout = settings.AUTH_TIMEOUT_SECONDS

    async def verify_token(self, token: str) -> UserSession:
        """
        Spring Boot 서버에 토큰 검증 요청을 보냅니다.
        """
        async with httpx.AsyncClient() as client:
            try:
                response = await client.post(
                    self.verify_url,
                    json={"token": token},
                    timeout=self.timeout
                )
                
                if response.status_code == 200:
                    try:
                        return UserSession(**response.json())
                    except ValidationError as exc:
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
billing_client = BillingClient()
agent_client = AgentClient()
