from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class Document(BaseModel):
    """RAG 파이프라인에서 사용하는 표준 문서 스키마."""

    id: str = Field(..., description="문서 고유 식별자")
    ticker: str = Field(..., description="종목 코드")
    source: str = Field(..., description="데이터 출처")
    published_at: str = Field(..., description="발행 시각")
    title: str = Field(..., description="문서 제목")
    body: str = Field(..., description="임베딩 대상 본문")
    url: Optional[str] = Field(default=None, description="원문 URL")
    source_rank: float = Field(default=1.0, description="출처 신뢰도(0~1)")


class QuantAdaptiveParams(BaseModel):
    th: float = Field(..., description="의사결정 threshold")
    hb: int = Field(..., description="hold bars")
    cb: float = Field(..., description="cost bps")


class QuantBacktestSummary(BaseModel):
    wr: float = Field(..., description="win rate")
    tc: int = Field(..., description="trade count")
    cr: float = Field(..., description="cumulative return")
    sh: float = Field(..., description="sharpe ratio")


class QuantDirectionSummary(BaseModel):
    acc: float = Field(..., description="directional accuracy")
    base: float = Field(..., description="directional accuracy baseline")


class QuantReliabilitySummary(BaseModel):
    band: Optional[str] = Field(default=None, description="high|medium|low")
    ok: bool = Field(..., description="LLM이 강한 근거로 써도 되는지 여부")
    flags: List[str] = Field(default_factory=list, description="품질 경고 플래그")
    reasons: List[str] = Field(default_factory=list, description="신뢰도 판단 근거")


class QuantModelEvidence(BaseModel):
    profile: Optional[str] = Field(default=None, description="feature profile")
    model_type: Optional[str] = Field(default=None, description="model type")
    ap: QuantAdaptiveParams
    bt: QuantBacktestSummary
    dir: QuantDirectionSummary
    rel: QuantReliabilitySummary
    signal: Optional[str] = Field(default=None, description="BULLISH|BEARISH|NEUTRAL")


class QuantGuardrails(BaseModel):
    is_reliable: bool = Field(..., description="LLM이 강한 stance를 고려해도 되는지 여부")
    confidence_band: Optional[str] = Field(default=None, description="overall confidence band")
    risk_flags: List[str] = Field(default_factory=list, description="통합 위험 플래그")
    allowed_stances: List[str] = Field(default_factory=list, description="허용된 최종 stance")
    blocked_stances: List[str] = Field(default_factory=list, description="금지된 최종 stance")
    hard_constraints: List[str] = Field(default_factory=list, description="반드시 지켜야 할 제약")
    reason_summary: List[str] = Field(default_factory=list, description="guardrail 요약 사유")
    avoid_if: str = Field(default="none", description="이 조건이면 회피")


class QuantEvidence(BaseModel):
    schema_version: str = Field(default="v3", description="schema version")
    generated_at: datetime = Field(..., description="evidence 생성 시각")
    ticker: str = Field(..., description="종목 코드")
    mode: str = Field(..., description="single_model|dual_model")
    summary: Dict[str, Any] = Field(default_factory=dict, description="상위 요약")
    guardrails: QuantGuardrails
    models: Dict[str, QuantModelEvidence] = Field(default_factory=dict, description="모델별 evidence")
    agreement: Dict[str, Any] = Field(default_factory=dict, description="dual model agreement")
