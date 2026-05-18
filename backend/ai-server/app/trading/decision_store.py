import json
import logging
import os
import uuid
from datetime import date, datetime
from decimal import Decimal
from typing import Any, Dict, List, Optional

from collector.storage import get_storage_dir
from app.trading.constants import KST


DECISION_TRACE_SCHEMA = "agent_decision_trace_v1"
logger = logging.getLogger(__name__)


def _ensure_table() -> None:
    query = """
        CREATE TABLE IF NOT EXISTS agent_decision_traces (
            id BIGINT PRIMARY KEY AUTO_INCREMENT,
            decision_trace_id VARCHAR(128) NOT NULL,
            trade_date DATE NOT NULL,
            ticker VARCHAR(16) NOT NULL,
            user_id BIGINT NULL,
            strategy_slot VARCHAR(32) NULL,
            action VARCHAR(16) NULL,
            order_type VARCHAR(16) NULL,
            risk_decision VARCHAR(32) NULL,
            risk_blocked TINYINT(1) NOT NULL DEFAULT 0,
            execution_status VARCHAR(32) NULL,
            system_error TINYINT(1) NOT NULL DEFAULT 0,
            analysis_cache_status VARCHAR(32) NULL,
            market_regime VARCHAR(64) NULL,
            entry_risk VARCHAR(32) NULL,
            signal_confidence VARCHAR(32) NULL,
            historical_recommendation VARCHAR(64) NULL,
            s3_key VARCHAR(512) NULL,
            local_path VARCHAR(1024) NULL,
            jsonl_path VARCHAR(1024) NULL,
            s3_uploaded TINYINT(1) NOT NULL DEFAULT 0,
            created_at DATETIME NOT NULL,
            updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
            UNIQUE KEY uq_agent_decision_trace_id (decision_trace_id),
            KEY idx_agent_decision_trace_ticker_date (ticker, trade_date),
            KEY idx_agent_decision_trace_user_date (user_id, trade_date),
            KEY idx_agent_decision_trace_strategy (strategy_slot, trade_date),
            KEY idx_agent_decision_trace_action (action, trade_date)
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
        logger.warning("S3 client unavailable; skipping decision trace upload - error=%s", exc)
        return False
    return bool(s3_client.upload_file(local_path, s3_key))


def _download_s3(s3_key: str, local_path: str) -> bool:
    try:
        from app.shared.infra.s3_client import s3_client
    except Exception as exc:
        logger.warning("S3 client unavailable; skipping decision trace download - error=%s", exc)
        return False
    return bool(s3_client.download_file(s3_key, local_path))


def _safe_get(mapping: Dict[str, Any], key: str, default: Any = None) -> Any:
    value = mapping.get(key) if isinstance(mapping, dict) else default
    return default if value is None else value


def _safe_float(value: Any) -> Optional[float]:
    try:
        if value is None:
            return None
        if isinstance(value, str) and not value.strip():
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
    parsed = datetime.fromisoformat(str(value))
    return parsed


def _parse_date(value: Any, fallback: date) -> date:
    if not value:
        return fallback
    return datetime.fromisoformat(str(value)).date()


def _db_datetime(value: Any) -> datetime:
    parsed = _parse_datetime(value)
    if parsed.tzinfo is not None:
        parsed = parsed.astimezone(KST).replace(tzinfo=None)
    return parsed


def _nested(mapping: Dict[str, Any], *keys: str) -> Any:
    current: Any = mapping
    for key in keys:
        if not isinstance(current, dict):
            return None
        current = current.get(key)
    return current


def _position_ratio(order_card: Dict[str, Any]) -> Optional[float]:
    account_snapshot = order_card.get("account_snapshot") if isinstance(order_card.get("account_snapshot"), dict) else {}
    holding = account_snapshot.get("holding") if isinstance(account_snapshot.get("holding"), dict) else {}
    cash = _safe_float(account_snapshot.get("available_cash")) or 0.0
    quantity = _safe_float(holding.get("quantity")) or 0.0
    average_price = _safe_float(holding.get("average_price")) or 0.0
    position_value = quantity * average_price
    denominator = cash + position_value
    if denominator <= 0:
        return None
    return round(position_value / denominator, 4)


def build_memory_features(*, state: Dict[str, Any], order_card: Dict[str, Any]) -> Dict[str, Any]:
    quant_state = state.get("quant_state") if isinstance(state.get("quant_state"), dict) else {}
    market_state = quant_state.get("market_state") if isinstance(quant_state.get("market_state"), dict) else {}
    multi_timeframe = (
        quant_state.get("multi_timeframe") if isinstance(quant_state.get("multi_timeframe"), dict) else {}
    )
    symbol_profile = quant_state.get("symbol_profile") if isinstance(quant_state.get("symbol_profile"), dict) else {}
    risk_context = quant_state.get("risk_context") if isinstance(quant_state.get("risk_context"), dict) else {}
    order = order_card.get("order") if isinstance(order_card.get("order"), dict) else {}
    risk_review = order_card.get("risk_review") if isinstance(order_card.get("risk_review"), dict) else {}
    historical_comparison = (
        state.get("historical_comparison") if isinstance(state.get("historical_comparison"), dict) else {}
    )

    return {
        "ticker": str(_safe_get(state, "ticker", order_card.get("ticker") or "")),
        "strategy_slot": str(_safe_get(state, "resolved_slot", state.get("strategy_slot") or "daily")),
        "invest_style": state.get("invest_style"),
        "user_investment_style": state.get("user_investment_style"),
        "news_stance": _safe_get(state.get("news_card", {}), "stance"),
        "news_score": _safe_float(_safe_get(state.get("news_card", {}), "score")),
        "quant_stance": _safe_get(state.get("quant_card", {}), "stance"),
        "quant_score": _safe_float(_safe_get(state.get("quant_card", {}), "score")),
        "final_stance": order_card.get("final_stance"),
        "final_score": _safe_float(order_card.get("final_score")),
        "signal_confidence": state.get("signal_confidence") or risk_context.get("signal_confidence"),
        "action": str(_safe_get(order, "action", "hold")).lower(),
        "order_type": str(_safe_get(order, "order_type", "")).lower(),
        "risk_decision": str(_safe_get(risk_review, "decision", "")).upper(),
        "risk_score": _safe_float(risk_review.get("risk_score")),
        "risk_blocked": bool(risk_review.get("blocked")) if isinstance(risk_review, dict) else False,
        "historical_recommendation": historical_comparison.get("recommendation"),
        "historical_multiplier": _safe_float(historical_comparison.get("position_size_multiplier")),
        "market_regime": market_state.get("intraday_trend") or market_state.get("trend"),
        "price_vs_vwap": market_state.get("price_vs_vwap"),
        "intraday_position": market_state.get("intraday_position"),
        "volatility_state": market_state.get("volatility_state"),
        "volume_state": market_state.get("volume_state"),
        "overheat_state": market_state.get("overheat_state"),
        "mtf_alignment": _safe_float(multi_timeframe.get("alignment_score")),
        "mtf_direction": multi_timeframe.get("dominant_direction") or multi_timeframe.get("direction"),
        "volatility_character": symbol_profile.get("volatility_character"),
        "mean_reversion_tendency": symbol_profile.get("mean_reversion_tendency"),
        "entry_risk": risk_context.get("entry_risk"),
        "reward_risk_quality": risk_context.get("reward_risk_quality"),
        "current_position_ratio": _position_ratio(order_card),
    }


def _build_decision_trace_id(
    *,
    ticker: str,
    user_id: Optional[int],
    strategy_slot: str,
    created_at: datetime,
) -> str:
    user_token = "anon" if user_id is None else f"user{user_id}"
    random_token = uuid.uuid4().hex[:10]
    timestamp = created_at.strftime("%Y%m%dT%H%M%S%f")
    return f"{timestamp}-{ticker}-{user_token}-{strategy_slot}-{random_token}"


def build_decision_trace_s3_key(trace: Dict[str, Any]) -> str:
    created_at = _parse_datetime(trace["created_at"])
    day_path = created_at.strftime("%Y/%m/%d")
    ticker = str(_safe_get(trace.get("query_index", {}), "ticker", "unknown"))
    trace_id = str(trace.get("decision_trace_id") or uuid.uuid4().hex)
    return f"decision-traces/{day_path}/{ticker}/{trace_id}.json"


def _build_object_local_path(s3_key: str) -> str:
    storage_dir = get_storage_dir("decision_trace_objects")
    return os.path.join(storage_dir, *s3_key.split("/"))


def _append_jsonl(trace: Dict[str, Any]) -> str:
    storage_dir = get_storage_dir("decisions")
    created_at = _parse_datetime(trace["created_at"])
    day_token = created_at.strftime("%Y%m%d")
    file_path = os.path.join(storage_dir, f"{day_token}_decisions.jsonl")

    with open(file_path, "a", encoding="utf-8") as fp:
        fp.write(json.dumps(trace, ensure_ascii=False, default=_json_default))
        fp.write("\n")
    return file_path


def _save_object(trace: Dict[str, Any], s3_key: str) -> Dict[str, Any]:
    local_path = _build_object_local_path(s3_key)
    os.makedirs(os.path.dirname(local_path), exist_ok=True)
    with open(local_path, "w", encoding="utf-8") as fp:
        json.dump(trace, fp, ensure_ascii=False, default=_json_default)
    try:
        uploaded = _upload_s3(local_path, s3_key)
    except Exception as exc:
        logger.warning(
            "decision trace S3 upload failed - decision_trace_id=%s s3_key=%s error=%s",
            trace.get("decision_trace_id"),
            s3_key,
            exc,
        )
        uploaded = False
    return {"local_path": local_path, "s3_key": s3_key, "s3_uploaded": bool(uploaded)}


def _upsert_trace_row(
    trace: Dict[str, Any],
    *,
    local_path: str,
    jsonl_path: str,
    s3_key: str,
    s3_uploaded: bool,
) -> None:
    _ensure_table()
    index = trace.get("query_index") if isinstance(trace.get("query_index"), dict) else {}
    created_at = _db_datetime(trace["created_at"])
    trade_date = _parse_date(index.get("trade_date"), created_at.date())
    query = """
        INSERT INTO agent_decision_traces (
            decision_trace_id, trade_date, ticker, user_id, strategy_slot,
            action, order_type, risk_decision, risk_blocked, execution_status,
            system_error, analysis_cache_status, market_regime, entry_risk,
            signal_confidence, historical_recommendation, s3_key, local_path,
            jsonl_path, s3_uploaded, created_at
        ) VALUES (
            %s, %s, %s, %s, %s,
            %s, %s, %s, %s, %s,
            %s, %s, %s, %s,
            %s, %s, %s, %s,
            %s, %s, %s
        )
        ON DUPLICATE KEY UPDATE
            trade_date = VALUES(trade_date),
            ticker = VALUES(ticker),
            user_id = VALUES(user_id),
            strategy_slot = VALUES(strategy_slot),
            action = VALUES(action),
            order_type = VALUES(order_type),
            risk_decision = VALUES(risk_decision),
            risk_blocked = VALUES(risk_blocked),
            execution_status = VALUES(execution_status),
            system_error = VALUES(system_error),
            analysis_cache_status = VALUES(analysis_cache_status),
            market_regime = VALUES(market_regime),
            entry_risk = VALUES(entry_risk),
            signal_confidence = VALUES(signal_confidence),
            historical_recommendation = VALUES(historical_recommendation),
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
                    trace.get("decision_trace_id"),
                    trade_date,
                    str(index.get("ticker") or ""),
                    _safe_int(index.get("user_id")),
                    index.get("strategy_slot"),
                    index.get("action"),
                    index.get("order_type"),
                    index.get("risk_decision"),
                    1 if index.get("risk_blocked") else 0,
                    index.get("execution_status"),
                    1 if index.get("system_error") else 0,
                    index.get("analysis_cache_status"),
                    index.get("market_regime"),
                    index.get("entry_risk"),
                    index.get("signal_confidence"),
                    index.get("historical_recommendation"),
                    s3_key,
                    local_path,
                    jsonl_path,
                    1 if s3_uploaded else 0,
                    created_at,
                ),
            )


