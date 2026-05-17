import json
import os
import uuid
from datetime import datetime
from decimal import Decimal
from typing import Any, Dict, Optional

from collector.storage import get_storage_dir
from app.trading.constants import KST


DECISION_TRACE_SCHEMA = "agent_decision_trace_v1"


def _json_default(value: Any) -> Any:
    if isinstance(value, Decimal):
        return float(value)
    if isinstance(value, datetime):
        return value.isoformat()
    return str(value)


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
    storage_dir = get_storage_dir("decisions")
    created_at = datetime.fromisoformat(str(trace["created_at"]))
    day_token = created_at.strftime("%Y%m%d")
    file_path = os.path.join(storage_dir, f"{day_token}_decisions.jsonl")

    with open(file_path, "a", encoding="utf-8") as fp:
        fp.write(json.dumps(trace, ensure_ascii=False, default=_json_default))
        fp.write("\n")

    return {
        "decision_trace_id": trace["decision_trace_id"],
        "schema": trace["schema"],
        "path": file_path,
        "query_index": trace.get("query_index", {}),
    }
