import logging
import os
import time as time_module
from datetime import datetime, time
from decimal import Decimal
from functools import lru_cache
from typing import Any, Dict, Optional, TypedDict

from langgraph.graph import END, START, StateGraph

from app.news.agent import NewsReporterAgent
from app.news.sources import retrieve_news, retrieve_community_posts
from app.quant.agent import QuantAnalysisAgent
from app.quant.data_loader import get_latest_feature_s3_key, download_and_load_feature_df
from app.quant.pipeline import build_state_from_feature_row
from app.quant.sources import load_ohlcv_from_db
from app.shared.agents.judge_agent import JudgeAgent
from app.shared.agents.rebuttal_agent import RebuttalAgent
from app.trading.account_service import (
    apply_account_constraints,
    build_account_summary,
    cap_buy_quantity,
    extract_holding_from_snapshot,
)
from app.trading.agent_response_store import mark_agent_response
from app.trading.analysis_store import (
    ANALYSIS_WORKFLOW_VERSION,
    current_trade_date,
    load_cache_row,
    load_payload,
    save_completed,
    save_failed,
    try_mark_running,
)
from app.trading.constants import DEFAULT_REBUTTAL_SCORE_GAP_THRESHOLD, KST
from app.trading.core_api_client import execute_order, get_trading_account_snapshot, get_user_profile
from app.trading.market_data import get_current_price
from app.trading.strategy_service import build_signal_weights, build_strategy_profile, resolve_strategy_slot

logger = logging.getLogger(__name__)


class TradingGraphState(TypedDict, total=False):
    ticker: str
    available_cash: int
    user_id: Optional[int]
    account_type: str
    invest_style: str
    execute_immediately: bool
    score_gap_threshold: int
    strategy_slot: Optional[str]
    workflow: str
    workflow_version: str
    user_profile: Dict[str, Any]
    user_investment_style: str
    strategy_profile: Dict[str, Any]
    resolved_slot: str
    actual_available_cash: int
    current_holding: Dict[str, Any]
    curr_price: Decimal
    news_card: Dict[str, Any]
    quant_card: Dict[str, Any]
    quant_state: Dict[str, Any]
    news_system_error: bool
    quant_system_error: bool
    judge_system_error: bool
    news_error_message: str
    quant_error_message: str
    judge_error_message: str
    rebuttal_result: Dict[str, Any]
    analysis_profile: str
    analysis_cache_status: str
    analysis_cache_key: Dict[str, Any]
    signal_confidence: Any
    judge_payload: Dict[str, Any]
    order_card: Dict[str, Any]
    execution_status: str


def _ensure_kst_datetime(value: Any) -> Optional[datetime]:
    if value is None:
        return None
    if hasattr(value, "to_pydatetime"):
        value = value.to_pydatetime()
    if not isinstance(value, datetime):
        return None
    if value.tzinfo is None or value.tzinfo.utcoffset(value) is None:
        return value.replace(tzinfo=KST)
    return value.astimezone(KST)


def _build_today_intraday_context(ticker: str) -> Dict[str, Any]:
    try:
        intraday_df = load_ohlcv_from_db(ticker, days=0)
    except Exception as exc:
        logger.warning("[%s] 당일 장중 데이터 로드 실패: %s", ticker, exc)
        return {}

    if intraday_df.empty:
        return {}

    intraday_df["ts"] = intraday_df["ts"].apply(_ensure_kst_datetime)
    intraday_df = intraday_df.dropna(subset=["ts"])
    intraday_df = intraday_df.sort_values("ts").reset_index(drop=True)
    intraday_df = intraday_df[
        intraday_df["ts"].apply(lambda ts: time(9, 0) <= ts.time() <= time(12, 0))
    ].copy()
    if intraday_df.empty:
        return {}

    first_row = intraday_df.iloc[0]
    last_row = intraday_df.iloc[-1]
    open_price = float(first_row["open"])
    last_price = float(last_row["close"])
    high_price = float(intraday_df["high"].max())
    low_price = float(intraday_df["low"].min())
    total_volume = float(intraday_df["volume"].sum())
    change_pct = ((last_price / open_price) - 1.0) if open_price > 0 else 0.0
    range_pct = ((high_price / low_price) - 1.0) if low_price > 0 else 0.0

    if change_pct >= 0.005:
        trend = "up"
    elif change_pct <= -0.005:
        trend = "down"
    else:
        trend = "neutral"

    return {
        "window": "09:00-12:00",
        "bars": int(len(intraday_df)),
        "open_price": round(open_price, 2),
        "last_price": round(last_price, 2),
        "high_price": round(high_price, 2),
        "low_price": round(low_price, 2),
        "change_pct": round(change_pct, 4),
        "range_pct": round(range_pct, 4),
        "total_volume": int(total_volume),
        "trend": trend,
        "as_of": last_row["ts"].isoformat() if hasattr(last_row["ts"], "isoformat") else str(last_row["ts"]),
    }


def _resolve_signal_confidence(
    news_card: Dict[str, Any],
    quant_card: Dict[str, Any],
    quant_state: Dict[str, Any],
) -> Any:
    quant_risk_context = quant_state.get("risk_context") if isinstance(quant_state, dict) else {}
    quant_signal_confidence = (
        quant_risk_context.get("signal_confidence") if isinstance(quant_risk_context, dict) else None
    )
    if quant_signal_confidence:
        return quant_signal_confidence

    confidences = []
    for card in (news_card, quant_card):
        try:
            confidences.append(float(card.get("confidence")))
        except Exception:
            continue
    if not confidences:
        return None
    return sum(confidences) / len(confidences)


def run_news_agent(ticker: str, question: str = "이 종목의 향후 단기 주가 방향은 어떨까?") -> Dict[str, Any]:
    logger.debug("[%s] 1단계: 뉴스/커뮤니티 수집 및 NewsAgent 실행", ticker)

    news_docs = retrieve_news(ticker, query=question, top_k=5)
    comm_docs = retrieve_community_posts(ticker, query=question, top_k=2)

    agent = NewsReporterAgent()
    return agent.generate_analysis_card(
        ticker=ticker,
        question=question,
        news_docs=news_docs,
        community_docs=comm_docs,
    )


def run_quant_agent(ticker: str) -> tuple[Dict[str, Any], Dict[str, Any]]:
    logger.debug("[%s] 2단계: 퀀트 데이터 로드 및 QuantAgent 실행", ticker)

    latest_s3_key = get_latest_feature_s3_key(ticker)
    if not latest_s3_key:
        return QuantAnalysisAgent._fallback_card(ticker, "S3 피처 정보 없음"), {}

    feat_df = download_and_load_feature_df(ticker, latest_s3_key)
    if feat_df is None or feat_df.empty:
        return QuantAnalysisAgent._fallback_card(ticker, "S3 피처 로드 실패"), {}

    feature_row = feat_df.iloc[-1].to_dict()
    quant_state = build_state_from_feature_row(feature_row, ticker=ticker)
    today_intraday_context = _build_today_intraday_context(ticker)
    if today_intraday_context:
        quant_state["today_intraday_context"] = today_intraday_context

    agent = QuantAnalysisAgent()
    quant_card = agent.generate_analysis_card(ticker=ticker, quant_evidence=quant_state)
    return quant_card, quant_state


def run_rebuttal_agent(
    ticker: str,
    news_card: Dict[str, Any],
    quant_card: Dict[str, Any],
    *,
    score_gap_threshold: int = DEFAULT_REBUTTAL_SCORE_GAP_THRESHOLD,
) -> Dict[str, Any]:
    def _safe_score(card: Dict[str, Any]) -> int:
        try:
            return int(card.get("score", 0))
        except (ValueError, TypeError):
            return 0

    news_score = _safe_score(news_card)
    quant_score = _safe_score(quant_card)
    score_gap = abs(news_score - quant_score)
    triggered = score_gap >= score_gap_threshold

    result: Dict[str, Any] = {
        "triggered": triggered,
        "rebuttal_round": 0,
        "score_gap": score_gap,
        "score_gap_threshold": score_gap_threshold,
        "news_score": news_score,
        "quant_score": quant_score,
    }
    if not triggered:
        return result

    try:
        agent = RebuttalAgent()
        result["rebuttal"] = agent.generate_rebuttal(news_card, quant_card)
        result["rebuttal_round"] = 1
        logger.debug("[%s] Rebuttal 생성 완료", ticker)
    except Exception as exc:
        logger.error("[%s] RebuttalAgent 실행 실패: %s", ticker, exc)
        result["triggered"] = False
        result["error"] = str(exc)

    return result