def build_decision_trace(
    *,
    state: Dict[str, Any],
    order_card: Dict[str, Any],
) -> Dict[str, Any]:
    created_at = datetime.now(KST)
    ticker = str(_safe_get(state, "ticker", order_card.get("ticker") or ""))
    user_id = state.get("user_id")
    strategy_slot = str(_safe_get(state, "resolved_slot", state.get("strategy_slot") or "daily"))
    account_type = str(_safe_get(state, "account_type", "USER"))
    order = order_card.get("order") if isinstance(order_card.get("order"), dict) else {}
    risk_review = order_card.get("risk_review") if isinstance(order_card.get("risk_review"), dict) else {}
    analysis_cache = order_card.get("analysis_cache") if isinstance(order_card.get("analysis_cache"), dict) else {}
    system_error_details = (
        order_card.get("system_error_details") if isinstance(order_card.get("system_error_details"), dict) else {}
    )

    trace_id = _build_decision_trace_id(
        ticker=ticker,
        user_id=int(user_id) if user_id is not None else None,
        strategy_slot=strategy_slot,
        created_at=created_at,
    )
    memory_features = build_memory_features(state=state, order_card=order_card)
    trade_date = str(_safe_get(state, "trade_date", created_at.date().isoformat()))

    return {
        "schema": DECISION_TRACE_SCHEMA,
        "decision_trace_id": trace_id,
        "created_at": created_at.isoformat(),
        "project": "ai-server",
        "workflow": "trading_decision",
        "workflow_version": str(_safe_get(state, "workflow_version", "v1")),
        "runtime": "langgraph",
        "subject": {
            "ticker": ticker,
            "user_id": user_id,
            "account_type": account_type,
            "strategy_slot": strategy_slot,
            "invest_style": state.get("invest_style"),
            "user_investment_style": state.get("user_investment_style"),
        },
        "query_index": {
            "trade_date": trade_date,
            "ticker": ticker,
            "user_id": user_id,
            "strategy_slot": strategy_slot,
            "action": str(_safe_get(order, "action", "hold")).lower(),
            "order_type": str(_safe_get(order, "order_type", "")).lower(),
            "risk_decision": str(_safe_get(risk_review, "decision", "")).upper(),
            "risk_blocked": bool(risk_review.get("blocked")) if isinstance(risk_review, dict) else False,
            "execution_status": str(_safe_get(order_card, "execution_status", "")),
            "system_error": bool(order_card.get("system_error")),
            "analysis_cache_status": analysis_cache.get("status"),
            "market_regime": memory_features.get("market_regime"),
            "entry_risk": memory_features.get("entry_risk"),
            "signal_confidence": memory_features.get("signal_confidence"),
            "historical_recommendation": memory_features.get("historical_recommendation"),
        },
        "steps": [
            {"name": "load_context", "status": "success"},
            {
                "name": "load_analysis",
                "status": "error" if order_card.get("system_error") and system_error_details else "success",
                "cache": analysis_cache,
            },
            {
                "name": "judge_agent",
                "status": "error" if state.get("judge_system_error") else "success",
            },
            {
                "name": "risk_review",
                "status": "blocked" if risk_review.get("blocked") else "success",
                "decision": risk_review.get("decision"),
            },
            {
                "name": "apply_constraints",
                "status": "adjusted" if order_card.get("adjusted_by_account_state") else "success",
            },
            {
                "name": "finalize_execution",
                "status": str(_safe_get(order_card, "execution_status", "")),
            },
        ],
        "signals": {
            "signal_confidence": state.get("signal_confidence"),
            "news_score": _safe_get(state.get("news_card", {}), "score"),
            "news_stance": _safe_get(state.get("news_card", {}), "stance"),
            "quant_score": _safe_get(state.get("quant_card", {}), "score"),
            "quant_stance": _safe_get(state.get("quant_card", {}), "stance"),
            "final_score": order_card.get("final_score"),
            "final_stance": order_card.get("final_stance"),
        },
        "memory_features": memory_features,
        "analysis": {
            "news_card": state.get("news_card", {}),
            "quant_card": state.get("quant_card", {}),
            "quant_state": state.get("quant_state", {}),
            "rebuttal_result": state.get("rebuttal_result", {}),
            "analysis_cache": analysis_cache,
        },
        "decision": {
            "judge_payload": state.get("judge_payload", {}),
            "historical_comparison": state.get("historical_comparison", {}),
            "risk_review": risk_review,
            "order_card": order_card,
            "execution_status": order_card.get("execution_status"),
        },
    }


