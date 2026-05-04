from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from src.auth.dependencies import get_session_context
from src.auth.schemas import SessionContext
from src.db.postgres import get_db
from src.plan.schemas import PlanCreateRequest, PlanRejectRequest, PlanResponse
from src.plan.service import (
    create_plan,
    get_plan_for_project,
    list_plans_for_session,
    transition_approve,
    transition_execute,
    transition_reject,
    transition_submit,
)

router = APIRouter()


@router.post("/plans", response_model=PlanResponse)
async def create_plan_endpoint(
    request: PlanCreateRequest,
    session: SessionContext = Depends(get_session_context),
    db: Session = Depends(get_db),
) -> PlanResponse:
    return PlanResponse.from_model(create_plan(db, session.project_id, request))


@router.get("/plans/{plan_id}", response_model=PlanResponse)
async def get_plan_endpoint(
    plan_id: str,
    session: SessionContext = Depends(get_session_context),
    db: Session = Depends(get_db),
) -> PlanResponse:
    plan = get_plan_for_project(db, plan_id, session.project_id)
    if plan is None:
        from fastapi import HTTPException, status
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Plan not found")
    return PlanResponse.from_model(plan)


@router.get("/sessions/{chat_session_id}/plans", response_model=list[PlanResponse])
async def list_session_plans_endpoint(
    chat_session_id: int,
    session: SessionContext = Depends(get_session_context),
    db: Session = Depends(get_db),
) -> list[PlanResponse]:
    plans = list_plans_for_session(db, session.project_id, chat_session_id)
    return [PlanResponse.from_model(plan) for plan in plans]


@router.patch("/plans/{plan_id}/submit", response_model=PlanResponse)
async def submit_plan_endpoint(
    plan_id: str,
    session: SessionContext = Depends(get_session_context),
    db: Session = Depends(get_db),
) -> PlanResponse:
    return PlanResponse.from_model(transition_submit(db, session.project_id, plan_id))


@router.patch("/plans/{plan_id}/approve", response_model=PlanResponse)
async def approve_plan_endpoint(
    plan_id: str,
    session: SessionContext = Depends(get_session_context),
    db: Session = Depends(get_db),
) -> PlanResponse:
    return PlanResponse.from_model(transition_approve(db, session.project_id, plan_id))


@router.patch("/plans/{plan_id}/reject", response_model=PlanResponse)
async def reject_plan_endpoint(
    plan_id: str,
    request: PlanRejectRequest,
    session: SessionContext = Depends(get_session_context),
    db: Session = Depends(get_db),
) -> PlanResponse:
    return PlanResponse.from_model(transition_reject(db, session.project_id, plan_id, request.feedback))


@router.patch("/plans/{plan_id}/execute", response_model=PlanResponse)
async def execute_plan_endpoint(
    plan_id: str,
    session: SessionContext = Depends(get_session_context),
    db: Session = Depends(get_db),
) -> PlanResponse:
    return PlanResponse.from_model(transition_execute(db, session.project_id, plan_id, session.user_id))
