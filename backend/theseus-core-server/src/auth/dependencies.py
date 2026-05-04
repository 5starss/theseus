from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from src.config import settings
from src.auth.schemas import SessionContext, UserSession
from src.auth.client import auth_client
from typing import Optional

security = HTTPBearer(auto_error=False)

async def get_bearer_token(
    auth: Optional[HTTPAuthorizationCredentials] = Depends(security),
) -> str:
    """
    Authorization Header에서 Bearer 토큰을 추출합니다.
    """
    if auth:
        return auth.credentials

    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Missing authentication token",
        headers={"WWW-Authenticate": "Bearer"},
    )


async def get_sse_token(
    request: Request,
    auth: Optional[HTTPAuthorizationCredentials] = Depends(security),
) -> str:
    """
    SSE 연결에서는 Header(Bearer) 또는 Query Parameter(token)에서 토큰을 추출합니다.
    """
    if auth:
        return auth.credentials

    token = request.query_params.get("token")
    if token:
        return token

    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Missing authentication token",
        headers={"WWW-Authenticate": "Bearer"},
    )

async def get_session_context(
    token: str = Depends(get_bearer_token)
) -> SessionContext:
    """
    추출된 토큰을 검증하고 세션 컨텍스트를 반환합니다.
    AUTH_MODE=mock인 경우 고정된 데이터를 반환합니다.
    """
    if settings.AUTH_MODE == "mock":
        # Mock 모드: 고정 데이터 반환
        return SessionContext(
            user_id="dev-user",
            project_id="dev-project",
            permission_level=3,  # Admin 권한 부여
            token=token
        )
    
    # 실제 Spring Boot 연동 모드
    user_session: UserSession = await auth_client.verify_token(token)
    
    return SessionContext(
        user_id=user_session.user_id,
        project_id=user_session.project_id,
        permission_level=user_session.permission_level,
        token=token
    )


async def get_sse_session_context(
    request: Request,
    token: str = Depends(get_sse_token)
) -> SessionContext:
    """
    SSE 전용 토큰 추출 방식을 사용하는 세션 컨텍스트 의존성입니다.
    """
    if settings.AUTH_MODE == "mock":
        return SessionContext(
            user_id="dev-user",
            project_id="dev-project",
            permission_level=3,
            token=token
        )

    user_session: UserSession = await auth_client.verify_token(
        token,
        chat_session_id=request.query_params.get("chat_session_id"),
        project_id=request.query_params.get("project_id"),
    )

    return SessionContext(
        user_id=user_session.user_id,
        project_id=user_session.project_id,
        permission_level=user_session.permission_level,
        token=token
    )
