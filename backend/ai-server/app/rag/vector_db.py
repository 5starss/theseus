import logging
import os
import time
from typing import List

from langchain_chroma import Chroma
from langchain_core.documents import Document as LangChainDocument

from app.rag.embedder import UpstageEmbedder
from app.schemas import Document as AppDocument

logger = logging.getLogger(__name__)


class NewsVectorDB:
    """뉴스/커뮤니티 문서를 임베딩해 ChromaDB에 저장하는 벡터 저장소."""

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

    def delete_collection(self):
        self.vector_store.delete_collection()
        self.vector_store = Chroma(
            collection_name=self.collection_name,
            embedding_function=self.embedder.get_embedding_model(),
            persist_directory=self.persist_directory,
        )
