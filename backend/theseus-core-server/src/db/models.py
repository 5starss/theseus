import uuid

from sqlalchemy import Column, String, Integer, DateTime, ForeignKey, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from pgvector.sqlalchemy import Vector
from src.db.postgres import Base
from src.config import settings

class KnowledgeDocument(Base):
    __tablename__ = "knowledge_documents"

    id = Column(String(36), primary_key=True)
    project_id = Column(String(36), index=True, nullable=False)
    source_type = Column(String(50), nullable=False) # e.g., "pdf", "notion", "web"
    source_uri = Column(String(512), nullable=False)
    title = Column(String(255), nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    # 관계 설정 (Cascade delete)
    chunks = relationship("KnowledgeChunk", back_populates="document", cascade="all, delete-orphan")


class KnowledgeChunk(Base):
    __tablename__ = "knowledge_chunks"

    id = Column(String(36), primary_key=True)
    document_id = Column(String(36), ForeignKey("knowledge_documents.id"), index=True, nullable=False)
    project_id = Column(String(36), index=True, nullable=False)
    chunk_index = Column(Integer, nullable=False)
    content = Column(Text, nullable=False)
    metadata_json = Column(JSONB, nullable=True) # 추가 메타데이터
    
    # pgvector 임베딩 컬럼 (차원 수는 config에서 주입)
    embedding = Column(Vector(settings.VECTOR_DIMENSION))
    
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    # 관계 설정
    document = relationship("KnowledgeDocument", back_populates="chunks")


class BillingOutbox(Base):
    __tablename__ = "billing_outbox"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String(255), nullable=False, index=True)
    project_id = Column(String(255), nullable=False, index=True)
    usage_data = Column(JSONB, nullable=False)
    status = Column(String(32), nullable=False, default="pending", index=True)
    retry_count = Column(Integer, nullable=False, default=0)
    last_error = Column(Text, nullable=True)
    next_retry_at = Column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        index=True,
    )
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )


class ToolPlan(Base):
    __tablename__ = "tool_plans"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    project_id = Column(String(36), index=True, nullable=False)
    chat_session_id = Column(Integer, index=True, nullable=False)
    status = Column(String(32), index=True, nullable=False, default="drafting")
    goal = Column(Text, nullable=False)
    content = Column(JSONB, nullable=False)
    feedback = Column(Text, nullable=True)
    executing_started_at = Column(DateTime(timezone=True), nullable=True)
    executing_by_user_id = Column(String(255), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )
