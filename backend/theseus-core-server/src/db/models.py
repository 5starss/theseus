import uuid

from sqlalchemy import Column, String, Integer, DateTime, ForeignKey, Text, UniqueConstraint
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


class CoreRunCheckpoint(Base):
    __tablename__ = "core_run_checkpoints"

    run_id = Column(String(64), primary_key=True)
    project_id = Column(Integer, index=True, nullable=False)
    chat_session_id = Column(Integer, index=True, nullable=False)
    request_type = Column(String(50), nullable=False)
    mode = Column(String(30), nullable=False)
    status = Column(String(30), index=True, nullable=False)
    checkpoint_version = Column(Integer, nullable=False, default=1)
    state_machine_json = Column(JSONB, nullable=False, default=dict)
    conversation_json = Column(JSONB, nullable=False, default=list)
    tool_trace_json = Column(JSONB, nullable=True)
    progress_json = Column(JSONB, nullable=True)
    last_event_sequence = Column(Integer, nullable=False, default=0)
    retry_count = Column(Integer, nullable=False, default=0)
    last_error_code = Column(String(100), nullable=True)
    last_error_message = Column(Text, nullable=True)
    lease_owner = Column(String(100), nullable=True)
    lease_expires_at = Column(DateTime(timezone=True), nullable=True)
    requested_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)
    completed_at = Column(DateTime(timezone=True), nullable=True)

    events = relationship("CoreRunEvent", back_populates="checkpoint", cascade="all, delete-orphan")


class CoreRunEvent(Base):
    __tablename__ = "core_run_events"
    __table_args__ = (
        UniqueConstraint("run_id", "event_sequence", name="uk_core_run_events_run_sequence"),
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    run_id = Column(String(64), ForeignKey("core_run_checkpoints.run_id"), index=True, nullable=False)
    event_sequence = Column(Integer, nullable=False)
    event_type = Column(String(80), nullable=False)
    payload_json = Column(JSONB, nullable=False)
    publish_status = Column(String(30), nullable=False, default="pending", index=True)
    publish_attempts = Column(Integer, nullable=False, default=0)
    last_error = Column(Text, nullable=True)
    published_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    checkpoint = relationship("CoreRunCheckpoint", back_populates="events")
