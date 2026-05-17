import json
import os
import uuid
from datetime import datetime
from decimal import Decimal
from typing import Any, Dict, List, Optional

from collector.storage import get_storage_dir
from app.trading.constants import KST


DECISION_REVIEW_SCHEMA = "agent_decision_review_v1"


def _json_default(value: Any) -> Any:
    if isinstance(value, Decimal):
        return float(value)
    if isinstance(value, datetime):
        return value.isoformat()
    return str(value)


def _safe_float(value: Any) -> Optional[float]:
    try:
        if value is None:
            return None
        return float(value)
    except Exception:
        return None


def _normalize_tags(tags: Optional[List[str]]) -> List[str]:
    normalized: List[str] = []
    for item in tags or []:
        tag = str(item or "").strip().lower().replace(" ", "_").replace("-", "_")
        tag = "".join(ch for ch in tag if ch.isalnum() or ch == "_")
        if tag and tag not in normalized:
            normalized.append(tag[:64])
    return normalized[:10]


def build_decision_review(
    *,
    decision_trace_id: str,
    ticker: str,
    user_id: Optional[int] = None,
    strategy_slot: Optional[str] = None,
    outcome: str,
    pnl_pct: Optional[float] = None,
    max_drawdown_pct: Optional[float] = None,
    holding_minutes: Optional[int] = None,
    execution_status: Optional[str] = None,
    mistake_tags: Optional[List[str]] = None,
    lesson: str = "",
    evaluator: str = "system",
    extra: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    reviewed_at = datetime.now(KST)
    normalized_outcome = str(outcome or "UNKNOWN").upper()
    if normalized_outcome not in {"WIN", "LOSS", "FLAT", "NOT_EXECUTED", "UNKNOWN"}:
        normalized_outcome = "UNKNOWN"

    return {
        "schema": DECISION_REVIEW_SCHEMA,
        "review_id": f"{reviewed_at.strftime('%Y%m%dT%H%M%S%f')}-{uuid.uuid4().hex[:10]}",
        "decision_trace_id": decision_trace_id,
        "reviewed_at": reviewed_at.isoformat(),
        "ticker": ticker,
        "user_id": user_id,
        "strategy_slot": strategy_slot,
        "outcome": normalized_outcome,
        "pnl_pct": _safe_float(pnl_pct),
        "max_drawdown_pct": _safe_float(max_drawdown_pct),
        "holding_minutes": holding_minutes,
        "execution_status": execution_status,
        "mistake_tags": _normalize_tags(mistake_tags),
        "lesson": str(lesson or "").strip(),
        "evaluator": evaluator,
        "extra": extra or {},
    }


def save_decision_review(review: Dict[str, Any]) -> Dict[str, Any]:
    storage_dir = get_storage_dir("decision_reviews")
    reviewed_at = datetime.fromisoformat(str(review["reviewed_at"]))
    day_token = reviewed_at.strftime("%Y%m%d")
    file_path = os.path.join(storage_dir, f"{day_token}_reviews.jsonl")

    with open(file_path, "a", encoding="utf-8") as fp:
        fp.write(json.dumps(review, ensure_ascii=False, default=_json_default))
        fp.write("\n")

    return {
        "review_id": review["review_id"],
        "decision_trace_id": review["decision_trace_id"],
        "schema": review["schema"],
        "path": file_path,
    }


def iter_decision_reviews() -> List[Dict[str, Any]]:
    storage_dir = get_storage_dir("decision_reviews")
    reviews: List[Dict[str, Any]] = []
    if not os.path.isdir(storage_dir):
        return reviews

    for name in sorted(os.listdir(storage_dir)):
        if not name.endswith("_reviews.jsonl"):
            continue
        path = os.path.join(storage_dir, name)
        with open(path, "r", encoding="utf-8") as fp:
            for line in fp:
                line = line.strip()
                if not line:
                    continue
                try:
                    review = json.loads(line)
                except json.JSONDecodeError:
                    continue
                review["_source_path"] = path
                reviews.append(review)
    return reviews


def load_latest_reviews_by_decision_id() -> Dict[str, Dict[str, Any]]:
    latest: Dict[str, Dict[str, Any]] = {}
    for review in iter_decision_reviews():
        decision_trace_id = str(review.get("decision_trace_id") or "")
        if not decision_trace_id:
            continue
        previous = latest.get(decision_trace_id)
        if previous is None or str(review.get("reviewed_at") or "") > str(previous.get("reviewed_at") or ""):
            latest[decision_trace_id] = review
    return latest
