import glob
import json
import logging
import os
import time
from collections import Counter
from datetime import date, datetime
from typing import Any, Dict, List, Optional

from collector.storage import get_storage_dir
from app.trading.decision_store import iter_decision_trace_records, load_decision_trace_payload
from app.trading.decision_review_store import load_latest_reviews_by_decision_id


logger = logging.getLogger(__name__)


def _parse_date(value: Optional[str]) -> Optional[date]:
    if not value:
        return None
    return datetime.fromisoformat(str(value)).date()


def _safe_float(value: Any) -> Optional[float]:
    try:
        if value is None:
            return None
        return float(value)
    except Exception:
        return None


def _days_between(left: Optional[str], right: Optional[str]) -> Optional[int]:
    try:
        left_date = _parse_date(left)
        right_date = _parse_date(right)
    except Exception:
        return None
    if left_date is None or right_date is None:
        return None
    return abs((right_date - left_date).days)


def _matches(value: Any, expected: Any) -> bool:
    if expected is None:
        return True
    return str(value).lower() == str(expected).lower()


def _date_in_range(value: Optional[str], from_date: Optional[str], to_date: Optional[str]) -> bool:
    parsed = _parse_date(value)
    if parsed is None:
        return False
    start = _parse_date(from_date)
    end = _parse_date(to_date)
    if start and parsed < start:
        return False
    if end and parsed > end:
        return False
    return True


def _same_text(left: Any, right: Any) -> bool:
    if left is None or right is None:
        return False
    return str(left).strip().lower() == str(right).strip().lower()


def _numeric_similarity(left: Any, right: Any, *, max_distance: float) -> float:
    left_value = _safe_float(left)
    right_value = _safe_float(right)
    if left_value is None or right_value is None:
        return 0.0
    distance = abs(left_value - right_value)
    return max(0.0, 1.0 - min(distance, max_distance) / max_distance)


def _review_quality_bonus(review: Optional[Dict[str, Any]]) -> float:
    if not isinstance(review, dict):
        return 0.0
    score = 0.5
    outcome = str(review.get("outcome") or "").upper()
    if outcome == "WIN":
        score += 0.7
    elif outcome == "LOSS":
        score += 0.4
    elif outcome in {"FLAT", "NOT_EXECUTED"}:
        score += 0.2
    if review.get("lesson"):
        score += 0.4
    if review.get("mistake_tags"):
        score += 0.3
    return score


def _summarize_items(items: List[Dict[str, Any]]) -> Dict[str, Any]:
    outcomes: Counter[str] = Counter()
    actions: Counter[str] = Counter()
    risk_decisions: Counter[str] = Counter()
    historical_recommendations: Counter[str] = Counter()
    tags: Counter[str] = Counter()
    action_outcomes: Counter[str] = Counter()
    action_tags: Counter[str] = Counter()
    pnl_values: List[float] = []
    win_pnls: List[float] = []
    loss_pnls: List[float] = []
    drawdowns: List[float] = []
    executed_count = 0

    for item in items:
        order = item.get("order") if isinstance(item.get("order"), dict) else {}
        review = item.get("review") if isinstance(item.get("review"), dict) else {}
        risk_review = item.get("risk_review") if isinstance(item.get("risk_review"), dict) else {}
        features = item.get("memory_features") if isinstance(item.get("memory_features"), dict) else {}

        action = str(order.get("action") or features.get("action") or "").lower()
        if action:
            actions[action] += 1
        risk_decision = str(risk_review.get("decision") or features.get("risk_decision") or "").upper()
        if risk_decision:
            risk_decisions[risk_decision] += 1
        recommendation = str(features.get("historical_recommendation") or "").upper()
        if recommendation:
            historical_recommendations[recommendation] += 1

        outcome = str(review.get("outcome") or "").upper()
        if outcome:
            outcomes[outcome] += 1
            if action:
                action_outcomes[f"{action}:{outcome}"] += 1
        if str(item.get("execution_status") or "").lower() == "filled":
            executed_count += 1

        pnl = _safe_float(review.get("pnl_pct"))
        if pnl is not None:
            pnl_values.append(pnl)
            if outcome == "WIN":
                win_pnls.append(pnl)
            elif outcome == "LOSS":
                loss_pnls.append(pnl)
        drawdown = _safe_float(review.get("max_drawdown_pct"))
        if drawdown is not None:
            drawdowns.append(drawdown)

        for tag in review.get("mistake_tags") or []:
            tag_value = str(tag)
            tags[tag_value] += 1
            if action:
                action_tags[f"{action}:{tag_value}"] += 1

    def avg(values: List[float]) -> Optional[float]:
        if not values:
            return None
        return round(sum(values) / len(values), 4)

    return {
        "cases_considered": len(items),
        "executed_count": executed_count,
        "outcome_counts": dict(outcomes),
        "action_counts": dict(actions),
        "risk_decision_counts": dict(risk_decisions),
        "historical_recommendation_counts": dict(historical_recommendations),
        "tag_counts": dict(tags),
        "action_outcome_counts": dict(action_outcomes),
        "action_tag_counts": dict(action_tags),
        "avg_pnl_pct": avg(pnl_values),
        "avg_win_pnl_pct": avg(win_pnls),
        "avg_loss_pnl_pct": avg(loss_pnls),
        "worst_drawdown_pct": min(drawdowns) if drawdowns else None,
    }


