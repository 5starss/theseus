import logging
from datetime import datetime
from typing import Any, Dict

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Query

from collector.kis_news import fetch_kis_news_title
from collector.storage import save_snapshot
from collector.toss_community import fetch_toss_community_comments

load_dotenv()
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="AI Server Infrastructure Base")


@app.get("/health")
def health_check():
    return {"status": "healthy", "message": "AI Server is running"}


@app.get("/v1/test")
def test_connection():
    return {"message": "Connection to AI Server successful"}


@app.get("/v1/collect/news")
def collect_news(ticker: str = Query(..., min_length=6, max_length=6)) -> Dict[str, Any]:
    try:
        news_list = fetch_kis_news_title(ticker)
        payload = {
            "ticker": ticker,
            "collected_at": datetime.now().isoformat(),
            "sources": {"news": news_list},
        }
        file_path = save_snapshot("raw", ticker, payload)
        return {
            "ticker": ticker,
            "source": "KIS_NEWS",
            "count": len(news_list),
            "file_path": file_path,
            "data": news_list,
        }
    except Exception as exc:
        logger.exception("Failed to collect KIS news for %s", ticker)
        raise HTTPException(status_code=500, detail=f"KIS news collection failed: {exc}") from exc


@app.get("/v1/collect/community")
def collect_community(
    ticker: str = Query(..., min_length=6, max_length=6),
    limit: int = Query(15, ge=1, le=100),
) -> Dict[str, Any]:
    try:
        comments = fetch_toss_community_comments(ticker=ticker, limit=limit)
        payload = {
            "ticker": ticker,
            "collected_at": datetime.now().isoformat(),
            "sources": {"community": comments},
        }
        file_path = save_snapshot("comm", ticker, payload)
        return {
            "ticker": ticker,
            "source": "TOSS_COMMUNITY",
            "count": len(comments),
            "file_path": file_path,
            "data": comments,
        }
    except Exception as exc:
        logger.exception("Failed to collect Toss community for %s", ticker)
        raise HTTPException(status_code=500, detail=f"Toss community collection failed: {exc}") from exc


@app.get("/v1/collect/all")
def collect_all(
    ticker: str = Query(..., min_length=6, max_length=6),
    community_limit: int = Query(15, ge=1, le=100),
) -> Dict[str, Any]:
    news_result = collect_news(ticker)
    community_result = collect_community(ticker, community_limit)
    return {
        "ticker": ticker,
        "news": news_result,
        "community": community_result,
    }


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)