def save_decision_trace(trace: Dict[str, Any]) -> Dict[str, Any]:
    jsonl_path = _append_jsonl(trace)
    s3_key = build_decision_trace_s3_key(trace)
    object_meta = _save_object(trace, s3_key)
    db_saved = False
    try:
        _upsert_trace_row(
            trace,
            local_path=object_meta["local_path"],
            jsonl_path=jsonl_path,
            s3_key=object_meta["s3_key"],
            s3_uploaded=bool(object_meta["s3_uploaded"]),
        )
        db_saved = True
    except Exception as exc:
        logger.warning(
            "decision trace DB indexing failed - decision_trace_id=%s error=%s",
            trace.get("decision_trace_id"),
            exc,
        )

    return {
        "decision_trace_id": trace["decision_trace_id"],
        "schema": trace["schema"],
        "path": jsonl_path,
        "jsonl_path": jsonl_path,
        "local_path": object_meta["local_path"],
        "s3_key": object_meta["s3_key"],
        "s3_uploaded": object_meta["s3_uploaded"],
        "db_saved": db_saved,
        "query_index": trace.get("query_index", {}),
    }


def iter_decision_trace_records(
    *,
    ticker: Optional[str] = None,
    user_id: Optional[int] = None,
    strategy_slot: Optional[str] = None,
    action: Optional[str] = None,
    risk_decision: Optional[str] = None,
    execution_status: Optional[str] = None,
    from_date: Optional[str] = None,
    to_date: Optional[str] = None,
) -> List[Dict[str, Any]]:
    _ensure_table()
    clauses: List[str] = []
    params: List[Any] = []

    def add_clause(sql: str, value: Any) -> None:
        clauses.append(sql)
        params.append(value)

    if from_date:
        add_clause("trade_date >= %s", _parse_date(from_date, datetime.now(KST).date()))
    if to_date:
        add_clause("trade_date <= %s", _parse_date(to_date, datetime.now(KST).date()))
    if ticker is not None:
        add_clause("LOWER(ticker) = LOWER(%s)", ticker)
    if user_id is not None:
        add_clause("user_id = %s", user_id)
    if strategy_slot is not None:
        add_clause("LOWER(strategy_slot) = LOWER(%s)", strategy_slot)
    if action is not None:
        add_clause("LOWER(action) = LOWER(%s)", action)
    if risk_decision is not None:
        add_clause("LOWER(risk_decision) = LOWER(%s)", risk_decision)
    if execution_status is not None:
        add_clause("LOWER(execution_status) = LOWER(%s)", execution_status)

    where_sql = f"WHERE {' AND '.join(clauses)}" if clauses else ""
    query = f"""
        SELECT *
        FROM agent_decision_traces
        {where_sql}
        ORDER BY trade_date DESC, created_at DESC
    """
    with _open_db_conn() as conn:
        with conn.cursor() as cursor:
            cursor.execute(query, tuple(params))
            return list(cursor.fetchall() or [])


