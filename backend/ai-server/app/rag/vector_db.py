import logging
import os
import time
from typing import List, Optional

from langchain_chroma import Chroma
from langchain_core.documents import Document as LangChainDocument
from rank_bm25 import BM25Okapi

from app.rag.embedder import UpstageEmbedder
from app.schemas import Document as AppDocument

logger = logging.getLogger(__name__)


class NewsVectorDB:
    """뉴스/커뮤니티 문서를 임베딩해 ChromaDB에 저장/검색하는 벡터 저장소."""

    def __init__(self, collection_name: str = "kis_news_titles"):
        base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "../.."))
        self.persist_directory = os.getenv("AI_SERVER_CHROMA_DIR", os.path.join(base_dir, "chroma_db"))
        self.embedder = UpstageEmbedder()
        self.collection_name = collection_name

        self.vector_store = Chroma(
            collection_name=self.collection_name,
            embedding_function=self.embedder.get_embedding_model(),
            persist_directory=self.persist_directory,
        )
        self.bm25: Optional[BM25Okapi] = None
        self.all_docs: List[LangChainDocument] = []

    def add_documents(self, documents: List[AppDocument]) -> int:
        if not documents:
            logger.warning("색인할 문서가 없습니다.")
            return 0

        lc_docs = [
            LangChainDocument(
                page_content=doc.body,
                metadata={
                    "id": doc.id,
                    "source": doc.source,
                    "published_at": doc.published_at,
                    "title": doc.title,
                    "url": doc.url,
                    "source_rank": doc.source_rank,
                },
            )
            for doc in documents
        ]

        start_ts = time.perf_counter()
        self.vector_store.add_documents(lc_docs)
        elapsed = time.perf_counter() - start_ts
        logger.info("[API 시간] 벡터 색인(add_documents): %s건, %.2f초", len(lc_docs), elapsed)
        return len(lc_docs)

    def query(self, query_text: str, k: int = 5) -> List[LangChainDocument]:
        start_ts = time.perf_counter()
        results = self.vector_store.similarity_search(query_text, k=k)
        elapsed = time.perf_counter() - start_ts
        logger.info("[API 시간] 벡터 검색(similarity_search): k=%s, %.2f초", k, elapsed)
        return results

    def _load_all_documents(self) -> List[LangChainDocument]:
        results = self.vector_store.get()
        docs: List[LangChainDocument] = []
        ids = results.get("ids", [])
        documents = results.get("documents", [])
        metadatas = results.get("metadatas", [])

        for i in range(len(ids)):
            docs.append(
                LangChainDocument(
                    page_content=documents[i],
                    metadata=metadatas[i],
                )
            )
        return docs

    def _prepare_bm25(self, documents: List[LangChainDocument]):
        if not documents:
            self.bm25 = None
            self.all_docs = []
            return

        self.all_docs = documents
        tokenized_corpus = [doc.page_content.split() for doc in documents]
        self.bm25 = BM25Okapi(tokenized_corpus)
        logger.info("BM25 인덱스 준비 완료: %s건", len(documents))

    def hybrid_query(self, query_text: str, k: int = 5, source_filter: Optional[str] = None) -> List[LangChainDocument]:
        if not self.bm25:
            self._prepare_bm25(self._load_all_documents())

        if not self.bm25:
            return self.query(query_text, k=k)

        start_ts = time.perf_counter()
        if source_filter:
            vector_results = self.vector_store.similarity_search(
                query_text,
                k=k * 3,
                filter={"source": source_filter},
            )
        else:
            vector_results = self.vector_store.similarity_search(query_text, k=k * 3)
        elapsed = time.perf_counter() - start_ts
        logger.info(
            "[API 시간] 하이브리드 벡터 검색(similarity_search)%s: %.2f초",
            f" [필터: {source_filter}]" if source_filter else "",
            elapsed,
        )

        tokenized_query = query_text.split()
        bm25_scores = self.bm25.get_scores(tokenized_query)
        bm25_top_indices = sorted(range(len(bm25_scores)), key=lambda i: bm25_scores[i], reverse=True)

        bm25_results: List[LangChainDocument] = []
        for i in bm25_top_indices:
            if bm25_scores[i] <= 0:
                continue
            doc = self.all_docs[i]
            if source_filter and doc.metadata.get("source") != source_filter:
                continue
            bm25_results.append(doc)
            if len(bm25_results) >= k * 3:
                break

        rrf_scores = {}
        for rank, doc in enumerate(vector_results):
            doc_id = doc.metadata.get("id")
            if not doc_id:
                continue
            rrf_scores[doc_id] = rrf_scores.get(doc_id, 0.0) + 1.0 / (rank + 60)
        for rank, doc in enumerate(bm25_results):
            doc_id = doc.metadata.get("id")
            if not doc_id:
                continue
            rrf_scores[doc_id] = rrf_scores.get(doc_id, 0.0) + 1.0 / (rank + 60)

        sorted_ids = sorted(rrf_scores.keys(), key=lambda x: rrf_scores[x], reverse=True)[:k]
        id_to_doc = {doc.metadata.get("id"): doc for doc in vector_results + bm25_results}
        final_results = [id_to_doc[doc_id] for doc_id in sorted_ids if doc_id in id_to_doc]

        logger.info(
            "하이브리드 검색 완료%s: %s건",
            f" [필터: {source_filter}]" if source_filter else "",
            len(final_results),
        )
        return final_results

    def delete_collection(self):
        self.vector_store.delete_collection()
        self.vector_store = Chroma(
            collection_name=self.collection_name,
            embedding_function=self.embedder.get_embedding_model(),
            persist_directory=self.persist_directory,
        )
        self.bm25 = None
        self.all_docs = []
