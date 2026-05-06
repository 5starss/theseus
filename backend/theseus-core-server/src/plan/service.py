from __future__ import annotations

from datetime import datetime, timezone

from fastapi import HTTPException, status
from sqlalchemy import Select, select
from sqlalchemy.orm import Session

from src.db.models import ToolPlan
from src.plan.schemas import PlanCreateRequest

PLAN_STATUS_DRAFTING = "drafting"
PLAN_STATUS_WAIT_FOR_REVIEW = "wait_for_review"
PLAN_STATUS_APPROVED = "approved"
PLAN_STATUS_REJECTED = "rejected"
PLAN_STATUS_EXECUTING = "executing"


def get_plan_for_project(db: Session, plan_id: str, project_id: str) -> ToolPlan | None:
    return db.execute(
        select(ToolPlan).where(
            ToolPlan.id == plan_id,
            ToolPlan.project_id == project_id,
        )
    ).scalar_one_or_none()


def get_plan_by_id(db: Session, plan_id: str) -> ToolPlan | None:
    return db.execute(select(ToolPlan).where(ToolPlan.id == plan_id)).scalar_one_or_none()


def list_plans_for_session(db: Session, project_id: str, chat_session_id: int) -> list[ToolPlan]:
    return list(
        db.execute(
            select(ToolPlan)
            .where(
                ToolPlan.project_id == project_id,
                ToolPlan.chat_session_id == chat_session_id,
            )
            .order_by(ToolPlan.created_at.desc())
        ).scalars().all()
    )


def create_plan(db: Session, project_id: str, request: PlanCreateRequest) -> ToolPlan:
    plan = ToolPlan(
        project_id=project_id,
        chat_session_id=request.chat_session_id,
        goal=request.goal,
        content=request.content.model_dump(mode="json"),
        status=PLAN_STATUS_DRAFTING,
    )
    db.add(plan)
    db.commit()
    db.refresh(plan)
    return plan


def _locked_plan_query(project_id: str, plan_id: str) -> Select:
    return (
        select(ToolPlan)
        .where(ToolPlan.project_id == project_id, ToolPlan.id == plan_id)
        .with_for_update()
    )


def require_plan_or_404(db: Session, project_id: str, plan_id: str) -> ToolPlan:
    plan = db.execute(_locked_plan_query(project_id, plan_id)).scalar_one_or_none()
    if plan is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Plan not found")
    return plan


def transition_submit(db: Session, project_id: str, plan_id: str) -> ToolPlan:
    plan = require_plan_or_404(db, project_id, plan_id)
    if plan.status != PLAN_STATUS_DRAFTING:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Only drafting plans can be submitted")
    plan.status = PLAN_STATUS_WAIT_FOR_REVIEW
    plan.feedback = None
    db.commit()
    db.refresh(plan)
    return plan


def transition_approve(db: Session, project_id: str, plan_id: str) -> ToolPlan:
    plan = require_plan_or_404(db, project_id, plan_id)
    if plan.status != PLAN_STATUS_WAIT_FOR_REVIEW:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Only plans waiting for review can be approved")
    plan.status = PLAN_STATUS_APPROVED
    plan.feedback = None
    db.commit()
    db.refresh(plan)
    return plan


def transition_reject(db: Session, project_id: str, plan_id: str, feedback: str) -> ToolPlan:
    plan = require_plan_or_404(db, project_id, plan_id)
    if plan.status != PLAN_STATUS_WAIT_FOR_REVIEW:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Only plans waiting for review can be rejected")
    plan.status = PLAN_STATUS_REJECTED
    plan.feedback = feedback
    db.commit()
    db.refresh(plan)
    return plan


def transition_execute(db: Session, project_id: str, plan_id: str, executing_user_id: str) -> ToolPlan:
    plan = require_plan_or_404(db, project_id, plan_id)
    if plan.status != PLAN_STATUS_APPROVED:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Only approved plans can be executed")

    session_plans = list(
        db.execute(
            select(ToolPlan)
            .where(
                ToolPlan.project_id == project_id,
                ToolPlan.chat_session_id == plan.chat_session_id,
            )
            .with_for_update()
        ).scalars().all()
    )
    existing = next(
        (
            item
            for item in session_plans
            if item.status == PLAN_STATUS_EXECUTING and item.id != plan.id
        ),
        None,
    )
    if existing is not None:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Another plan is already executing for this chat session")

    plan.status = PLAN_STATUS_EXECUTING
    plan.executing_started_at = datetime.now(timezone.utc)
    plan.executing_by_user_id = executing_user_id
    db.commit()
    db.refresh(plan)
    return plan


def validate_executing_plan_binding(
    db: Session,
    *,
    plan_id: str,
    project_id: str,
    chat_session_id: int,
) -> ToolPlan:
    plan = get_plan_for_project(db, plan_id, project_id)
    if plan is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Plan not found")
    if plan.chat_session_id != chat_session_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Plan does not belong to this chat session")
    if plan.status != PLAN_STATUS_EXECUTING:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Plan is not in executing state")
    return plan


def restore_plan_after_stream(
    db: Session,
    *,
    plan_id: str,
    project_id: str,
    chat_session_id: int,
    executing_user_id: str,
) -> ToolPlan | None:
    plan = db.execute(_locked_plan_query(project_id, plan_id)).scalar_one_or_none()
    if plan is None:
        return None
    if plan.chat_session_id != chat_session_id:
        return None
    if plan.status != PLAN_STATUS_EXECUTING:
        return None
    if plan.executing_by_user_id != executing_user_id:
        return None

    plan.status = PLAN_STATUS_APPROVED
    db.commit()
    db.refresh(plan)
    return plan


def assert_plan_is_executing(db: Session, plan_id: str) -> ToolPlan:
    plan = get_plan_by_id(db, plan_id)
    if plan is None:
        raise RuntimeError("Plan not found")
    if plan.status != PLAN_STATUS_EXECUTING:
        raise RuntimeError("Plan is not in executing state")
    return plan


def assert_plan_execution_context(
    db: Session,
    *,
    plan_id: str,
    project_id: str,
    chat_session_id: int,
    executing_user_id: str,
) -> ToolPlan:
    plan = assert_plan_is_executing(db, plan_id)
    if plan.project_id != project_id:
        raise RuntimeError("Plan does not belong to this project")
    if plan.chat_session_id != chat_session_id:
        raise RuntimeError("Plan does not belong to this chat session")
    if plan.executing_by_user_id != executing_user_id:
        raise RuntimeError("Plan is executing under a different user")
    return plan
