"""PostgreSQL + pgvector 데이터베이스 관리 모듈.

pgvector 확장 설치와 스키마 초기화, 벡터 CRUD를
담당합니다. 동기(psycopg2) 커넥션 기반으로 구현됩니다.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional, Tuple

import psycopg2
import psycopg2.extras
from pgvector.psycopg2 import register_vector

from theseus_engine.rag.config import PostgresConfig

log = logging.getLogger(__name__)

# ------------------------------------------------------------------
# DDL: 테이블 및 인덱스 생성 SQL
# ------------------------------------------------------------------

_CREATE_EXTENSION_SQL = "CREATE EXTENSION IF NOT EXISTS vector;"

_CREATE_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS {schema}.knowledge_documents (
    id          BIGSERIAL PRIMARY KEY,
    content     TEXT NOT NULL,
    metadata    JSONB NOT NULL DEFAULT '{{}}'::jsonb,
    embedding   vector({dimension}),
    created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
"""

_CREATE_INDEX_SQL = """
CREATE INDEX IF NOT EXISTS idx_knowledge_embedding
ON {schema}.knowledge_documents
USING ivfflat (embedding vector_cosine_ops)
WITH (lists = 100);
"""


class DatabaseManager:
    """PostgreSQL pgvector 데이터베이스 매니저.

    Args:
        config: PostgreSQL 연결 설정.
        dimension: 임베딩 벡터 차원 수.
    """

    def __init__(
        self,
        config: PostgresConfig,
        dimension: int = 384,
    ) -> None:
        self._config = config
        self._dimension = dimension
        self._conn: Optional[psycopg2.extensions.connection] = None

    # ------------------------------------------------------------------
    # 연결 관리
    # ------------------------------------------------------------------

    def connect(self) -> None:
        """PostgreSQL에 연결하고 pgvector 타입을 등록합니다."""
        if self._conn and not self._conn.closed:
            return
        try:
            self._conn = psycopg2.connect(self._config.dsn)
            self._conn.autocommit = True
            
            # vector 확장이 없으면 register_vector가 실패하므로 먼저 생성합니다.
            with self._conn.cursor() as cur:
                cur.execute("CREATE EXTENSION IF NOT EXISTS vector;")
                
            register_vector(self._conn)
            log.info(
                "[RAG DB] Connected to PostgreSQL at "
                "%s:%d/%s",
                self._config.host,
                self._config.port,
                self._config.database,
            )
        except psycopg2.Error as e:
            log.error(
                "[RAG DB] Failed to connect: %s", e,
            )
            raise

    def close(self) -> None:
        """연결을 종료합니다."""
        if self._conn and not self._conn.closed:
            self._conn.close()
            log.info("[RAG DB] Connection closed.")

    @property
    def connection(
        self,
    ) -> psycopg2.extensions.connection:
        """활성 커넥션 객체를 반환합니다.

        Returns:
            psycopg2 connection 객체.

        Raises:
            RuntimeError: 연결이 초기화되지 않은 경우.
        """
        if not self._conn or self._conn.closed:
            raise RuntimeError(
                "DB 연결이 초기화되지 않았습니다. "
                "connect()를 먼저 호출하세요."
            )
        return self._conn

    # ------------------------------------------------------------------
    # 스키마 초기화
    # ------------------------------------------------------------------

    def initialize_schema(self) -> None:
        """pgvector 확장과 knowledge_documents 테이블을 생성합니다."""
        schema = self._config.schema
        dim = self._dimension

        with self.connection.cursor() as cur:
            cur.execute(_CREATE_EXTENSION_SQL)
            cur.execute(
                _CREATE_TABLE_SQL.format(
                    schema=schema, dimension=dim,
                ),
            )
            # IVFFlat 인덱스는 데이터가 충분할 때 생성
            try:
                cur.execute(
                    _CREATE_INDEX_SQL.format(schema=schema),
                )
            except psycopg2.Error:
                log.debug(
                    "[RAG DB] IVFFlat index creation "
                    "skipped (not enough rows yet).",
                )

        log.info(
            "[RAG DB] Schema initialized: "
            "%s.knowledge_documents (dim=%d)",
            schema, dim,
        )

    # ------------------------------------------------------------------
    # CRUD 메서드
    # ------------------------------------------------------------------

    def insert_document(
        self,
        content: str,
        embedding: List[float],
        metadata: Optional[Dict[str, Any]] = None,
    ) -> int:
        """문서와 임베딩 벡터를 삽입합니다.

        Args:
            content: 원본 텍스트 내용.
            embedding: 벡터 리스트.
            metadata: 부가 메타데이터 (출처, 태그 등).

        Returns:
            생성된 문서의 ID.
        """
        import numpy as np

        meta = metadata or {}
        vec = np.array(embedding, dtype=np.float32)
        schema = self._config.schema

        sql = f"""
        INSERT INTO {schema}.knowledge_documents
            (content, metadata, embedding)
        VALUES (%s, %s, %s)
        RETURNING id;
        """

        with self.connection.cursor() as cur:
            cur.execute(
                sql,
                (
                    content,
                    psycopg2.extras.Json(meta),
                    vec,
                ),
            )
            doc_id: int = cur.fetchone()[0]

        log.debug(
            "[RAG DB] Inserted document id=%d "
            "(len=%d chars)",
            doc_id, len(content),
        )
        return doc_id

    def insert_documents_batch(
        self,
        documents: List[
            Tuple[str, List[float], Dict[str, Any]]
        ],
    ) -> List[int]:
        """다수의 문서를 배치로 삽입합니다.

        Args:
            documents: (content, embedding, metadata)
                       튜플 리스트.

        Returns:
            생성된 문서 ID 리스트.
        """
        ids: List[int] = []
        for content, embedding, meta in documents:
            doc_id = self.insert_document(
                content, embedding, meta,
            )
            ids.append(doc_id)
        return ids

    def search_similar(
        self,
        query_embedding: List[float],
        top_k: int = 5,
        min_score: float = 0.5,
    ) -> List[Dict[str, Any]]:
        """코사인 유사도 기반으로 유사 문서를 검색합니다.

        Args:
            query_embedding: 쿼리 임베딩 벡터.
            top_k: 반환할 최대 결과 수.
            min_score: 최소 유사도 임계값 (0~1).

        Returns:
            검색된 문서 리스트.
            각 항목: {id, content, metadata, score}.
        """
        import numpy as np

        vec = np.array(query_embedding, dtype=np.float32)
        schema = self._config.schema

        sql = f"""
        SELECT
            id,
            content,
            metadata,
            1 - (embedding <=> %s) AS score
        FROM {schema}.knowledge_documents
        WHERE 1 - (embedding <=> %s) >= %s
        ORDER BY embedding <=> %s
        LIMIT %s;
        """

        with self.connection.cursor(
            cursor_factory=psycopg2.extras.RealDictCursor,
        ) as cur:
            cur.execute(
                sql, (vec, vec, min_score, vec, top_k),
            )
            rows = cur.fetchall()

        results: List[Dict[str, Any]] = []
        for row in rows:
            results.append({
                "id": row["id"],
                "content": row["content"],
                "metadata": row["metadata"],
                "score": float(row["score"]),
            })

        log.debug(
            "[RAG DB] Search returned %d results "
            "(top_k=%d, min_score=%.2f)",
            len(results), top_k, min_score,
        )
        return results

    def get_document_count(self) -> int:
        """현재 적재된 문서 수를 반환합니다.

        Returns:
            문서 수.
        """
        schema = self._config.schema
        sql = (
            f"SELECT COUNT(*) FROM "
            f"{schema}.knowledge_documents;"
        )
        with self.connection.cursor() as cur:
            cur.execute(sql)
            count: int = cur.fetchone()[0]
        return count

    def delete_document(self, doc_id: int) -> bool:
        """특정 문서를 ID 기반으로 삭제합니다.

        Args:
            doc_id: 삭제할 문서 ID.

        Returns:
            삭제 성공 여부.
        """
        schema = self._config.schema
        sql = (
            f"DELETE FROM {schema}.knowledge_documents "
            f"WHERE id = %s;"
        )
        with self.connection.cursor() as cur:
            cur.execute(sql, (doc_id,))
            deleted = cur.rowcount > 0
        return deleted
