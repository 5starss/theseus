import json
import logging
import os
import uuid
from datetime import datetime
from decimal import Decimal
from typing import Any, Dict, List, Optional

from collector.storage import get_storage_dir
from app.trading.constants import KST


DECISION_REVIEW_SCHEMA = "agent_decision_review_v1"
logger = logging.getLogger(__name__)


def _ensure_table() -> None:
    query = """
        CREATE TABLE IF NOT EXISTS agent_decision_reviews (
            id BIGINT PRIMARY KEY AUTO_INCREMENT,
            review_id VARCHAR(128) NOT NULL,
            decision_trace_id VARCHAR(128) NOT NULL,
            reviewed_at DATETIME NOT NULL,
            ticker VARCHAR(16) NOT NULL,
            user_id BIGINT NULL,
            strategy_slot VARCHAR(32) NULL,
            outcome VARCHAR(32) NOT NULL,
            pnl_pct DOUBLE NULL,
            max_drawdown_pct DOUBLE NULL,
            holding_minutes INT NULL,
            execution_status VARCHAR(32) NULL,
            mistake_tags_json TEXT NULL,
            evaluator VARCHAR(128) NULL,
            s3_key VARCHAR(512) NULL,
            local_path VARCHAR(1024) NULL,
            jsonl_path VARCHAR(1024) NULL,
            s3_uploaded TINYINT(1) NOT NULL DEFAULT 0,
            created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
            updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
            UNIQUE KEY uq_agent_decision_review_id (review_id),
            KEY idx_agent_decision_review_trace (decision_trace_id, reviewed_at),
            KEY idx_agent_decision_review_ticker_time (ticker, reviewed_at),
            KEY idx_agent_decision_review_user_time (user_id, reviewed_at),
            KEY idx_agent_decision_review_outcome (outcome, reviewed_at)
        )
    """
    with _open_db_conn() as conn:
        with conn.cursor() as cursor:
            cursor.execute(query)


def _json_default(value: Any) -> Any:
    if isinstance(value, Decimal):
        return float(value)
    if isinstance(value, datetime):
        return value.isoformat()
    return str(value)


def _open_db_conn():
    try:
        from app.trading.core_api_client import _get_db_conn
    except Exception as exc:
        raise RuntimeError(f"DB client unavailable: {exc}") from exc
    return _get_db_conn()


def _upload_s3(local_path: str, s3_key: str) -> bool:
    try:
        from app.shared.infra.s3_client import s3_client
    except Exception as exc:
        logger.warning("S3 client unavailable; skipping decision review upload - error=%s", exc)
        return False
    return bool(s3_client.upload_file(local_path, s3_key))


def _download_s3(s3_key: str, local_path: str) -> bool:
    try:
        from app.shared.infra.s3_client import s3_client
    except Exception as exc:
        logger.warning("S3 client unavailable; skipping decision review download - error=%s", exc)
        return False
    return bool(s3_client.download_file(s3_key, local_path))


def _safe_float(value: Any) -> Optional[float]:
    try:
        if value is None:
            return None
        return float(value)
    except Exception:
        return None


def _safe_int(value: Any) -> Optional[int]:
    try:
        if value is None:
            return None
        if isinstance(value, str) and not value.strip():
            return None
        return int(value)
    except Exception:
        return None


def _parse_datetime(value: Any) -> datetime:
    return datetime.fromisoformat(str(value))


def _db_datetime(value: Any) -> datetime:
    parsed = _parse_datetime(value)
    if parsed.tzinfo is not None:
        parsed = parsed.astimezone(KST).replace(tzinfo=None)
    return parsed


def _normalize_tags(tags: Optional[List[str]]) -> List[str]:
    normalized: List[str] = []
    for item in tags or []:
        tag = str(item or "").strip().lower().replace(" ", "_").replace("-", "_")
        tag = "".join(ch for ch in tag if ch.isalnum() or ch == "_")
        if tag and tag not in normalized:
            normalized.append(tag[:64])
    return normalized[:10]


def build_decision_review_s3_key(review: Dict[str, Any]) -> str:
    reviewed_at = _parse_datetime(review["reviewed_at"])
    day_path = reviewed_at.strftime("%Y/%m/%d")
    ticker = str(review.get("ticker") or "unknown")
    review_id = str(review.get("review_id") or uuid.uuid4().hex)
    return f"decision-reviews/{day_path}/{ticker}/{review_id}.json"


def _build_object_local_path(s3_key: str) -> str:
    storage_dir = get_storage_dir("decision_review_objects")
    return os.path.join(storage_dir, *s3_key.split("/"))


def _append_jsonl(review: Dict[str, Any]) -> str:
    storage_dir = get_storage_dir("decision_reviews")
    reviewed_at = _parse_datetime(review["reviewed_at"])
    day_token = reviewed_at.strftime("%Y%m%d")
    file_path = os.path.join(storage_dir, f"{day_token}_reviews.jsonl")

    with open(file_path, "a", encoding="utf-8") as fp:
        fp.write(json.dumps(review, ensure_ascii=False, default=_json_default))
        fp.write("\n")
    return file_path


def _save_object(review: Dict[str, Any], s3_key: str) -> Dict[str, Any]:
    local_path = _build_object_local_path(s3_key)
    os.makedirs(os.path.dirname(local_path), exist_ok=True)
    with open(local_path, "w", encoding="utf-8") as fp:
        json.dump(review, fp, ensure_ascii=False, default=_json_default)
    try:
        uploaded = _upload_s3(local_path, s3_key)
    except Exception as exc:
        logger.warning(
            "decision review S3 upload failed - review_id=%s s3_key=%s error=%s",
            review.get("review_id"),
            s3_key,
            exc,
        )
        uploaded = False
    return {"local_path": local_path, "s3_key": s3_key, "s3_uploaded": bool(uploaded)}