def _analysis_profile_for_strategy(strategy_profile: Dict[str, Any]) -> str:
    invest_style = str(strategy_profile.get("invest_style") or "LONG").lower()
    return f"common_{invest_style}"


def _build_analysis_payload(
    *,
    ticker: str,
    strategy_slot: str,
    analysis_profile: str,
    news_card: Dict[str, Any],
    quant_card: Dict[str, Any],
    quant_state: Dict[str, Any],
    rebuttal_result: Dict[str, Any],
) -> Dict[str, Any]:
    trade_date = current_trade_date()
    return {
        "schema": "ticker_analysis_v1",
        "ticker": ticker,
        "trade_date": trade_date.isoformat(),
        "strategy_slot": strategy_slot,
        "analysis_profile": analysis_profile,
        "workflow_version": ANALYSIS_WORKFLOW_VERSION,
        "generated_at": datetime.now(KST).isoformat(),
        "news_card": news_card,
        "quant_card": quant_card,
        "quant_state": quant_state,
        "rebuttal_result": rebuttal_result,
        "status": "completed",
    }


def _wait_for_completed_analysis(
    *,
    ticker: str,
    strategy_slot: str,
    analysis_profile: str,
) -> Optional[Dict[str, Any]]:
    wait_seconds = max(0, int(os.getenv("TICKER_ANALYSIS_CACHE_WAIT_SECONDS", "30")))
    poll_seconds = max(1, int(os.getenv("TICKER_ANALYSIS_CACHE_POLL_SECONDS", "2")))
    deadline = time_module.time() + wait_seconds

    while time_module.time() <= deadline:
        row = load_cache_row(
            ticker=ticker,
            strategy_slot=strategy_slot,
            analysis_profile=analysis_profile,
            workflow_version=ANALYSIS_WORKFLOW_VERSION,
        )
        if row and row.get("status") == "completed":
            payload = load_payload(row)
            if payload:
                return payload
        if row and row.get("status") == "failed":
            return None
        time_module.sleep(poll_seconds)
    return None


