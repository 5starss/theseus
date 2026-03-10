import json
from datetime import datetime
from typing import Any, Dict, List, Tuple

from app.shared.schemas import Document as AppDocument
from collector.kis_news import fetch_kis_news_title
from collector.storage import save_snapshot


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