def _upsert_review_row(
    review: Dict[str, Any],
    *,
    local_path: str,
    jsonl_path: str,
    s3_key: str,
    s3_uploaded: bool,
) -> None:
    _ensure_table()
    reviewed_at = _db_datetime(review["reviewed_at"])
    query = """
        INSERT INTO agent_decision_reviews (
            review_id, decision_trace_id, reviewed_at, ticker, user_id,
            strategy_slot, outcome, pnl_pct, max_drawdown_pct, holding_minutes,
            execution_status, mistake_tags_json, evaluator, s3_key, local_path,
            jsonl_path, s3_uploaded
        ) VALUES (
            %s, %s, %s, %s, %s,
            %s, %s, %s, %s, %s,
            %s, %s, %s, %s, %s,
            %s, %s
        )
        ON DUPLICATE KEY UPDATE
            decision_trace_id = VALUES(decision_trace_id),
            reviewed_at = VALUES(reviewed_at),
            ticker = VALUES(ticker),
            user_id = VALUES(user_id),
            strategy_slot = VALUES(strategy_slot),
            outcome = VALUES(outcome),
            pnl_pct = VALUES(pnl_pct),
            max_drawdown_pct = VALUES(max_drawdown_pct),
            holding_minutes = VALUES(holding_minutes),
            execution_status = VALUES(execution_status),
            mistake_tags_json = VALUES(mistake_tags_json),
            evaluator = VALUES(evaluator),
            s3_key = VALUES(s3_key),
            local_path = VALUES(local_path),
            jsonl_path = VALUES(jsonl_path),
            s3_uploaded = VALUES(s3_uploaded)
    """
    with _open_db_conn() as conn:
        with conn.cursor() as cursor:
            cursor.execute(
                query,
                (
                    review.get("review_id"),
                    review.get("decision_trace_id"),
                    reviewed_at,
                    str(review.get("ticker") or ""),
                    _safe_int(review.get("user_id")),
                    review.get("strategy_slot"),
                    review.get("outcome"),
                    _safe_float(review.get("pnl_pct")),
                    _safe_float(review.get("max_drawdown_pct")),
                    _safe_int(review.get("holding_minutes")),
                    review.get("execution_status"),
                    json.dumps(review.get("mistake_tags") or [], ensure_ascii=False),
                    review.get("evaluator"),
                    s3_key,
                    local_path,
                    jsonl_path,
                    1 if s3_uploaded else 0,
                ),
            )


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
    jsonl_path = _append_jsonl(review)
    s3_key = build_decision_review_s3_key(review)
    object_meta = _save_object(review, s3_key)
    db_saved = False
    try:
        _upsert_review_row(
            review,
            local_path=object_meta["local_path"],
            jsonl_path=jsonl_path,
            s3_key=object_meta["s3_key"],
            s3_uploaded=bool(object_meta["s3_uploaded"]),
        )
        db_saved = True
    except Exception as exc:
        logger.warning(
            "decision review DB indexing failed - review_id=%s decision_trace_id=%s error=%s",
            review.get("review_id"),
            review.get("decision_trace_id"),
            exc,
        )

    return {
        "review_id": review["review_id"],
        "decision_trace_id": review["decision_trace_id"],
        "schema": review["schema"],
        "path": jsonl_path,
        "jsonl_path": jsonl_path,
        "local_path": object_meta["local_path"],
        "s3_key": object_meta["s3_key"],
        "s3_uploaded": object_meta["s3_uploaded"],
        "db_saved": db_saved,
    }


def _iter_local_decision_reviews() -> List[Dict[str, Any]]:
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


def iter_decision_review_records() -> List[Dict[str, Any]]:
    _ensure_table()
    query = """
        SELECT *
        FROM agent_decision_reviews
        ORDER BY reviewed_at ASC
    """
    with _open_db_conn() as conn:
        with conn.cursor() as cursor:
            return list(cursor.fetchall() or [])


def load_decision_review_payload(row: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    local_path = str(row.get("local_path") or "")
    s3_key = str(row.get("s3_key") or "")

    if local_path and os.path.exists(local_path):
        with open(local_path, "r", encoding="utf-8") as fp:
            review = json.load(fp)
            review["_source_path"] = local_path
            review["_source_type"] = "db_local_object"
            return review

    if s3_key:
        local_path = _build_object_local_path(s3_key)
        os.makedirs(os.path.dirname(local_path), exist_ok=True)
        if _download_s3(s3_key, local_path):
            with open(local_path, "r", encoding="utf-8") as fp:
                review = json.load(fp)
                review["_source_path"] = local_path
                review["_source_type"] = "s3_object"
                return review

    jsonl_path = str(row.get("jsonl_path") or "")
    target = str(row.get("review_id") or "")
    if not jsonl_path or not target or not os.path.exists(jsonl_path):
        return None

    with open(jsonl_path, "r", encoding="utf-8") as fp:
        for line in fp:
            line = line.strip()
            if not line:
                continue
            try:
                review = json.loads(line)
            except json.JSONDecodeError:
                continue
            if str(review.get("review_id") or "") == target:
                review["_source_path"] = jsonl_path
                review["_source_type"] = "jsonl_fallback"
                return review
    return None


def iter_decision_reviews() -> List[Dict[str, Any]]:
    try:
        reviews = [
            review
            for row in iter_decision_review_records()
            for review in [load_decision_review_payload(row)]
            if review is not None
        ]
        if reviews:
            return reviews
    except Exception as exc:
        logger.warning("decision review DB/S3 load failed; falling back to local JSONL - error=%s", exc)
    return _iter_local_decision_reviews()


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