def _load_or_create_ticker_analysis(
    *,
    ticker: str,
    strategy_slot: str,
    strategy_profile: Dict[str, Any],
    score_gap_threshold: int,
) -> tuple[Dict[str, Any], str]:
    analysis_profile = _analysis_profile_for_strategy(strategy_profile)
    row = load_cache_row(
        ticker=ticker,
        strategy_slot=strategy_slot,
        analysis_profile=analysis_profile,
        workflow_version=ANALYSIS_WORKFLOW_VERSION,
    )
    if row and row.get("status") == "completed":
        payload = load_payload(row)
        if payload:
            return payload, "hit"

    acquired = try_mark_running(
        ticker=ticker,
        strategy_slot=strategy_slot,
        analysis_profile=analysis_profile,
        workflow_version=ANALYSIS_WORKFLOW_VERSION,
    )
    if not acquired:
        payload = _wait_for_completed_analysis(
            ticker=ticker,
            strategy_slot=strategy_slot,
            analysis_profile=analysis_profile,
        )
        if payload:
            return payload, "wait_hit"
        acquired = try_mark_running(
            ticker=ticker,
            strategy_slot=strategy_slot,
            analysis_profile=analysis_profile,
            workflow_version=ANALYSIS_WORKFLOW_VERSION,
        )
        if not acquired:
            raise RuntimeError("ticker analysis is running and no completed payload is available")

    try:
        news_card = run_news_agent(ticker, question=strategy_profile["news_question"])
        quant_card, quant_state = run_quant_agent(ticker)
        if news_card.get("risk_flags") == ["system_error"] or quant_card.get("risk_flags") == ["system_error"]:
            rebuttal_result = {
                "triggered": False,
                "rebuttal_round": 0,
                "skipped": True,
                "reason": "upstream_system_error",
            }
        else:
            rebuttal_result = run_rebuttal_agent(
                ticker,
                news_card,
                quant_card,
                score_gap_threshold=score_gap_threshold,
            )
        payload = _build_analysis_payload(
            ticker=ticker,
            strategy_slot=strategy_slot,
            analysis_profile=analysis_profile,
            news_card=news_card,
            quant_card=quant_card,
            quant_state=quant_state,
            rebuttal_result=rebuttal_result,
        )
        archive = save_completed(
            payload=payload,
            ticker=ticker,
            strategy_slot=strategy_slot,
            analysis_profile=analysis_profile,
            workflow_version=ANALYSIS_WORKFLOW_VERSION,
        )
        payload["archive"] = archive
        return payload, "created"
    except Exception as exc:
        save_failed(
            ticker=ticker,
            strategy_slot=strategy_slot,
            analysis_profile=analysis_profile,
            error=exc,
            workflow_version=ANALYSIS_WORKFLOW_VERSION,
        )
        raise


def _build_system_error_analysis_card(*, ticker: str, agent: str, error: Exception) -> Dict[str, Any]:
    return {
        "$schema": "analysis_card_v1",
        "agent": agent,
        "ticker": ticker,
        "timestamp": datetime.now(KST).isoformat(),
        "stance": "hold",
        "confidence": 0.0,
        "score": 0,
        "signal_breakdown": {"system_error": 1},
        "top_reasons": [f"시스템 에러로 인한 판단 불가: {error}"],
        "risk_flags": ["system_error"],
        "requested_action": {"preference": "hold", "avoid_if": "system_error"},
    }


def _build_system_error_order_card(*, ticker: str, error: Exception) -> Dict[str, Any]:
    return {
        "$schema": "order_card_v1",
        "ticker": ticker,
        "timestamp": datetime.now(KST).isoformat(),
        "final_stance": "hold",
        "final_score": 0,
        "order": {
            "action": "hold",
            "order_type": "limit",
            "quantity": 0,
            "price": 0,
            "time_in_force": "day",
        },
        "risk_management": {"stop_loss_price": 0, "take_profit_price": 0},
        "verdict": f"시스템 장애로 인한 강제 관망 (에러: {error})",
    }


def _load_context_node(state: TradingGraphState) -> TradingGraphState:
    ticker = state["ticker"]
    user_id = state.get("user_id")
    account_type = state.get("account_type", "USER")
    available_cash = int(state.get("available_cash") or 0)
    invest_style = state.get("invest_style", "LONG")

    logger.info("[%s] LangGraph 오케스트레이션 시작 (User=%s, Style=%s)", ticker, user_id, invest_style)

    user_profile = get_user_profile(user_id=user_id) if user_id is not None else {}
    user_investment_style = str(user_profile.get("investmentStyle") or "GROWTH").upper()
    strategy_profile = build_strategy_profile(invest_style, user_investment_style)
    resolved_slot = resolve_strategy_slot(state.get("strategy_slot"))

    account_info = get_trading_account_snapshot(user_id=user_id, account_type=account_type)
    actual_available_cash = int(account_info.get("availableAmt") or available_cash)
    current_holding = extract_holding_from_snapshot(account_info, ticker)
    curr_price = get_current_price(ticker) or Decimal("0")

    return {
        "user_profile": user_profile,
        "user_investment_style": user_investment_style,
        "strategy_profile": strategy_profile,
        "resolved_slot": resolved_slot,
        "actual_available_cash": actual_available_cash,
        "current_holding": current_holding,
        "curr_price": curr_price,
    }


