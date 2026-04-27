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

class UsageMetrics(BaseModel):
    """
    AI 에이전트 실행 중 발생하는 리소스 사용량 모델
    """
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0
    model_name: str = "default"

class BillingUsageReport(BaseModel):
    """
    Spring Boot Billing API로 전송할 최종 과금 보고서 모델
    """
    user_id: str
    project_id: str
    usage: UsageMetrics
    timestamp: datetime = Field(default_factory=datetime.utcnow)

# --- Tool Plan Storage Schemas ---

class PlanStep(BaseModel):
    stepNumber: int
    title: str
    description: str
    subTasks: list[str]
    dependencies: list[int]
    estimatedComplexity: str
    outputArtifacts: list[str]

class StructuredPlan(BaseModel):
    goal: str
    overview: list[str]
    approach: str
    keyDecisions: list[str]
    steps: list[PlanStep]
    risks: list[str]
    successCriteria: list[str]

class AgentToolPlanPayload(BaseModel):
    """
    AI 서버가 도구 플랜 생성을 완료한 후 Backend(Spring)에 저장을 요청할 때 사용하는 페이로드
    """
    projectMemberId: int
    chatSessionId: int
    toolName: str
    rawMarkdown: str
    structuredPlan: StructuredPlan
