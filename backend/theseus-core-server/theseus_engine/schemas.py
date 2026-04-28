"""Theseus 에이전트 구조화된 출력(Structured Output) 스키마 정의.

Plan 모드에서 LLM이 반환하는 데이터의 형태를 Pydantic 모델로 정의합니다.
마크다운 파싱에 의존하지 않고, LLM이 직접 구조화된 JSON을
생성하도록 강제하여 파편화 없는 데이터를 확보합니다.
"""

import uuid
from typing import List, Optional

from pydantic import BaseModel, Field


class PlanStep(BaseModel):
    """플랜의 개별 실행 단계.

    description은 단계의 목적을 1문장으로 요약하고,
    sub_tasks에 구체적인 세부 작업들을 개별 항목으로 분리합니다.
    """

    step_number: int = Field(
        description="Step number, sequential starting from 1."
    )
    title: str = Field(
        description="Concise step title. "
        "Example: 'Define Pydantic input model'"
    )
    description: str = Field(
        description="One-sentence summary of what this step achieves."
    )
    sub_tasks: List[str] = Field(
        description="Granular list of individual action items "
        "within this step. Each sub_task should be a single, "
        "concrete, actionable sentence. Minimum 2 items."
    )
    output_artifacts: List[str] = Field(
        default_factory=list,
        description="List of files or artifacts produced by this step. "
        "Example: ['requirements.txt', 'src/models.py']"
    )
    dependencies: List[int] = Field(
        default_factory=list,
        description="Step numbers that must be completed before "
        "this step. Empty list if none."
    )
    estimated_complexity: str = Field(
        default="medium",
        description="Estimated complexity: 'low', 'medium', or 'high'."
    )


class PlanDocument(BaseModel):
    """LLM이 생성하는 구조화된 플랜 문서.

    Plan 모드의 Drafting 단계에서 LLM이 이 스키마에 맞추어
    JSON을 반환합니다. 모든 텍스트 필드는 단문으로 분리됩니다.
    """

    goal: str = Field(
        description="The user's original goal restated in one clear "
        "sentence."
    )
    overview: List[str] = Field(
        description="High-level summary broken into individual "
        "bullet points. Each item is one key aspect of the plan. "
        "2-4 items."
    )
    approach: str = Field(
        description="One-sentence description of the chosen "
        "technical approach."
    )
    key_decisions: List[str] = Field(
        description="List of important technical decisions and "
        "their rationale. Each item: 'Decision — Reason'. "
        "2-5 items."
    )
    steps: List[PlanStep] = Field(
        description="Ordered list of implementation steps."
    )
    risks: List[str] = Field(
        default_factory=list,
        description="Potential failure points. Each item should be "
        "a single risk with its mitigation in one sentence."
    )
    success_criteria: List[str] = Field(
        description="Checklist of conditions that define 'done'. "
        "Each item is one testable criterion. 2-5 items."
    )


# ---------------------------------------------------------------------------
# UI Rendering Models (Frontend / CLI)
# ---------------------------------------------------------------------------


class SubItem(BaseModel):
    """블록 내부의 개별 리뷰 가능 항목.

    각 sub_item에 고유 item_id를 부여하여 프론트엔드에서
    개별 코멘트, 수정, 승인/거부를 처리할 수 있도록 합니다.

    Attributes:
        item_id: 고유 식별자 (예: "sub-a1b2c3d4").
        index: 블록 내 순번 (1-based).
        content: 항목 본문 텍스트.
    """

    item_id: str = Field(
        default_factory=lambda: f"sub-{uuid.uuid4().hex[:8]}"
    )
    index: int = Field(description="1-based index within the parent block")
    content: str = Field(description="Text content of this sub-item")


class PlanBlock(BaseModel):
    """프론트엔드 리뷰 UI를 위한 블록 단위 데이터.

    PlanDocument의 각 요소를 프론트엔드에서 개별적으로
    렌더링하고 코멘트를 달 수 있도록 block_id를 부여합니다.
    sub_items 내 각 항목에도 개별 item_id가 있어
    세분화된 리뷰가 가능합니다.
    """

    block_id: str = Field(
        default_factory=lambda: f"blk-{uuid.uuid4().hex[:8]}"
    )
    block_type: str = Field(
        description=(
            "Block type: 'goal', 'overview', 'approach', "
            "'decisions', 'step', 'risks', 'criteria'"
        )
    )
    title: str = Field(description="Block title for display")
    content: str = Field(
        default="",
        description="Primary text content (summary line)"
    )
    sub_items: List[SubItem] = Field(
        default_factory=list,
        description="Granular sub-items, each with its own "
        "reviewable item_id"
    )
    editable: bool = Field(default=True)
    metadata: dict = Field(default_factory=dict)