def _similarity_score(
    trace: Dict[str, Any],
    similar_to: Optional[Dict[str, Any]],
    *,
    review: Optional[Dict[str, Any]] = None,
    to_date: Optional[str] = None,
) -> float:
    if not similar_to:
        return round(_review_quality_bonus(review), 4)
    signals = trace.get("signals") if isinstance(trace.get("signals"), dict) else {}
    features = trace.get("memory_features") if isinstance(trace.get("memory_features"), dict) else {}
    index = trace.get("query_index") if isinstance(trace.get("query_index"), dict) else {}
    score = 0.0

    for key, weight in (
        ("news_stance", 1.0),
        ("quant_stance", 1.0),
        ("market_regime", 1.2),
        ("entry_risk", 1.0),
        ("signal_confidence", 0.8),
        ("volatility_state", 0.6),
        ("volume_state", 0.4),
        ("price_vs_vwap", 0.4),
        ("intraday_position", 0.4),
    ):
        trace_value = features.get(key, signals.get(key))
        if _same_text(trace_value, similar_to.get(key)):
            score += weight

    for key, max_distance, weight in (
        ("news_score", 60.0, 1.0),
        ("quant_score", 60.0, 1.0),
        ("final_score", 60.0, 0.7),
        ("mtf_alignment", 1.0, 1.2),
        ("current_position_ratio", 1.0, 0.5),
    ):
        trace_value = features.get(key, signals.get(key))
        score += _numeric_similarity(trace_value, similar_to.get(key), max_distance=max_distance) * weight

    if review:
        score += _review_quality_bonus(review)

    days_old = _days_between(index.get("trade_date"), to_date)
    if days_old is not None:
        score += max(0.0, 1.0 - min(days_old, 120) / 120.0) * 0.5

    return round(score, 4)


def _iter_decision_traces() -> List[Dict[str, Any]]:
    storage_dir = get_storage_dir("decisions")
    traces: List[Dict[str, Any]] = []
    for path in sorted(glob.glob(os.path.join(storage_dir, "*_decisions.jsonl"))):
        with open(path, "r", encoding="utf-8") as fp:
            for line in fp:
                line = line.strip()
                if not line:
                    continue
                try:
                    trace = json.loads(line)
                except json.JSONDecodeError:
                    continue
                trace["_source_path"] = path
                traces.append(trace)
    return traces