def _news_agent_node(state: TradingGraphState) -> TradingGraphState:
    ticker = state["ticker"]
    user_id = state.get("user_id")
    resolved_slot = state["resolved_slot"]
    strategy_profile = state["strategy_profile"]

    try:
        news_card = run_news_agent(ticker, question=strategy_profile["news_question"])
        mark_agent_response(user_id=user_id, ticker=ticker, strategy_slot=resolved_slot, agent_type="news")
        return {
            "news_card": news_card,
            "news_system_error": False,
            "news_error_message": "",
        }
    except Exception as exc:
        logger.error("[%s] NewsAgent 노드 실행 실패: %s", ticker, exc)
        return {
            "news_card": _build_system_error_analysis_card(ticker=ticker, agent="news", error=exc),
            "news_system_error": True,
            "news_error_message": str(exc),
        }


def _quant_agent_node(state: TradingGraphState) -> TradingGraphState:
    ticker = state["ticker"]
    user_id = state.get("user_id")
    resolved_slot = state["resolved_slot"]

    try:
        quant_card, quant_state = run_quant_agent(ticker)
        mark_agent_response(user_id=user_id, ticker=ticker, strategy_slot=resolved_slot, agent_type="quant")
        return {
            "quant_card": quant_card,
            "quant_state": quant_state,
            "quant_system_error": False,
            "quant_error_message": "",
        }
    except Exception as exc:
        logger.error("[%s] QuantAgent 노드 실행 실패: %s", ticker, exc)
        return {
            "quant_card": _build_system_error_analysis_card(ticker=ticker, agent="quant", error=exc),
            "quant_state": {},
            "quant_system_error": True,
            "quant_error_message": str(exc),
        }


def _load_analysis_node(state: TradingGraphState) -> TradingGraphState:
    ticker = state["ticker"]
    user_id = state.get("user_id")
    resolved_slot = state["resolved_slot"]
    strategy_profile = state["strategy_profile"]
    analysis_profile = _analysis_profile_for_strategy(strategy_profile)

    try:
        analysis_payload, cache_status = _load_or_create_ticker_analysis(
            ticker=ticker,
            strategy_slot=resolved_slot,
            strategy_profile=strategy_profile,
            score_gap_threshold=int(state.get("score_gap_threshold") or DEFAULT_REBUTTAL_SCORE_GAP_THRESHOLD),
        )
        mark_agent_response(user_id=user_id, ticker=ticker, strategy_slot=resolved_slot, agent_type="news")
        mark_agent_response(user_id=user_id, ticker=ticker, strategy_slot=resolved_slot, agent_type="quant")
        return {
            "news_card": analysis_payload.get("news_card") or {},
            "quant_card": analysis_payload.get("quant_card") or {},
            "quant_state": analysis_payload.get("quant_state") or {},
            "rebuttal_result": analysis_payload.get("rebuttal_result") or {},
            "news_system_error": False,
            "quant_system_error": False,
            "news_error_message": "",
            "quant_error_message": "",
            "analysis_profile": analysis_profile,
            "analysis_cache_status": cache_status,
            "analysis_cache_key": {
                "ticker": ticker,
                "trade_date": analysis_payload.get("trade_date"),
                "strategy_slot": resolved_slot,
                "analysis_profile": analysis_profile,
                "workflow_version": ANALYSIS_WORKFLOW_VERSION,
            },
        }
    except Exception as exc:
        logger.error("[%s] TickerAnalysis load/create failed: %s", ticker, exc)
        return {
            "news_card": _build_system_error_analysis_card(ticker=ticker, agent="news", error=exc),
            "quant_card": _build_system_error_analysis_card(ticker=ticker, agent="quant", error=exc),
            "quant_state": {},
            "rebuttal_result": {
                "triggered": False,
                "rebuttal_round": 0,
                "skipped": True,
                "reason": "analysis_system_error",
            },
            "news_system_error": True,
            "quant_system_error": True,
            "news_error_message": str(exc),
            "quant_error_message": str(exc),
            "analysis_profile": analysis_profile,
            "analysis_cache_status": "error",
            "analysis_cache_key": {
                "ticker": ticker,
                "trade_date": current_trade_date().isoformat(),
                "strategy_slot": resolved_slot,
                "analysis_profile": analysis_profile,
                "workflow_version": ANALYSIS_WORKFLOW_VERSION,
            },
        }


