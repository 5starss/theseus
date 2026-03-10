import logging
from datetime import datetime
from typing import Any, Dict, List, Optional

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Query

from app.news.agent import NewsReporterAgent
from app.news.eval import RAGEvaluator
from app.shared.rag.ingest_pipeline import RAGIngestPipeline
from app.shared.rag.reranker import SolarReranker
from app.shared.rag.vector_db import NewsVectorDB
from collector.kis_news import fetch_kis_news_title
from collector.storage import list_storage_files, save_snapshot
from collector.toss_community import fetch_toss_community_comments

load_dotenv()
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="AI Server Infrastructure Base")
TICKER_PATTERN = r"^\d{6}$"
SOURCE_NEWS = "KIS_NEWS"
SOURCE_COMMUNITY = "TOSS_COMMUNITY"


@app.get("/health")
def health_check():
    return {"status": "healthy", "message": "AI Server is running"}


@app.get("/v1/test")
def test_connection():
    return {"message": "Connection to AI Server successful"}


@app.get("/v1/collect/news")
def collect_news(ticker: str = Query(..., pattern=TICKER_PATTERN)) -> Dict[str, Any]:
    return _collect_news_result(ticker)


@app.get("/v1/collect/community")
def collect_community(
    ticker: str = Query(..., pattern=TICKER_PATTERN),
    limit: int = Query(15, ge=1, le=100),
    community_limit: Optional[int] = Query(None, ge=1, le=100),
) -> Dict[str, Any]:
    resolved_limit = community_limit if community_limit is not None else limit
    return _collect_community_result(ticker=ticker, limit=resolved_limit)


@app.get("/v1/collect/all")
def collect_all(
    ticker: str = Query(..., pattern=TICKER_PATTERN),
    community_limit: int = Query(15, ge=1, le=100),
) -> Dict[str, Any]:
    news_result = _collect_news_result(ticker)
    community_result = _collect_community_result(ticker=ticker, limit=community_limit)
    return {
        "ticker": ticker,
        "news": news_result,
        "community": community_result,
    }


@app.get("/v1/storage/status")
def storage_status(
    category: str = Query("news", pattern=r"^(news|quant)$"),
    limit: int = Query(20, ge=1, le=200),
) -> Dict[str, Any]:
    try:
        return list_storage_files(category=category, limit=limit)
    except Exception as exc:
        logger.exception("Failed to read storage status")
        raise HTTPException(status_code=500, detail=f"Storage status failed: {exc}") from exc


@app.post("/v1/rag/ingest")
def rag_ingest(
    ticker: str = Query(..., pattern=TICKER_PATTERN),
    community_limit: int = Query(15, ge=1, le=100),
    reset_collection: bool = Query(True),
) -> Dict[str, Any]:
    try:
        pipeline = RAGIngestPipeline()
        result = pipeline.run(
            ticker=ticker,
            community_limit=community_limit,
            reset_collection=reset_collection,
        )
        return {"status": "ok", "result": result.to_dict()}
    except Exception as exc:
        logger.exception("Failed to run sequential RAG ingest for %s", ticker)
        raise HTTPException(status_code=500, detail=f"RAG ingest failed: {exc}") from exc


@app.post("/v1/rag/chat")
def rag_chat(
    query: str = Query(..., min_length=1),
    news_k: int = Query(15, ge=1, le=50),
    community_k: int = Query(2, ge=0, le=20),
    rerank_top_n: int = Query(5, ge=1, le=20),
    with_eval: bool = Query(False),
) -> Dict[str, Any]:
    try:
        return _run_rag_chat_pipeline(
            query=query,
            news_k=news_k,
            community_k=community_k,
            rerank_top_n=rerank_top_n,
            with_eval=with_eval,
        )
    except Exception as exc:
        logger.exception("Failed to run RAG chat")
        raise HTTPException(status_code=500, detail=f"RAG chat failed: {exc}") from exc


def _run_rag_chat_pipeline(
    query: str,
    news_k: int,
    community_k: int,
    rerank_top_n: int,
    with_eval: bool,
) -> Dict[str, Any]:
    vdb = NewsVectorDB()

    news_candidates = vdb.hybrid_query(query_text=query, k=news_k, source_filter=SOURCE_NEWS)
    news_docs = _rerank_news_candidates(query=query, candidates=news_candidates, top_n=rerank_top_n)

    community_docs: List[Any] = []
    if community_k > 0:
        community_docs = vdb.hybrid_query(query_text=query, k=community_k, source_filter=SOURCE_COMMUNITY)

    agent = NewsReporterAgent()
    answer = agent.generate_response(question=query, news_docs=news_docs, community_docs=community_docs)

    eval_result = None
    if with_eval and (news_docs or community_docs):
        evaluator = RAGEvaluator()
        eval_result = evaluator.run_full_eval(
            question=query,
            response=answer,
            retrieved_docs=(news_docs + community_docs),
        )

    result = {
        "status": "ok",
        "query": query,
        "retrieved": {
            "news_candidates": len(news_candidates),
            "news_used": len(news_docs),
            "community_used": len(community_docs),
        },
        "answer": answer,
    }
    if eval_result is not None:
        result["eval"] = eval_result
    return result


def _rerank_news_candidates(query: str, candidates: List[Any], top_n: int) -> List[Any]:
    if not candidates:
        return []
    reranker = SolarReranker()
    return reranker.rerank(query=query, documents=candidates, top_n=top_n)


def _build_collect_payload(ticker: str, source_key: str, items: List[Dict[str, Any]]) -> Dict[str, Any]:
    return {
        "ticker": ticker,
        "collected_at": datetime.now().isoformat(),
        "sources": {source_key: items},
    }


def _build_collect_response(
    ticker: str,
    source: str,
    file_path: str,
    items: List[Dict[str, Any]],
) -> Dict[str, Any]:
    return {
        "ticker": ticker,
        "source": source,
        "count": len(items),
        "file_path": file_path,
        "data": items,
    }


def _collect_news_result(ticker: str) -> Dict[str, Any]:
    try:
        news_list = fetch_kis_news_title(ticker)
        payload = _build_collect_payload(ticker=ticker, source_key="news", items=news_list)
        file_path = save_snapshot("raw", ticker, payload)
        logger.info("Saved KIS news snapshot: ticker=%s count=%s path=%s", ticker, len(news_list), file_path)
        return _build_collect_response(
            ticker=ticker,
            source=SOURCE_NEWS,
            file_path=file_path,
            items=news_list,
        )
    except Exception as exc:
        logger.exception("Failed to collect KIS news for %s", ticker)
        raise HTTPException(status_code=500, detail=f"KIS news collection failed: {exc}") from exc


def _collect_community_result(ticker: str, limit: int) -> Dict[str, Any]:
    try:
        comments = fetch_toss_community_comments(ticker=ticker, limit=limit)
        payload = _build_collect_payload(ticker=ticker, source_key="community", items=comments)
        file_path = save_snapshot("comm", ticker, payload)
        logger.info(
            "Saved Toss community snapshot: ticker=%s count=%s limit=%s path=%s",
            ticker,
            len(comments),
            limit,
            file_path,
        )
        return _build_collect_response(
            ticker=ticker,
            source=SOURCE_COMMUNITY,
            file_path=file_path,
            items=comments,
        )
    except Exception as exc:
        logger.exception("Failed to collect Toss community for %s", ticker)
        raise HTTPException(status_code=500, detail=f"Toss community collection failed: {exc}") from exc


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)