def load_decision_trace_payload(row: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    local_path = str(row.get("local_path") or "")
    s3_key = str(row.get("s3_key") or "")

    if local_path and os.path.exists(local_path):
        with open(local_path, "r", encoding="utf-8") as fp:
            trace = json.load(fp)
            trace["_source_path"] = local_path
            trace["_source_type"] = "db_local_object"
            return trace

    if s3_key:
        local_path = _build_object_local_path(s3_key)
        os.makedirs(os.path.dirname(local_path), exist_ok=True)
        if _download_s3(s3_key, local_path):
            with open(local_path, "r", encoding="utf-8") as fp:
                trace = json.load(fp)
                trace["_source_path"] = local_path
                trace["_source_type"] = "s3_object"
                return trace

    jsonl_path = str(row.get("jsonl_path") or "")
    target = str(row.get("decision_trace_id") or "")
    if not jsonl_path or not target or not os.path.exists(jsonl_path):
        return None

    with open(jsonl_path, "r", encoding="utf-8") as fp:
        for line in fp:
            line = line.strip()
            if not line:
                continue
            try:
                trace = json.loads(line)
            except json.JSONDecodeError:
                continue
            if str(trace.get("decision_trace_id") or "") == target:
                trace["_source_path"] = jsonl_path
                trace["_source_type"] = "jsonl_fallback"
                return trace
    return None
