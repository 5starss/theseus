import logging
from datetime import datetime, time
from decimal import Decimal
from typing import Any, Dict, Optional

from app.news.agent import NewsReporterAgent
from app.news.sources import retrieve_news, retrieve_community_posts
from app.quant.agent import QuantAnalysisAgent
from app.quant.data_loader import get_latest_feature_s3_key, download_and_load_feature_df
from app.quant.pipeline import build_state_from_feature_row
from app.quant.sources import load_ohlcv_from_db
from app.shared.agents.judge_agent import JudgeAgent
from app.shared.agents.rebuttal_agent import RebuttalAgent
from app.trading.account_service import (
    extract_holding_from_snapshot,
    apply_account_constraints,
    build_account_summary,
)
from app.trading.agent_response_store import mark_agent_response
from app.trading.constants import DEFAULT_REBUTTAL_SCORE_GAP_THRESHOLD, KST
from app.trading.core_api_client import get_trading_account_snapshot, execute_order, get_user_profile
from app.trading.market_data import get_current_price
from app.trading.strategy_service import (
    resolve_strategy_slot,
    build_strategy_profile,
    build_signal_weights,
)

logger = logging.getLogger(__name__)


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
    """
    RAG(ChromaDB)를 통해 뉴스와 커뮤니티 글을 검색하여 분석을 수행합니다.
    """
    logger.debug(f"[{ticker}] 1단계: 뉴스/커뮤니티 수집 및 NewsAgent 실행")
    
    news_docs = retrieve_news(ticker, query=question, top_k=5)
    comm_docs = retrieve_community_posts(ticker, query=question, top_k=3)
    
    agent = NewsReporterAgent()
    return agent.generate_analysis_card(
        ticker=ticker,
        question=question,
        news_docs=news_docs,
        community_docs=comm_docs
    )


def run_quant_agent(ticker: str) -> tuple[Dict[str, Any], Dict[str, Any]]:
    """
    S3 피처 데이터를 로드하고 상태 스키마 기반의 분석을 수행합니다.
    """
    logger.debug(f"[{ticker}] 2단계: 퀀트 데이터 로드 및 QuantAgent 실행")

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
    """
    두 에이전트 간의 의견 점수 차이가 큰 경우 Rebuttal(반박/재토론) 과정을 수행합니다.
    """
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
        logger.debug(f"[{ticker}] Rebuttal 생성 완료")
    except Exception as e:
        logger.error(f"[{ticker}] RebuttalAgent 실행 실패: {e}")
        result["triggered"] = False
        result["error"] = str(e)

    return result


def orchestrate_trading(
    ticker: str,
    available_cash: int = 5000000,
    user_id: Optional[int] = None,
    account_type: str = "USER",
    invest_style: str = "LONG",
    execute_immediately: bool = True,
    score_gap_threshold: int = DEFAULT_REBUTTAL_SCORE_GAP_THRESHOLD,
    strategy_slot: Optional[str] = None,
) -> Dict[str, Any]:
    """
    전체 에이전트 파이프라인(News -> Quant -> Rebuttal -> Judge)을 총괄하여 최종 매매를 결정 및 실행합니다.
    """
    logger.info("[%s] 오케스트레이션 시작 (User=%s, Style=%s)", ticker, user_id, invest_style)

    # 1. 설정 및 프로필 결정
    user_profile = get_user_profile(user_id=user_id) if user_id is not None else {}
    user_investment_style = str(user_profile.get("investmentStyle") or "GROWTH").upper()
    strategy_profile = build_strategy_profile(invest_style, user_investment_style)
    resolved_slot = resolve_strategy_slot(strategy_slot)
    
    # 2. 계좌 정보 및 실시간 시세 조회
    account_info = get_trading_account_snapshot(user_id=user_id, account_type=account_type)
    available_cash = int(account_info.get("availableAmt") or available_cash)
    current_holding = extract_holding_from_snapshot(account_info, ticker)
    curr_price = get_current_price(ticker) or Decimal("0")

    # 3. 개별 에이전트 분석 (순차 실행)
    news_card = run_news_agent(ticker, question=strategy_profile["news_question"])
    mark_agent_response(user_id=user_id, ticker=ticker, strategy_slot=resolved_slot, agent_type="news")
    quant_card, quant_state = run_quant_agent(ticker)
    mark_agent_response(user_id=user_id, ticker=ticker, strategy_slot=resolved_slot, agent_type="quant")
    
    # 4. 상충 의견 검토 (Rebuttal)
    rebuttal_result = run_rebuttal_agent(
        ticker, news_card, quant_card, score_gap_threshold=score_gap_threshold
    )
    
    # 5. 최종 판정 (Judge Agent)
    judge_payload = {
        "ticker": ticker,
        "current_price": int(curr_price),
        "available_cash": available_cash,
        "current_holding": current_holding,
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
    
    order_card = JudgeAgent().generate_order_card(judge_payload)
    mark_agent_response(user_id=user_id, ticker=ticker, strategy_slot=resolved_slot, agent_type="judge")
    
    # 6. 현실적 제약 조건 적용 (예수금/보유량)
    order_card = apply_account_constraints(
        order_card,
        available_cash=available_cash,
        current_holding=current_holding,
        current_price=curr_price,
        user_investment_style=user_investment_style,
        signal_confidence=_resolve_signal_confidence(news_card, quant_card, quant_state),
    )
    
    # 7. 메타데이터 후처리
    order_card.update({
        "account_snapshot": build_account_summary(
            available_cash=available_cash,
            current_holding=current_holding,
            account_type=account_type,
            user_id=user_id,
            strategy_profile=strategy_profile,
            strategy_slot=resolved_slot,
        ),
        "rebuttal": rebuttal_result,
        "execution_mode": "immediate" if execute_immediately else "deferred"
    })
    
    # 8. 최종 주문 발송 (실행 모드인 경우)
    if execute_immediately:
        order_card["execution_status"] = _execute_finalize(
            ticker, order_card.get("order", {}), user_id, account_type, curr_price
        )
    else:
        order_card["execution_status"] = "planned" if order_card.get("order", {}).get("action") in ["buy", "sell"] else "hold"

    logger.info("[%s] 오케스트레이션 완료 - Status=%s", ticker, order_card.get("execution_status"))
    return order_card


def _execute_finalize(ticker: str, order: Dict[str, Any], user_id: int | None, account_type: str, curr_price: Decimal) -> str:
    """내부 함수: 최종 주문 통신 수행"""
    action = order.get("action", "hold").lower()
    if action not in ["buy", "sell"]:
        return "hold"
        
    quantity = int(order.get("quantity") or 0)
    if quantity <= 0:
        return "skipped (zero quantity)"
        
    price = int(order.get("price") or int(curr_price))
    logger.debug(f"[{ticker}] {action.upper()} 주문 실행: {quantity}주 @ {price}원")
    
    success = execute_order(
        ticker, action, price, quantity, user_id=user_id, account_type=account_type
    )
    return "success" if success else "failed"
