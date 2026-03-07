from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


class Document(BaseModel):
    """RAG 파이프라인에서 사용하는 표준 문서 스키마."""

    id: str = Field(..., description="문서 고유 식별자")
    source: str = Field(..., description="데이터 출처")
    published_at: str = Field(..., description="발행 시각")
    title: str = Field(..., description="문서 제목")
    body: str = Field(..., description="임베딩 대상 본문")
    url: Optional[str] = Field(default=None, description="원문 URL")
    source_rank: float = Field(default=1.0, description="출처 신뢰도(0~1)")