def _rebuttal_agent_node(state: TradingGraphState) -> TradingGraphState:
    ticker = state["ticker"]
    if state.get("news_system_error") or state.get("quant_system_error"):
        return {
            "rebuttal_result": {
                "triggered": False,
                "rebuttal_round": 0,
                "skipped": True,
                "reason": "upstream_system_error",
            }
        }
    rebuttal_result = run_rebuttal_agent(
        ticker,
        state["news_card"],
        state["quant_card"],
        score_gap_threshold=int(state.get("score_gap_threshold") or DEFAULT_REBUTTAL_SCORE_GAP_THRESHOLD),
    )
    return {"rebuttal_result": rebuttal_result}


def _judge_agent_node(state: TradingGraphState) -> TradingGraphState:
    ticker = state["ticker"]
    user_id = state.get("user_id")
    resolved_slot = state["resolved_slot"]
    actual_available_cash = state["actual_available_cash"]
    current_holding = state["current_holding"]
    curr_price = state["curr_price"]
    strategy_profile = state["strategy_profile"]
    user_investment_style = state["user_investment_style"]
    quant_state = state.get("quant_state", {})
    news_card = state["news_card"]
    quant_card = state["quant_card"]
    rebuttal_result = state["rebuttal_result"]

    signal_conf = _resolve_signal_confidence(news_card, quant_card, quant_state)
    max_buy_qty, _ = cap_buy_quantity(
        requested_qty=999999,
        available_cash=actual_available_cash,
        current_holding=current_holding,
        effective_price=int(curr_price),
        user_investment_style=user_investment_style,
        signal_confidence=signal_conf,
    )
    max_sell_qty = int(current_holding.get("available_quantity") or 0)

    judge_payload = {
        "ticker": ticker,
        "current_price": int(curr_price),
        "available_cash": actual_available_cash,
        "current_holding": current_holding,
        "max_allowed_buy_quantity": max_buy_qty,
        "max_allowed_sell_quantity": max_sell_qty,
        "signal_confidence": signal_conf,
        "risk_type": strategy_profile["risk_type"],
        "invest_style": strategy_profile["invest_style"],
        "user_investment_style": strategy_profile["user_investment_style"],
        "strategy_prompt": strategy_profile["strategy_prompt"],
        "strategy_slot": resolved_slot,
        "signal_weights": build_signal_weights(resolved_slot),
        "news_card": news_card,
        "quant_card": quant_card,
        "quant_state_summary": quant_state,
        "rebuttal": rebuttal_result,
    }

    try:
        order_card = JudgeAgent().generate_order_card(judge_payload)
        mark_agent_response(user_id=user_id, ticker=ticker, strategy_slot=resolved_slot, agent_type="judge")
        return {
            "signal_confidence": signal_conf,
            "judge_payload": judge_payload,
            "order_card": order_card,
            "judge_system_error": False,
            "judge_error_message": "",
        }
    except Exception as exc:
        logger.error("[%s] JudgeAgent 노드 실행 실패: %s", ticker, exc)
        return {
            "signal_confidence": signal_conf,
            "judge_payload": judge_payload,
            "order_card": _build_system_error_order_card(ticker=ticker, error=exc),
            "judge_system_error": True,
            "judge_error_message": str(exc),
        }


