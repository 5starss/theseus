import httpx
from fastapi import HTTPException, status
from src.config import settings
from src.auth.schemas import UserSession
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
                    return UserSession(**response.json())
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

auth_client = AuthClient()
