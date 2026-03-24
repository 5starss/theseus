import json
import glob
import os
from datetime import datetime
from typing import Any, Dict, List, Tuple

from app.shared.schemas import Document as AppDocument
from collector.kis_news import fetch_kis_news_title
from collector.storage import get_storage_dir, save_snapshot

from app.shared.rag.vector_db import NewsVectorDB
from app.shared.rag.reranker import SolarReranker
from app.news.sources_community import load_community_documents_from_snapshot
from typing import List, Any


def _format_publish_dt(data_dt: str, data_tm: str) -> str:
    if len(data_dt) == 8:
        formatted_date = f"{data_dt[:4]}-{data_dt[4:6]}-{data_dt[6:]}"
    else:
        formatted_date = data_dt
    return f"{formatted_date} {data_tm}".strip()


def convert_news_items_to_documents(ticker: str, news_items: List[Dict[str, Any]]) -> List[AppDocument]:
    docs: List[AppDocument] = []
    for item in news_items:
        title = item.get("hts_pbnt_titl_cntt", "")
        if not title:
            continue

        published_at = _format_publish_dt(item.get("data_dt", ""), item.get("data_tm", ""))
        unique_id = item.get("cntt_usiq_srno") or f"{ticker}_{int(datetime.now().timestamp())}"

        docs.append(
            AppDocument(
                id=f"KIS_{unique_id}",
                source="KIS_NEWS",
                published_at=published_at,
                title=title,
                body=f"[{ticker}] {title}",
                url="",
                source_rank=1.0,
            )
        )
    return docs


def fetch_store_and_convert_news(ticker: str) -> Tuple[str, List[AppDocument]]:
    news_items = fetch_kis_news_title(ticker)
    payload = {
        "ticker": ticker,
        "collected_at": datetime.now().isoformat(),
        "sources": {"news": news_items},
    }
    file_path = save_snapshot("raw", ticker, payload)
    docs = convert_news_items_to_documents(ticker=ticker, news_items=news_items)
    return file_path, docs


def load_news_documents_from_snapshot(path: str) -> List[AppDocument]:
    with open(path, "r", encoding="utf-8") as f:
        payload = json.load(f)

    ticker = payload.get("ticker", "UNKNOWN")
    news_items = payload.get("sources", {}).get("news", [])
    return convert_news_items_to_documents(ticker=ticker, news_items=news_items)


def _latest_snapshot_path(prefix: str, ticker: str) -> str | None:
    storage_dir = get_storage_dir("news")
    pattern = os.path.join(storage_dir, f"{prefix}_{ticker}_*.json")
    files = sorted(glob.glob(pattern))
    if not files:
        return None
    return files[-1]


def retrieve_news(
    ticker: str,
    query: str = "이 종목의 향후 단기 주가 방향은 어떨까?",
    top_k: int = 5,
    collection_name: str | None = None,
) -> List[Any]:
    """
    ChromaDB에서 뉴스 데이터를 검색하고 Rerank하여 반환합니다.
    """
    vdb = NewsVectorDB(collection_name=collection_name or "kis_news_titles")
    # KIS_NEWS 소스 필터 적용
    search_results = vdb.hybrid_query(query_text=query, k=top_k * 2, source_filter="KIS_NEWS")
    
    if not search_results:
        snapshot_path = _latest_snapshot_path("raw", ticker)
        if not snapshot_path:
            return []
        return load_news_documents_from_snapshot(snapshot_path)[:top_k]
        
    reranker = SolarReranker()
    reranked_docs = reranker.rerank(query=query, documents=search_results, top_n=top_k)
    return reranked_docs


def retrieve_community_posts(
    ticker: str,
    query: str = "이 종목의 향후 단기 주가 방향은 어떨까?",
    top_k: int = 3,
    collection_name: str | None = None,
) -> List[Any]:
    """
    ChromaDB에서 커뮤니티 데이터를 검색하고 Rerank하여 반환합니다.
    """
    vdb = NewsVectorDB(collection_name=collection_name or "kis_news_titles")
    # TOSS_COMMUNITY 소스 필터 적용
    search_results = vdb.hybrid_query(query_text=query, k=top_k * 2, source_filter="TOSS_COMMUNITY")
    
    if not search_results:
        snapshot_path = _latest_snapshot_path("comm", ticker)
        if not snapshot_path:
            return []
        return load_community_documents_from_snapshot(snapshot_path)[:top_k]
        
    reranker = SolarReranker()
    reranked_docs = reranker.rerank(query=query, documents=search_results, top_n=top_k)
    return reranked_docs
