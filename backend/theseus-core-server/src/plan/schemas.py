from datetime import datetime

from pydantic import BaseModel, Field

from src.auth.schemas import StructuredPlan


class PlanCreateRequest(BaseModel):
    chat_session_id: int = Field(..., ge=1)
    goal: str = Field(..., min_length=1)
    content: StructuredPlan


class PlanRejectRequest(BaseModel):
    feedback: str = Field(..., min_length=1)


class PlanResponse(BaseModel):
    id: str
    project_id: str
    chat_session_id: int
    status: str
    goal: str
    content: StructuredPlan
    feedback: str | None = None
    executing_started_at: datetime | None = None
    executing_by_user_id: str | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None

    @classmethod
    def from_model(cls, plan) -> "PlanResponse":
        return cls(
            id=plan.id,
            project_id=plan.project_id,
            chat_session_id=plan.chat_session_id,
            status=plan.status,
            goal=plan.goal,
            content=StructuredPlan.model_validate(plan.content),
            feedback=plan.feedback,
            executing_started_at=plan.executing_started_at,
            executing_by_user_id=plan.executing_by_user_id,
            created_at=plan.created_at,
            updated_at=plan.updated_at,
        )
