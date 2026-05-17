from typing import Any, Dict, Optional

from app.trading.decision_query import get_decision_trace
from app.trading.decision_review_store import build_decision_review, save_decision_review


def _subject_from_trace(trace: Dict[str, Any]) -> Dict[str, Any]:
    subject = trace.get("subject") if isinstance(trace.get("subject"), dict) else {}
    index = trace.get("query_index") if isinstance(trace.get("query_index"), dict) else {}
    return {
        "ticker": subject.get("ticker") or index.get("ticker") or "",
        "user_id": subject.get("user_id") if subject.get("user_id") is not None else index.get("user_id"),
        "strategy_slot": subject.get("strategy_slot") or index.get("strategy_slot"),
    }


def review_decision_trace(
    *,
    decision_trace_id: str,
    market_outcome: Dict[str, Any],
    reviewer: Optional[Any] = None,
    save: bool = True,
) -> Dict[str, Any]:
    trace = get_decision_trace(decision_trace_id)
    if trace is None:
        raise ValueError(f"decision trace not found: {decision_trace_id}")

    if reviewer is None:
        from app.shared.agents.review_agent import ReviewAgent

        reviewer = ReviewAgent()
    agent_review = reviewer.generate_review(decision_trace=trace, market_outcome=market_outcome)
    subject = _subject_from_trace(trace)

    review = build_decision_review(
        decision_trace_id=decision_trace_id,
        ticker=str(subject["ticker"]),
        user_id=subject.get("user_id"),
        strategy_slot=subject.get("strategy_slot"),
        outcome=agent_review["outcome"],
        pnl_pct=agent_review.get("pnl_pct"),
        max_drawdown_pct=agent_review.get("max_drawdown_pct"),
        holding_minutes=agent_review.get("holding_minutes"),
        execution_status=agent_review.get("execution_status"),
        mistake_tags=agent_review.get("mistake_tags", []),
        lesson=agent_review.get("lesson", ""),
        evaluator=reviewer.__class__.__name__,
        extra={
            "signal_assessment": agent_review.get("signal_assessment", {}),
            "review_summary": agent_review.get("review_summary", ""),
            "market_outcome": market_outcome,
        },
    )
    saved = save_decision_review(review) if save else None
    return {"review": review, "saved": saved}
