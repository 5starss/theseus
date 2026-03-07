import logging
import os
from dataclasses import dataclass
from typing import Dict, List, Optional

from app.rag.vector_db import NewsVectorDB
from app.schemas import Document as AppDocument
from app.sources import convert_to_documents, fetch_and_store_news
from app.sources_community import convert_community_to_documents, fetch_and_store_community

logger = logging.getLogger(__name__)


@dataclass
class IngestResult:
    ticker: str
    news_raw_path: str
    community_raw_path: Optional[str]
    indexed_count: int
    news_count: int
    community_count: int


class RAGIngestPipeline:
    """
    RAG 파이프라인의 수집/임베딩/저장 단계만 순차 실행합니다.
    - 뉴스/커뮤니티 수집
    - Document 변환
    - 벡터 DB 임베딩 및 저장
    """

    def __init__(self, reset_collection: bool = True):
        self.reset_collection = reset_collection

    def _load_documents(self, news_raw_path: str, community_raw_path: Optional[str]) -> Dict[str, List[AppDocument]]:
        news_docs = convert_to_documents(news_raw_path)
        community_docs: List[AppDocument] = []

        if community_raw_path and os.path.exists(community_raw_path):
            community_docs = convert_community_to_documents(community_raw_path)

        return {"news": news_docs, "community": community_docs}

    def run(self, ticker: str) -> IngestResult:
        logger.info(f"[{ticker}] 순차 수집 시작 (뉴스/커뮤니티)")
        news_raw_path = fetch_and_store_news(ticker)
        community_raw_path = fetch_and_store_community(ticker)

        docs_by_source = self._load_documents(news_raw_path, community_raw_path)
        all_docs = docs_by_source["news"] + docs_by_source["community"]

        if not all_docs:
            logger.warning("색인할 문서가 없어 임베딩/저장 단계를 건너뜁니다.")
            return IngestResult(
                ticker=ticker,
                news_raw_path=news_raw_path,
                community_raw_path=community_raw_path,
                indexed_count=0,
                news_count=0,
                community_count=0,
            )

        vdb = NewsVectorDB()
        if self.reset_collection:
            logger.info("기존 컬렉션 초기화 후 색인합니다.")
            vdb.delete_collection()

        logger.info(f"총 {len(all_docs)}건 임베딩 및 벡터 저장 시작")
        vdb.add_documents(all_docs)

        return IngestResult(
            ticker=ticker,
            news_raw_path=news_raw_path,
            community_raw_path=community_raw_path,
            indexed_count=len(all_docs),
            news_count=len(docs_by_source["news"]),
            community_count=len(docs_by_source["community"]),
        )

