from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime

class UserSession(BaseModel):
    """
    Spring Boot 인증 서버에서 토큰 검증 후 반환하는 세션 정보 모델
    """
    user_id: str
    project_id: str
    permission_level: int = Field(default=1, description="1: Read, 2: Write, 3: Admin")
    expires_at: Optional[datetime] = None

class SessionContext(BaseModel):
    """
    FastAPI 내부적으로 의존성 주입을 통해 전달될 세션 컨텍스트
    """
    user_id: str
    project_id: str
    permission_level: int
    token: str
