"""RAG 설정 모듈: .env로부터 DB/임베딩 설정을 로드합니다.

환경변수 참조:
    - POSTGRES_HOST, POSTGRES_PORT, POSTGRES_DB,
      POSTGRES_USER, POSTGRES_PASSWORD, POSTGRES_SCHEMA
    - EMBEDDING_PROVIDER, EMBEDDING_MODEL,
      VECTOR_DIMENSION, RAG_TOP_K, RAG_MIN_SCORE
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field


@dataclass(frozen=True)
class PostgresConfig:
    """PostgreSQL 연결 설정.

    Attributes:
        host: DB 호스트 주소.
        port: DB 포트.
        database: DB 이름.
        user: DB 사용자.
        password: DB 비밀번호.
        schema: 사용할 스키마 이름.
    """

    host: str = field(default_factory=lambda: os.getenv(
        "POSTGRES_HOST", "localhost",
    ))
    port: int = field(default_factory=lambda: int(os.getenv(
        "POSTGRES_PORT", "15432",
    )))
    database: str = field(default_factory=lambda: os.getenv(
        "POSTGRES_DB", "theseus_core",
    ))
    user: str = field(default_factory=lambda: os.getenv(
        "POSTGRES_USER", "root",
    ))
    password: str = field(default_factory=lambda: os.getenv(
        "POSTGRES_PASSWORD", "root",
    ))
    schema: str = field(default_factory=lambda: os.getenv(
        "POSTGRES_SCHEMA", "public",
    ))

    @property
    def dsn(self) -> str:
        """psycopg2 호환 DSN 문자열을 반환합니다."""
        return (
            f"host={self.host} port={self.port} "
            f"dbname={self.database} user={self.user} "
            f"password={self.password}"
        )

    @property
    def async_url(self) -> str:
        """asyncpg 호환 URL 문자열을 반환합니다."""
        return (
            f"postgresql://{self.user}:{self.password}"
            f"@{self.host}:{self.port}/{self.database}"
        )


@dataclass(frozen=True)
class EmbeddingConfig:
    """임베딩 프로바이더 설정.

    Attributes:
        provider: 'local' (sentence-transformers) 또는
                  'remote' (openai).
        model: 임베딩 모델 이름.
        dimension: 벡터 차원 수.
    """

    provider: str = field(default_factory=lambda: os.getenv(
        "EMBEDDING_PROVIDER", "local",
    ))
    model: str = field(default_factory=lambda: os.getenv(
        "EMBEDDING_MODEL", "all-MiniLM-L6-v2",
    ))
    dimension: int = field(default_factory=lambda: int(os.getenv(
        "VECTOR_DIMENSION", "384",
    )))


@dataclass(frozen=True)
class RAGConfig:
    """RAG 검색 파라미터 설정.

    Attributes:
        top_k: 검색 시 반환할 최대 문서 수.
        min_score: 유사도 하한 임계값 (0~1).
    """

    top_k: int = field(default_factory=lambda: int(os.getenv(
        "RAG_TOP_K", "5",
    )))
    min_score: float = field(default_factory=lambda: float(
        os.getenv("RAG_MIN_SCORE", "0.5"),
    ))


def load_rag_configs() -> tuple[
    PostgresConfig, EmbeddingConfig, RAGConfig
]:
    """모든 RAG 관련 설정을 한번에 로드합니다.

    Returns:
        (PostgresConfig, EmbeddingConfig, RAGConfig) 튜플.
    """
    return PostgresConfig(), EmbeddingConfig(), RAGConfig()