def _apply_constraints_node(state: TradingGraphState) -> TradingGraphState:
    order_card = apply_account_constraints(
        state["order_card"],
        available_cash=state["actual_available_cash"],
        current_holding=state["current_holding"],
        current_price=state["curr_price"],
        user_investment_style=state["user_investment_style"],
        signal_confidence=state.get("signal_confidence"),
    )

    order_card.update(
        {
            "account_snapshot": build_account_summary(
                available_cash=state["actual_available_cash"],
                current_holding=state["current_holding"],
                account_type=state.get("account_type", "USER"),
                user_id=state.get("user_id"),
                strategy_profile=state["strategy_profile"],
                strategy_slot=state["resolved_slot"],
            ),
            "rebuttal": state["rebuttal_result"],
            "analysis_cache": {
                "status": state.get("analysis_cache_status"),
                "key": state.get("analysis_cache_key"),
            },
            "execution_mode": "immediate" if state.get("execute_immediately") else "deferred",
            "workflow": state.get("workflow", "langgraph"),
            "workflow_version": state.get("workflow_version", "v1"),
            "system_error": bool(
                state.get("news_system_error")
                or state.get("quant_system_error")
                or state.get("judge_system_error")
            ),
            "system_error_details": {
                "news": state.get("news_error_message"),
                "quant": state.get("quant_error_message"),
                "judge": state.get("judge_error_message"),
            },
        }
    )
    return {"order_card": order_card}


def _execute_finalize_node(state: TradingGraphState) -> TradingGraphState:
    order_card = state["order_card"]
    curr_price = state["curr_price"]
    if state.get("execute_immediately"):
        execution_status = _execute_finalize(
            state["ticker"],
            order_card.get("order", {}),
            state.get("user_id"),
            state.get("account_type", "USER"),
            curr_price,
        )
    else:
        execution_status = "planned" if order_card.get("order", {}).get("action") in ["buy", "sell"] else "hold"

    order_card["execution_status"] = execution_status
    logger.info("[%s] LangGraph 오케스트레이션 완료 - Status=%s", state["ticker"], execution_status)
    return {"execution_status": execution_status, "order_card": order_card}


def _execute_finalize(
    ticker: str,
    order: Dict[str, Any],
    user_id: int | None,
    account_type: str,
    curr_price: Decimal,
) -> str:
    action = order.get("action", "hold").lower()
    if action not in ["buy", "sell"]:
        return "hold"

    quantity = int(order.get("quantity") or 0)
    if quantity <= 0:
        return "skipped (zero quantity)"

    price = int(order.get("price") or int(curr_price))
    logger.debug("[%s] %s 주문 실행: %s주 @ %s원", ticker, action.upper(), quantity, price)

    success = execute_order(
        ticker,
        action,
        price,
        quantity,
        user_id=user_id,
        account_type=account_type,
    )
    return "success" if success else "failed"


@lru_cache(maxsize=1)
def get_trading_graph():
    graph = StateGraph(TradingGraphState)
    graph.add_node("load_context", _load_context_node)
    graph.add_node("load_analysis", _load_analysis_node)
    graph.add_node("judge_agent", _judge_agent_node)
    graph.add_node("apply_constraints", _apply_constraints_node)
    graph.add_node("finalize_execution", _execute_finalize_node)

    graph.add_edge(START, "load_context")
    graph.add_edge("load_context", "load_analysis")
    graph.add_edge("load_analysis", "judge_agent")
    graph.add_edge("judge_agent", "apply_constraints")
    graph.add_edge("apply_constraints", "finalize_execution")
    graph.add_edge("finalize_execution", END)
    return graph.compile()


def orchestrate_trading(
    ticker: str,
    available_cash: int = 5000000,
    user_id: Optional[int] = None,
    account_type: str = "USER",
    invest_style: str = "LONG",
    execute_immediately: bool = False,
    score_gap_threshold: int = DEFAULT_REBUTTAL_SCORE_GAP_THRESHOLD,
    strategy_slot: Optional[str] = None,
) -> Dict[str, Any]:
    initial_state: TradingGraphState = {
        "ticker": ticker,
        "available_cash": available_cash,
        "user_id": user_id,
        "account_type": account_type,
        "invest_style": invest_style,
        "execute_immediately": execute_immediately,
        "score_gap_threshold": score_gap_threshold,
        "strategy_slot": strategy_slot,
        "workflow": "langgraph",
        "workflow_version": "v1",
    }
    final_state = get_trading_graph().invoke(initial_state)
    return final_state["order_card"]