def _iter_indexed_decision_traces(
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
    records = iter_decision_trace_records(
        ticker=ticker,
        user_id=user_id,
        strategy_slot=strategy_slot,
        action=action,
        risk_decision=risk_decision,
        execution_status=execution_status,
        from_date=from_date,
        to_date=to_date,
    )
    traces: List[Dict[str, Any]] = []
    for record in records:
        trace = load_decision_trace_payload(record)
        if trace is not None:
            traces.append(trace)
    return traces


def search_decision_traces(
    *,
    ticker: Optional[str] = None,
    user_id: Optional[int] = None,
    strategy_slot: Optional[str] = None,
    action: Optional[str] = None,
    risk_decision: Optional[str] = None,
    execution_status: Optional[str] = None,
    from_date: Optional[str] = None,
    to_date: Optional[str] = None,
    similar_to: Optional[Dict[str, Any]] = None,
    limit: int = 20,
) -> Dict[str, Any]:
    started = time.perf_counter()
    items: List[Dict[str, Any]] = []
    latest_reviews = load_latest_reviews_by_decision_id()
    try:
        traces = _iter_indexed_decision_traces(
            ticker=ticker,
            user_id=user_id,
            strategy_slot=strategy_slot,
            action=action,
            risk_decision=risk_decision,
            execution_status=execution_status,
            from_date=from_date,
            to_date=to_date,
        )
    except Exception as exc:
        logger.warning("decision trace DB/S3 search failed; falling back to local JSONL - error=%s", exc)
        traces = []
    if not traces:
        traces = _iter_decision_traces()

    for trace in traces:
        index = trace.get("query_index") if isinstance(trace.get("query_index"), dict) else {}
        if not _date_in_range(index.get("trade_date"), from_date, to_date):
            continue
        if not _matches(index.get("ticker"), ticker):
            continue
        if not _matches(index.get("user_id"), user_id):
            continue
        if not _matches(index.get("strategy_slot"), strategy_slot):
            continue
        if not _matches(index.get("action"), action):
            continue
        if not _matches(index.get("risk_decision"), risk_decision):
            continue
        if not _matches(index.get("execution_status"), execution_status):
            continue

        decision_trace_id = trace.get("decision_trace_id")
        review = latest_reviews.get(str(decision_trace_id)) or trace.get("review")
        item = {
            "decision_trace_id": decision_trace_id,
            "created_at": trace.get("created_at"),
            "query_index": index,
            "signals": trace.get("signals", {}),
            "memory_features": trace.get("memory_features", {}),
            "risk_review": trace.get("decision", {}).get("risk_review", {}),
            "order": trace.get("decision", {}).get("order_card", {}).get("order", {}),
            "execution_status": trace.get("decision", {}).get("execution_status"),
            "review": review,
            "source_path": trace.get("_source_path"),
            "similarity_score": _similarity_score(trace, similar_to, review=review, to_date=to_date),
        }
        items.append(item)

    items.sort(key=lambda item: (item.get("similarity_score", 0.0), str(item.get("created_at") or "")), reverse=True)
    limited_items = items[: max(1, limit)]
    elapsed_ms = round((time.perf_counter() - started) * 1000, 3)
    return {
        "count": len(items),
        "items": limited_items,
        "summary": _summarize_items(limited_items),
        "elapsed_ms": elapsed_ms,
        "filters": {
            "ticker": ticker,
            "user_id": user_id,
            "strategy_slot": strategy_slot,
            "action": action,
            "risk_decision": risk_decision,
            "execution_status": execution_status,
            "from_date": from_date,
            "to_date": to_date,
            "limit": limit,
        },
        "similar_to": similar_to or {},
    }


def get_decision_trace(decision_trace_id: str) -> Optional[Dict[str, Any]]:
    target = str(decision_trace_id or "")
    if not target:
        return None
    latest_reviews = load_latest_reviews_by_decision_id()
    try:
        traces = _iter_indexed_decision_traces()
    except Exception as exc:
        logger.warning("decision trace DB/S3 get failed; falling back to local JSONL - error=%s", exc)
        traces = []
    if not traces:
        traces = _iter_decision_traces()

    for trace in traces:
        if str(trace.get("decision_trace_id") or "") != target:
            continue
        review = latest_reviews.get(target) or trace.get("review")
        if review:
            trace["review"] = review
        return trace
    return None


class LocalDecisionHistoryProvider:
    def search(self, **kwargs: Any) -> Dict[str, Any]:
        return search_decision_traces(**kwargs)


class TheseusToolDecisionHistoryProvider:
    """Adapter placeholder for a future Theseus-generated decision lookup tool."""

    def __init__(self, tool_callable: Any):
        self.tool_callable = tool_callable

    def search(self, **kwargs: Any) -> Dict[str, Any]:
        return self.tool_callable(**kwargs)
