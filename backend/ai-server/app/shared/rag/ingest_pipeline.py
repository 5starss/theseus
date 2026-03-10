import logging
from dataclasses import asdict, dataclass
from typing import Dict

from app.shared.rag.vector_db import NewsVectorDB
from app.news.sources import fetch_store_and_convert_news
from app.news.sources_community import fetch_store_and_convert_community

logger = logging.getLogger(__name__)


@dataclass
class IngestResult:
    ticker: str
    news_raw_path: str
    community_raw_path: str
    news_count: int
    community_count: int
    indexed_count: int

    def to_dict(self) -> Dict[str, object]:
        return asdict(self)


class RAGIngestPipeline:
    """
    순차 RAG ingest:
    1) 뉴스/커뮤니티 수집 및 스냅샷 저장
    2) Document 변환
    3) 임베딩 및 벡터 DB 저장
    """

    def run(self, ticker: str, community_limit: int = 15, reset_collection: bool = True) -> IngestResult:
        news_raw_path, news_docs = fetch_store_and_convert_news(ticker)
        community_raw_path, community_docs = fetch_store_and_convert_community(ticker=ticker, limit=community_limit)

        all_docs = news_docs + community_docs
        vdb = NewsVectorDB()
        if reset_collection:
            logger.info("기존 컬렉션 초기화 후 순차 색인 진행")
            vdb.delete_collection()
        indexed_count = vdb.add_documents(all_docs)

        return IngestResult(
            ticker=ticker,
            news_raw_path=news_raw_path,
            community_raw_path=community_raw_path,
            news_count=len(news_docs),
            community_count=len(community_docs),
            indexed_count=indexed_count,
        )

