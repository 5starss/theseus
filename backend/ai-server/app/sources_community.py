import json
from datetime import datetime
from typing import Any, Dict, List, Tuple

from app.schemas import Document as AppDocument
from collector.storage import save_snapshot
from collector.toss_community import fetch_toss_community_comments


def convert_community_items_to_documents(ticker: str, items: List[Dict[str, Any]]) -> List[AppDocument]:
    docs: List[AppDocument] = []
    published_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    for idx, item in enumerate(items):
        nickname = item.get("nickname", "익명")
        body = (item.get("body") or "").strip()
        if not body:
            continue

        docs.append(
            AppDocument(
                id=f"COMM_{ticker}_{int(datetime.now().timestamp())}_{idx}",
                source="TOSS_COMMUNITY",
                published_at=published_at,
                title=f"[{ticker}] 커뮤니티 여론 ({nickname})",
                body=body,
                url=f"https://www.tossinvest.com/stocks/A{ticker}/community",
                source_rank=0.2,
            )
        )
    return docs


def fetch_store_and_convert_community(ticker: str, limit: int = 15) -> Tuple[str, List[AppDocument]]:
    items = fetch_toss_community_comments(ticker=ticker, limit=limit)
    payload = {
        "ticker": ticker,
        "collected_at": datetime.now().isoformat(),
        "sources": {"community": items},
    }
    file_path = save_snapshot("comm", ticker, payload)
    docs = convert_community_items_to_documents(ticker=ticker, items=items)
    return file_path, docs


def load_community_documents_from_snapshot(path: str) -> List[AppDocument]:
    with open(path, "r", encoding="utf-8") as f:
        payload = json.load(f)

    ticker = payload.get("ticker", "UNKNOWN")
    items = payload.get("sources", {}).get("community", [])
    return convert_community_items_to_documents(ticker=ticker, items=items)
