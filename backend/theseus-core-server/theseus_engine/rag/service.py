"""RAG 서비스 모듈: 문서 적재(Ingestion) 및 벡터 검색 비즈니스 로직.

DatabaseManager와 EmbeddingProvider를 조합하여
문서 청킹(Chunking), 임베딩, 적재, 유사도 검색 등
핵심 RAG 파이프라인을 제공합니다.
"""

from __future__ import annotations

import logging
import re
from typing import Any, Dict, List, Optional

from theseus_engine.rag.config import (
    EmbeddingConfig,
    PostgresConfig,
    RAGConfig,
    load_rag_configs,
)
from theseus_engine.rag.database import DatabaseManager
from theseus_engine.rag.embeddings import (
    BaseEmbeddingProvider,
    create_embedding_provider,
)

log = logging.getLogger(__name__)


class RAGService:
    """PostgreSQL pgvector 기반 RAG 서비스.

    문서 적재(Ingest), 벡터 검색(Search),
    텍스트 청킹(Chunking) 기능을 제공합니다.

    Args:
        pg_config: PostgreSQL 설정.
        emb_config: 임베딩 프로바이더 설정.
        rag_config: 검색 파라미터 설정.
    """

    def __init__(
        self,
        pg_config: Optional[PostgresConfig] = None,
        emb_config: Optional[EmbeddingConfig] = None,
        rag_config: Optional[RAGConfig] = None,
    ) -> None:
        _pg, _emb, _rag = load_rag_configs()
        self._pg_config = pg_config or _pg
        self._emb_config = emb_config or _emb
        self._rag_config = rag_config or _rag

        self._db: Optional[DatabaseManager] = None
        self._embedder: Optional[
            BaseEmbeddingProvider
        ] = None
        self._initialized = False

    # ------------------------------------------------------------------
    # 초기화 / 종료
    # ------------------------------------------------------------------

    def initialize(self) -> None:
        """DB 연결 + 스키마 초기화 + 임베딩 프로바이더를 로드합니다."""
        if self._initialized:
            return

        # DB 연결
        self._db = DatabaseManager(
            config=self._pg_config,
            dimension=self._emb_config.dimension,
        )
        self._db.connect()
        self._db.initialize_schema()

        # 임베딩 프로바이더
        self._embedder = create_embedding_provider(
            self._emb_config,
        )

        self._initialized = True
        log.info(
            "[RAG Service] Initialized. "
            "Provider=%s, Model=%s, Dim=%d",
            self._emb_config.provider,
            self._emb_config.model,
            self._emb_config.dimension,
        )

    def close(self) -> None:
        """리소스를 정리합니다."""
        if self._db:
            self._db.close()
        self._initialized = False

    @property
    def db(self) -> DatabaseManager:
        """활성 DatabaseManager를 반환합니다."""
        if not self._db:
            raise RuntimeError(
                "RAGService가 초기화되지 않았습니다. "
                "initialize()를 먼저 호출하세요."
            )
        return self._db

    @property
    def embedder(self) -> BaseEmbeddingProvider:
        """활성 EmbeddingProvider를 반환합니다."""
        if not self._embedder:
            raise RuntimeError(
                "RAGService가 초기화되지 않았습니다. "
                "initialize()를 먼저 호출하세요."
            )
        return self._embedder

    # ------------------------------------------------------------------
    # 텍스트 청킹
    # ------------------------------------------------------------------

    @staticmethod
    def chunk_text(
        text: str,
        chunk_size: int = 500,
        overlap: int = 50,
    ) -> List[str]:
        """텍스트를 겹침(Overlap)을 가진 청크로 분할합니다.

        문장 경계를 존중하여 자연스러운 분할을 시도합니다.

        Args:
            text: 원본 텍스트.
            chunk_size: 청크 최대 글자 수.
            overlap: 인접 청크 간 겹치는 글자 수.

        Returns:
            청크 문자열 리스트.
        """
        if not text or not text.strip():
            return []

        # 문장 단위로 분리
        sentences = re.split(
            r"(?<=[.!?。\n])\s+", text.strip(),
        )

        chunks: List[str] = []
        current_chunk: List[str] = []
        current_len = 0

        for sentence in sentences:
            sentence_len = len(sentence)

            if (
                current_len + sentence_len > chunk_size
                and current_chunk
            ):
                chunk_text = " ".join(current_chunk)
                chunks.append(chunk_text)

                # 오버랩: 마지막 문장들을 다음 청크로 이월
                overlap_text = chunk_text[-overlap:]
                current_chunk = [overlap_text]
                current_len = len(overlap_text)

            current_chunk.append(sentence)
            current_len += sentence_len

        # 마지막 청크 추가
        if current_chunk:
            chunks.append(" ".join(current_chunk))

        return chunks

    # ------------------------------------------------------------------
    # 문서 적재 (Ingestion)
    # ------------------------------------------------------------------

    def ingest_text(
        self,
        content: str,
        metadata: Optional[Dict[str, Any]] = None,
        chunk_size: int = 500,
        overlap: int = 50,
    ) -> List[int]:
        """텍스트를 청킹 후 임베딩하여 DB에 적재합니다.

        Args:
            content: 원본 텍스트.
            metadata: 문서 메타데이터.
            chunk_size: 청크 최대 글자 수.
            overlap: 오버랩 글자 수.

        Returns:
            생성된 문서 ID 리스트.
        """
        self.initialize()
        meta = metadata or {}

        chunks = self.chunk_text(
            content, chunk_size, overlap,
        )
        if not chunks:
            log.warning(
                "[RAG Service] No chunks generated "
                "from input text.",
            )
            return []

        embeddings = self.embedder.embed_texts(chunks)

        documents = []
        for i, (chunk, emb) in enumerate(
            zip(chunks, embeddings),
        ):
            doc_meta = {
                **meta,
                "chunk_index": i,
                "total_chunks": len(chunks),
            }
            documents.append((chunk, emb, doc_meta))

        ids = self.db.insert_documents_batch(documents)
        log.info(
            "[RAG Service] Ingested %d chunks "
            "from document (source=%s)",
            len(ids),
            meta.get("source", "unknown"),
        )
        return ids

    def ingest_file(
        self,
        file_path: str,
        metadata: Optional[Dict[str, Any]] = None,
        chunk_size: int = 500,
        overlap: int = 50,
        encoding: str = "utf-8",
    ) -> List[int]:
        """파일을 읽어 적재합니다.

        Args:
            file_path: 파일 경로.
            metadata: 추가 메타데이터.
            chunk_size: 청크 크기.
            overlap: 오버랩 크기.
            encoding: 파일 인코딩.

        Returns:
            생성된 문서 ID 리스트.
        """
        with open(file_path, "r", encoding=encoding) as f:
            content = f.read()

        meta = {
            "source": file_path,
            **(metadata or {}),
        }
        return self.ingest_text(
            content, meta, chunk_size, overlap,
        )

    # ------------------------------------------------------------------
    # 벡터 검색
    # ------------------------------------------------------------------

    def search(
        self,
        query: str,
        top_k: Optional[int] = None,
        min_score: Optional[float] = None,
    ) -> List[Dict[str, Any]]:
        """자연어 쿼리로 유사 문서를 검색합니다.

        Args:
            query: 검색 쿼리 텍스트.
            top_k: 반환할 최대 결과 수.
            min_score: 최소 유사도 임계값.

        Returns:
            검색된 문서 리스트.
        """
        self.initialize()

        k = top_k or self._rag_config.top_k
        score = min_score or self._rag_config.min_score

        query_embedding = self.embedder.embed_text(query)
        results = self.db.search_similar(
            query_embedding=query_embedding,
            top_k=k,
            min_score=score,
        )

        log.debug(
            "[RAG Service] Search for '%s' returned "
            "%d results",
            query[:50], len(results),
        )
        return results

    # ------------------------------------------------------------------
    # 유틸리티
    # ------------------------------------------------------------------

    def get_stats(self) -> Dict[str, Any]:
        """지식 베이스 통계를 반환합니다.

        Returns:
            {document_count, embedding_provider,
             embedding_model, vector_dimension} 딕셔너리.
        """
        self.initialize()
        return {
            "document_count": self.db.get_document_count(),
            "embedding_provider": (
                self._emb_config.provider
            ),
            "embedding_model": self._emb_config.model,
            "vector_dimension": (
                self._emb_config.dimension
            ),
            "rag_top_k": self._rag_config.top_k,
            "rag_min_score": self._rag_config.min_score,
        }


# ------------------------------------------------------------------
# 모듈 레벨 싱글톤 접근자
# ------------------------------------------------------------------

_service_instance: Optional[RAGService] = None


def get_rag_service() -> RAGService:
    """전역 RAGService 싱글톤을 반환합니다.

    Returns:
        초기화된 RAGService 인스턴스.
    """
    global _service_instance
    if _service_instance is None:
        _service_instance = RAGService()
    return _service_instance
