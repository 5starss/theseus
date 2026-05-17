import argparse
import csv
import glob
import json
import logging
import os
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from decimal import Decimal
from pathlib import Path
from typing import Any, Dict, List, Optional

import pandas as pd
from dotenv import load_dotenv

from app.news.agent import NewsReporterAgent
from app.news.sources import convert_news_items_to_documents
from app.quant.agent import QuantAnalysisAgent
from app.quant.feature_engineer import IntradayFeatureEngineer
from app.quant.pipeline import build_state_from_feature_row
from app.quant.sources import load_ohlcv_from_csv
from app.shared.agents.historical_comparison_agent import HistoricalComparisonAgent
from app.shared.agents.judge_agent import JudgeAgent
from app.shared.agents.rebuttal_agent import RebuttalAgent
from app.shared.agents.risk_review_agent import RiskReviewAgent
from app.shared.rag.vector_db import NewsVectorDB
from app.shared.schemas import Document
from app.trading.account_service import apply_account_constraints, build_account_summary, cap_buy_quantity
from app.trading.constants import DEFAULT_REBUTTAL_SCORE_GAP_THRESHOLD
from app.trading.decision_review_store import build_decision_review, save_decision_review
from app.trading.decision_store import build_decision_trace, save_decision_trace
from app.trading.strategy_service import build_strategy_profile

load_dotenv()

logger = logging.getLogger("simulate_agent_replay")


@dataclass
class PositionState:
    quantity: int = 0
    available_quantity: int = 0
    average_price: int = 0
    company_name: str = ""


@dataclass
class SimulationAccount:
    cash: int
    positions: Dict[str, PositionState] = field(default_factory=dict)

    def holding_payload(self, ticker: str) -> Dict[str, Any]:
        position = self.positions.get(ticker) or PositionState(company_name=ticker)
        return {
            "quantity": position.quantity,
            "available_quantity": position.available_quantity,
            "average_price": position.average_price,
            "company_name": position.company_name or ticker,
        }

    def apply_fill(self, *, ticker: str, action: str, quantity: int, price: int) -> None:
        position = self.positions.setdefault(ticker, PositionState(company_name=ticker))

        if action == "buy":
            total_cost = position.average_price * position.quantity + price * quantity
            new_qty = position.quantity + quantity
            position.quantity = new_qty
            position.available_quantity = new_qty
            position.average_price = int(total_cost / new_qty) if new_qty > 0 else 0
            self.cash -= price * quantity
            return

        sell_qty = min(quantity, position.available_quantity)
        position.quantity -= sell_qty
        position.available_quantity -= sell_qty
        if position.quantity <= 0:
            position.quantity = 0
            position.available_quantity = 0
            position.average_price = 0
        self.cash += price * sell_qty


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="히스토리컬 멀티 에이전트 전략 replay 시뮬레이터")
    parser.add_argument("--tickers", default="005930", help="쉼표 구분 종목 코드 목록")
    parser.add_argument("--start-date", required=True, help="시뮬레이션 시작일 (YYYY-MM-DD)")
    parser.add_argument("--end-date", required=True, help="시뮬레이션 종료일 (YYYY-MM-DD)")
    parser.add_argument("--news-dir", required=True, help="히스토리컬 뉴스 JSON 디렉터리")
    parser.add_argument("--quant-data-dir", default="storage/quant/data_cybos", help="1분봉 CSV 디렉터리")
    parser.add_argument("--output-dir", default="backend/ai-server/storage/sim", help="시뮬레이션 결과 디렉터리")
    parser.add_argument("--initial-cash", type=int, default=5000000, help="초기 현금")
    parser.add_argument("--invest-style", default="SHORT", choices=["LONG", "SHORT"], help="에이전트 투자 스타일")
    parser.add_argument("--user-investment-style", default="AGGRESSIVE", help="사용자 투자 성향")
    parser.add_argument("--strategy-slot", default="daily", choices=["daily", "morning", "afternoon"], help="시뮬레이션 전략 슬롯")
    parser.add_argument("--max-news", type=int, default=40, help="일자별 최대 뉴스 수")
    parser.add_argument("--horizon-minutes", type=int, default=5, help="퀀트 feature horizon")
    parser.add_argument("--feature-profile", default="mtf", help="퀀트 feature profile")
    parser.add_argument("--score-gap-threshold", type=int, default=DEFAULT_REBUTTAL_SCORE_GAP_THRESHOLD)
    parser.add_argument("--log-level", default="INFO", help="로그 레벨")
    args = parser.parse_args()
    if args.output_dir == "backend/ai-server/storage/sim" and Path.cwd().name == "ai-server":
        args.output_dir = "storage/sim"
    return args


def _normalize_generic_news_docs(ticker: str, items: List[Dict[str, Any]]) -> List[Document]:
    docs: List[Document] = []
    for idx, item in enumerate(items):
        title = str(item.get("title") or item.get("headline") or "").strip()
        body = str(item.get("body") or item.get("description") or title).strip()
        if not title and not body:
            continue
        published_at = str(item.get("published_at") or item.get("publishedAt") or item.get("date") or "")
        docs.append(
            Document(
                id=str(item.get("id") or f"SIM_{ticker}_{idx}"),
                ticker=ticker,
                source=str(item.get("source") or "SIM_NEWS"),
                published_at=published_at or datetime.now().isoformat(),
                title=title or body[:80],
                body=body,
                url=str(item.get("url") or ""),
                source_rank=float(item.get("source_rank") or 1.0),
            )
        )
    return docs


def load_news_documents(news_dir: str, ticker: str, base_date: date, max_news: int) -> List[Document]:
    base_variants = [base_date.strftime("%Y%m%d"), base_date.strftime("%Y-%m-%d")]
    candidates: List[str] = []
    for day_token in base_variants:
        patterns = [
            os.path.join(news_dir, "**", f"*{ticker}*{day_token}*.json"),
            os.path.join(news_dir, "**", f"*{day_token}*{ticker}*.json"),
            os.path.join(news_dir, day_token, f"*{ticker}*.json"),
            os.path.join(news_dir, ticker, f"*{day_token}*.json"),
        ]
        for pattern in patterns:
            candidates.extend(glob.glob(pattern, recursive=True))

    if not candidates:
        return []

    news_path = sorted(set(candidates))[0]
    with open(news_path, "r", encoding="utf-8") as fp:
        payload = json.load(fp)

    if isinstance(payload, dict) and isinstance(payload.get("sources", {}).get("news"), list):
        docs = convert_news_items_to_documents(ticker=ticker, news_items=payload["sources"]["news"])
        return docs[:max_news]

    if isinstance(payload, list):
        return _normalize_generic_news_docs(ticker, payload)[:max_news]

    if isinstance(payload, dict) and isinstance(payload.get("news"), list):
        return _normalize_generic_news_docs(ticker, payload["news"])[:max_news]

    return []


def build_sim_collection_name(ticker: str, trade_date: date) -> str:
    return f"sim_{ticker}_{trade_date.strftime('%Y%m%d')}"


def prepare_rag_collection(collection_name: str, news_docs: List[Document]) -> int:
    vdb = NewsVectorDB(collection_name=collection_name)
    vdb.delete_collection()
    return vdb.add_documents(news_docs)


def retrieve_sim_news(collection_name: str, query: str, top_k: int = 5) -> List[Any]:
    vdb = NewsVectorDB(collection_name=collection_name)
    return vdb.hybrid_query(query_text=query, k=top_k)


def build_sim_signal_weights(strategy_slot: str) -> Dict[str, int]:
    if strategy_slot == "morning":
        return {"news_weight": 60, "quant_weight": 40}
    if strategy_slot == "afternoon":
        return {"news_weight": 40, "quant_weight": 60}
    return {"news_weight": 50, "quant_weight": 50}


def run_rebuttal_agent(
    ticker: str,
    news_card: Dict[str, Any],
    quant_card: Dict[str, Any],
    score_gap_threshold: int,
) -> Dict[str, Any]:
    def safe_score(card: Dict[str, Any]) -> int:
        try:
            return int(card.get("score", 0))
        except Exception:
            return 0

    news_score = safe_score(news_card)
    quant_score = safe_score(quant_card)
    score_gap = abs(news_score - quant_score)
    if score_gap < score_gap_threshold:
        return {
            "triggered": False,
            "rebuttal_round": 0,
            "score_gap": score_gap,
            "score_gap_threshold": score_gap_threshold,
            "news_score": news_score,
            "quant_score": quant_score,
        }

    try:
        rebuttal = RebuttalAgent().generate_rebuttal(news_card, quant_card)
        return {
            "triggered": True,
            "rebuttal_round": 1,
            "score_gap": score_gap,
            "score_gap_threshold": score_gap_threshold,
            "news_score": news_score,
            "quant_score": quant_score,
            "rebuttal": rebuttal,
        }
    except Exception as exc:
        logger.warning("[%s] rebuttal 생성 실패: %s", ticker, exc)
        return {
            "triggered": False,
            "rebuttal_round": 0,
            "score_gap": score_gap,
            "score_gap_threshold": score_gap_threshold,
            "news_score": news_score,
            "quant_score": quant_score,
            "error": str(exc),
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


def build_order_card(
    *,
    ticker: str,
    trade_date: date,
    base_date: date,
    previous_close: int,
    account: SimulationAccount,
    user_id: int,
    strategy_slot: str,
    strategy_profile: Dict[str, str],
    collection_name: str,
    feature_row: Dict[str, Any],
    score_gap_threshold: int,
    news_agent: NewsReporterAgent,
    quant_agent: QuantAnalysisAgent,
    judge_agent: JudgeAgent,
    historical_agent: HistoricalComparisonAgent,
    risk_review_agent: RiskReviewAgent,
) -> Dict[str, Any]:
    news_docs = retrieve_sim_news(collection_name=collection_name, query=strategy_profile["news_question"], top_k=5)
    community_docs: List[Any] = []
    current_holding = account.holding_payload(ticker)
    news_card = news_agent.generate_analysis_card(
        ticker=ticker,
        question=strategy_profile["news_question"],
        news_docs=news_docs,
        community_docs=community_docs,
    )
    news_card["timestamp"] = datetime.combine(trade_date, datetime.min.time()).replace(
        hour=8,
        minute=5,
    ).isoformat()
    quant_state = build_state_from_feature_row(feature_row, ticker=ticker)
    quant_card = quant_agent.generate_analysis_card(ticker=ticker, quant_evidence=quant_state)
    rebuttal_result = run_rebuttal_agent(
        ticker=ticker,
        news_card=news_card,
        quant_card=quant_card,
        score_gap_threshold=score_gap_threshold,
    )
    signal_confidence = _resolve_signal_confidence(news_card, quant_card, quant_state)
    historical_comparison = historical_agent.compare(
        ticker=ticker,
        user_id=user_id,
        strategy_slot=strategy_slot,
        news_card=news_card,
        quant_card=quant_card,
        quant_state=quant_state,
        as_of_date=trade_date.isoformat(),
        base_date=base_date.isoformat(),
    )
    max_buy_qty, _ = cap_buy_quantity(
        requested_qty=999999,
        available_cash=account.cash,
        current_holding=current_holding,
        effective_price=previous_close,
        user_investment_style=strategy_profile["user_investment_style"],
        signal_confidence=signal_confidence,
    )
    max_sell_qty = int(current_holding.get("available_quantity") or 0)

    judge_payload = {
        "ticker": ticker,
        "current_price": previous_close,
        "available_cash": account.cash,
        "current_holding": current_holding,
        "max_allowed_buy_quantity": max_buy_qty,
        "max_allowed_sell_quantity": max_sell_qty,
        "signal_confidence": signal_confidence,
        "risk_type": strategy_profile["risk_type"],
        "invest_style": strategy_profile["invest_style"],
        "user_investment_style": strategy_profile["user_investment_style"],
        "strategy_prompt": strategy_profile["strategy_prompt"],
        "strategy_slot": strategy_slot,
        "signal_weights": build_sim_signal_weights(strategy_slot),
        "news_card": news_card,
        "quant_card": quant_card,
        "quant_state_summary": quant_state,
        "rebuttal": rebuttal_result,
        "historical_comparison": historical_comparison,
    }
    order_card = judge_agent.generate_order_card(judge_payload)
    order_card, risk_review = risk_review_agent.review_order(
        order_card=order_card,
        current_holding=current_holding,
        quant_state=quant_state,
        historical_comparison=historical_comparison,
        signal_confidence=signal_confidence,
        system_error=False,
    )
    order_card = apply_account_constraints(
        order_card,
        available_cash=account.cash,
        current_holding=current_holding,
        current_price=Decimal(str(previous_close)),
        user_investment_style=strategy_profile["user_investment_style"],
        signal_confidence=signal_confidence,
    )
    order_card.update(
        {
            "account_snapshot": build_account_summary(
                available_cash=account.cash,
                current_holding=current_holding,
                account_type="SIM",
                user_id=user_id,
                strategy_profile=strategy_profile,
                strategy_slot=strategy_slot,
            ),
            "rebuttal": rebuttal_result,
            "historical_comparison": historical_comparison,
            "risk_review": risk_review,
            "execution_mode": "simulated",
            "execution_status": "planned" if order_card.get("order", {}).get("action") in {"buy", "sell"} else "hold",
            "news_doc_count": len(news_docs),
            "community_doc_count": len(community_docs),
            "_simulation_decision_state": {
                "trade_date": trade_date.isoformat(),
                "base_date": base_date.isoformat(),
                "ticker": ticker,
                "user_id": user_id,
                "account_type": "SIM",
                "invest_style": strategy_profile["invest_style"],
                "user_investment_style": strategy_profile["user_investment_style"],
                "resolved_slot": strategy_slot,
                "strategy_slot": strategy_slot,
                "workflow": "simulation_replay",
                "workflow_version": "sim_v1",
                "news_card": news_card,
                "quant_card": quant_card,
                "quant_state": quant_state,
                "rebuttal_result": rebuttal_result,
                "historical_comparison": historical_comparison,
                "signal_confidence": signal_confidence,
                "judge_payload": judge_payload,
                "risk_review": risk_review,
            },
        }
    )
    return order_card


def simulate_fill(
    *,
    ticker: str,
    trade_date: date,
    intraday_df: pd.DataFrame,
    order_card: Dict[str, Any],
    account: SimulationAccount,
) -> Dict[str, Any]:
    order = order_card.get("order", {})
    action = str(order.get("action") or "hold").lower()
    order_type = str(order.get("order_type") or "limit").lower()
    quantity = int(order.get("quantity") or 0)
    limit_price = int(order.get("price") or 0)

    result = {
        "trade_date": trade_date.isoformat(),
        "ticker": ticker,
        "action": action,
        "requested_quantity": quantity,
        "limit_price": limit_price,
        "status": "not_triggered",
        "executed_at": None,
        "executed_price": None,
        "executed_quantity": 0,
        "cash_after": account.cash,
        "holding_after": account.holding_payload(ticker),
    }

    if action not in {"buy", "sell"} or quantity <= 0:
        result["status"] = "skipped"
        return result

    if order_type == "market":
        for row in intraday_df.itertuples(index=False):
            current_price = int(getattr(row, "close"))
            if current_price <= 0:
                continue

            executable_qty = quantity
            if action == "buy":
                executable_qty = min(quantity, account.cash // current_price if current_price > 0 else 0)
            else:
                executable_qty = min(quantity, account.holding_payload(ticker)["available_quantity"])

            if executable_qty <= 0:
                result["status"] = "blocked"
                return result

            account.apply_fill(ticker=ticker, action=action, quantity=executable_qty, price=current_price)
            result.update(
                {
                    "status": "filled",
                    "executed_at": pd.Timestamp(getattr(row, "ts")).isoformat(),
                    "executed_price": current_price,
                    "executed_quantity": executable_qty,
                    "cash_after": account.cash,
                    "holding_after": account.holding_payload(ticker),
                }
            )
            return result

        result["status"] = "skipped"
        return result

    if limit_price <= 0:
        result["status"] = "skipped"
        return result

    for row in intraday_df.itertuples(index=False):
        current_price = int(getattr(row, "close"))
        should_fill = (action == "buy" and current_price <= limit_price) or (
            action == "sell" and current_price >= limit_price
        )
        if not should_fill:
            continue

        executable_qty = quantity
        if action == "buy":
            executable_qty = min(quantity, account.cash // current_price if current_price > 0 else 0)
        else:
            executable_qty = min(quantity, account.holding_payload(ticker)["available_quantity"])

        if executable_qty <= 0:
            result["status"] = "blocked"
            return result

        account.apply_fill(ticker=ticker, action=action, quantity=executable_qty, price=current_price)
        result.update(
            {
                "status": "filled",
                "executed_at": pd.Timestamp(getattr(row, "ts")).isoformat(),
                "executed_price": current_price,
                "executed_quantity": executable_qty,
                "cash_after": account.cash,
                "holding_after": account.holding_payload(ticker),
            }
        )
        return result

    return result


def build_market_outcome(fill_result: Dict[str, Any], intraday_df: pd.DataFrame) -> Dict[str, Any]:
    status = str(fill_result.get("status") or "")
    action = str(fill_result.get("action") or "hold").lower()
    executed_price = int(fill_result.get("executed_price") or 0)
    executed_at = fill_result.get("executed_at")

    if status != "filled" or executed_price <= 0 or intraday_df.empty:
        if action == "hold" and not intraday_df.empty:
            replay_df = intraday_df.copy()
            replay_df["ts"] = pd.to_datetime(replay_df["ts"])
            start_price = int(replay_df.iloc[0].get("open") or replay_df.iloc[0].get("close") or 0)
            final_price = int(replay_df.iloc[-1].get("close") or 0)
            high_price = int(replay_df["high"].max()) if "high" in replay_df else final_price
            low_price = int(replay_df["low"].min()) if "low" in replay_df else final_price
            opportunity_pct = ((final_price / start_price) - 1.0) * 100 if start_price > 0 else None
            upside_pct = ((high_price / start_price) - 1.0) * 100 if start_price > 0 else None
            downside_pct = ((low_price / start_price) - 1.0) * 100 if start_price > 0 else None
            return {
                "outcome": "NOT_EXECUTED",
                "execution_status": status,
                "pnl_pct": None,
                "max_drawdown_pct": None,
                "holding_minutes": None,
                "start_price": start_price,
                "final_price": final_price,
                "opportunity_pct": round(opportunity_pct, 4) if opportunity_pct is not None else None,
                "upside_pct": round(upside_pct, 4) if upside_pct is not None else None,
                "downside_pct": round(downside_pct, 4) if downside_pct is not None else None,
            }
        return {
            "outcome": "NOT_EXECUTED",
            "execution_status": status,
            "pnl_pct": None,
            "max_drawdown_pct": None,
            "holding_minutes": None,
        }

    replay_df = intraday_df.copy()
    replay_df["ts"] = pd.to_datetime(replay_df["ts"])
    if executed_at:
        replay_df = replay_df[replay_df["ts"] >= pd.Timestamp(executed_at)].copy()
    if replay_df.empty:
        replay_df = intraday_df.copy()

    final_price = int(replay_df.iloc[-1]["close"])
    if action == "buy":
        pnl_pct = ((final_price / executed_price) - 1.0) * 100 if executed_price > 0 else None
        min_price = int(replay_df["low"].min()) if "low" in replay_df else int(replay_df["close"].min())
        max_drawdown_pct = ((min_price / executed_price) - 1.0) * 100 if executed_price > 0 else None
        favorable_move_pct = (
            ((int(replay_df["high"].max()) / executed_price) - 1.0) * 100
            if executed_price > 0 and "high" in replay_df
            else None
        )
    elif action == "sell":
        pnl_pct = ((executed_price / final_price) - 1.0) * 100 if final_price > 0 else None
        max_price = int(replay_df["high"].max()) if "high" in replay_df else int(replay_df["close"].max())
        max_drawdown_pct = ((executed_price / max_price) - 1.0) * 100 if max_price > 0 else None
        min_price = int(replay_df["low"].min()) if "low" in replay_df else int(replay_df["close"].min())
        favorable_move_pct = ((executed_price / min_price) - 1.0) * 100 if min_price > 0 else None
    else:
        pnl_pct = None
        max_drawdown_pct = None
        favorable_move_pct = None

    if pnl_pct is None:
        outcome = "UNKNOWN"
    elif pnl_pct > 0.1:
        outcome = "WIN"
    elif pnl_pct < -0.1:
        outcome = "LOSS"
    else:
        outcome = "FLAT"

    start_ts = pd.Timestamp(executed_at) if executed_at else replay_df.iloc[0]["ts"]
    end_ts = replay_df.iloc[-1]["ts"]
    holding_minutes = max(0, int((end_ts - start_ts).total_seconds() // 60))

    return {
        "outcome": outcome,
        "execution_status": status,
        "entry_price": executed_price,
        "final_price": final_price,
        "pnl_pct": round(pnl_pct, 4) if pnl_pct is not None else None,
        "max_drawdown_pct": round(max_drawdown_pct, 4) if max_drawdown_pct is not None else None,
        "favorable_move_pct": round(favorable_move_pct, 4) if favorable_move_pct is not None else None,
        "holding_minutes": holding_minutes,
    }


def build_sim_review_tags(
    *,
    order_card: Dict[str, Any],
    fill_result: Dict[str, Any],
    market_outcome: Dict[str, Any],
) -> List[str]:
    tags: List[str] = []
    order = order_card.get("order") if isinstance(order_card.get("order"), dict) else {}
    risk_review = order_card.get("risk_review") if isinstance(order_card.get("risk_review"), dict) else {}
    historical = (
        order_card.get("historical_comparison")
        if isinstance(order_card.get("historical_comparison"), dict)
        else {}
    )
    action = str(fill_result.get("action") or order.get("action") or "hold").lower()
    status = str(fill_result.get("status") or "").lower()
    outcome = str(market_outcome.get("outcome") or "").upper()

    if status != "filled":
        tags.append("not_executed")
    if outcome == "WIN":
        tags.append("profitable_decision")
    elif outcome == "LOSS":
        tags.append("loss_after_entry")
    elif outcome == "FLAT":
        tags.append("flat_result")

    try:
        pnl_pct = float(market_outcome.get("pnl_pct")) if market_outcome.get("pnl_pct") is not None else None
    except Exception:
        pnl_pct = None
    try:
        max_drawdown_pct = (
            float(market_outcome.get("max_drawdown_pct"))
            if market_outcome.get("max_drawdown_pct") is not None
            else None
        )
    except Exception:
        max_drawdown_pct = None

    if action == "buy" and outcome == "WIN" and pnl_pct is not None and pnl_pct >= 2.0:
        tags.append("good_buy_entry")
        if str(risk_review.get("decision") or "").upper() == "REDUCE_SIZE":
            tags.append("under_sized_winner")
        if str(historical.get("recommendation") or "").upper() == "BUY_LESS":
            tags.append("buy_less_on_winner")
    if action == "buy" and outcome == "LOSS":
        tags.append("bad_buy_entry")
    if action == "sell" and outcome == "WIN":
        tags.append("good_sell_exit")
    if action == "sell" and outcome == "LOSS":
        tags.append("premature_sell")
        tags.append("missed_upside_after_sell")
    if action == "hold" and status != "filled":
        try:
            opportunity_pct = (
                float(market_outcome.get("opportunity_pct"))
                if market_outcome.get("opportunity_pct") is not None
                else None
            )
        except Exception:
            opportunity_pct = None
        if opportunity_pct is not None and opportunity_pct >= 1.5:
            tags.append("missed_upside_after_hold")
        elif opportunity_pct is not None and opportunity_pct <= -1.5:
            tags.append("good_hold")
    if max_drawdown_pct is not None and max_drawdown_pct <= -3.0:
        tags.append("large_adverse_move")

    return list(dict.fromkeys(tags))[:10]


def build_sim_review_lesson(tags: List[str], market_outcome: Dict[str, Any]) -> str:
    tag_set = set(tags)
    if "premature_sell" in tag_set or "missed_upside_after_sell" in tag_set:
        return "Similar sell decisions missed upside; avoid SELL_BIAS unless downside evidence is stronger."
    if "missed_upside_after_hold" in tag_set:
        return "Similar hold decisions missed upside; do not overuse HOLD when entry risk is low and alignment improves."
    if "good_hold" in tag_set:
        return "Similar hold decisions avoided downside; HOLD can be useful when signals are weak."
    if "under_sized_winner" in tag_set or "buy_less_on_winner" in tag_set:
        return "비슷한 강세 결과가 반복되면 BUY_LESS와 수량 축소를 완화할 근거로 사용한다."
    if "bad_buy_entry" in tag_set or "large_adverse_move" in tag_set:
        return "비슷한 진입 위험과 약한 신호에서 손실이 반복되면 신규 매수 수량을 줄이거나 보류한다."
    if "good_sell_exit" in tag_set:
        return "비슷한 조건의 매도 판단이 수익 방어에 도움이 되었는지 다음 판단에서 확인한다."
    if "not_executed" in tag_set:
        return "미체결 케이스는 방향성 학습 근거로 약하게 사용하고, 주문 가격 적정성만 참고한다."
    if str(market_outcome.get("outcome") or "").upper() == "WIN":
        return "비슷한 신호 조합에서 수익이 났으므로 방향성 근거로 재검토한다."
    return "simulation outcome recorded for future historical comparison"


def persist_sim_decision_artifacts(
    *,
    order_card: Dict[str, Any],
    fill_result: Dict[str, Any],
    intraday_df: pd.DataFrame,
) -> Dict[str, Any]:
    state = dict(order_card.get("_simulation_decision_state") or {})
    if not state:
        return {"decision_trace": None, "decision_review": None}

    order_card["execution_status"] = str(fill_result.get("status") or order_card.get("execution_status") or "")
    trace = build_decision_trace(state=state, order_card=order_card)
    trace_meta = save_decision_trace(trace)
    order_card["decision_trace"] = trace_meta

    market_outcome = build_market_outcome(fill_result, intraday_df)
    mistake_tags = build_sim_review_tags(
        order_card=order_card,
        fill_result=fill_result,
        market_outcome=market_outcome,
    )
    review = build_decision_review(
        decision_trace_id=trace_meta["decision_trace_id"],
        ticker=str(state.get("ticker") or order_card.get("ticker") or ""),
        user_id=state.get("user_id"),
        strategy_slot=state.get("resolved_slot") or state.get("strategy_slot"),
        outcome=market_outcome["outcome"],
        pnl_pct=market_outcome.get("pnl_pct"),
        max_drawdown_pct=market_outcome.get("max_drawdown_pct"),
        holding_minutes=market_outcome.get("holding_minutes"),
        execution_status=market_outcome.get("execution_status"),
        mistake_tags=mistake_tags,
        lesson=build_sim_review_lesson(mistake_tags, market_outcome),
        evaluator="simulate_agent_replay",
        extra={
            "market_outcome": market_outcome,
            "fill_result": fill_result,
        },
    )
    review_meta = save_decision_review(review)
    order_card["decision_review"] = review_meta
    return {"decision_trace": trace_meta, "decision_review": review_meta, "market_outcome": market_outcome}


def ensure_output_paths(output_dir: str, run_name: str) -> Dict[str, Path]:
    run_dir = Path(output_dir) / run_name
    run_dir.mkdir(parents=True, exist_ok=True)
    return {
        "run_dir": run_dir,
        "decisions_jsonl": run_dir / "decisions.jsonl",
        "fills_csv": run_dir / "fills.csv",
        "daily_summary_csv": run_dir / "daily_summary.csv",
        "position_timeline_csv": run_dir / "position_timeline.csv",
        "events_jsonl": run_dir / "events.jsonl",
        "summary_json": run_dir / "summary.json",
    }


def write_event(fp, *, ts: datetime, event_type: str, payload: Dict[str, Any]) -> None:
    fp.write(
        json.dumps(
            {
                "ts": ts.isoformat(),
                "event_type": event_type,
                "payload": payload,
            },
            ensure_ascii=False,
        )
        + "\n"
    )


def build_daily_summary_rows(fills: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    grouped: Dict[tuple[str, str], Dict[str, Any]] = {}
    for fill in fills:
        key = (str(fill.get("trade_date")), str(fill.get("ticker")))
        row = grouped.setdefault(
            key,
            {
                "trade_date": key[0],
                "ticker": key[1],
                "buy_count": 0,
                "sell_count": 0,
                "filled_buy_qty": 0,
                "filled_sell_qty": 0,
                "filled_buy_amount": 0,
                "filled_sell_amount": 0,
                "ending_cash": fill.get("cash_after"),
                "last_status": fill.get("status"),
            },
        )
        row["ending_cash"] = fill.get("cash_after")
        row["last_status"] = fill.get("status")
        if fill.get("status") != "filled":
            continue

        executed_qty = int(fill.get("executed_quantity") or 0)
        executed_price = int(fill.get("executed_price") or 0)
        action = str(fill.get("action") or "").lower()
        if action == "buy":
            row["buy_count"] += 1
            row["filled_buy_qty"] += executed_qty
            row["filled_buy_amount"] += executed_qty * executed_price
        elif action == "sell":
            row["sell_count"] += 1
            row["filled_sell_qty"] += executed_qty
            row["filled_sell_amount"] += executed_qty * executed_price

    return [grouped[key] for key in sorted(grouped.keys())]


def build_position_timeline_rows(
    *,
    fills: List[Dict[str, Any]],
    final_positions: Dict[str, PositionState],
) -> List[Dict[str, Any]]:
    timeline: List[Dict[str, Any]] = []
    latest_by_ticker: Dict[str, Dict[str, Any]] = {}

    for fill in fills:
        ticker = str(fill.get("ticker"))
        holding_after = fill.get("holding_after") or {}
        latest_by_ticker[ticker] = {
            "trade_date": fill.get("trade_date"),
            "ticker": ticker,
            "status": fill.get("status"),
            "action": fill.get("action"),
            "executed_at": fill.get("executed_at"),
            "executed_price": fill.get("executed_price"),
            "executed_quantity": fill.get("executed_quantity"),
            "position_quantity": int(holding_after.get("quantity") or 0),
            "available_quantity": int(holding_after.get("available_quantity") or 0),
            "average_price": int(holding_after.get("average_price") or 0),
            "cash_after": fill.get("cash_after"),
        }
        timeline.append(latest_by_ticker[ticker])

    for ticker, position in sorted(final_positions.items()):
        if ticker in latest_by_ticker:
            continue
        timeline.append(
            {
                "trade_date": "",
                "ticker": ticker,
                "status": "carried",
                "action": "",
                "executed_at": "",
                "executed_price": "",
                "executed_quantity": 0,
                "position_quantity": position.quantity,
                "available_quantity": position.available_quantity,
                "average_price": position.average_price,
                "cash_after": "",
            }
        )

    return timeline


def main() -> None:
    args = parse_args()
    logging.basicConfig(level=getattr(logging, str(args.log_level).upper(), logging.INFO))

    tickers = [ticker.strip() for ticker in args.tickers.split(",") if ticker.strip()]
    start_date = date.fromisoformat(args.start_date)
    end_date = date.fromisoformat(args.end_date)
    if start_date > end_date:
        raise ValueError("start-date must be <= end-date")

    strategy_profile = build_strategy_profile(args.invest_style, args.user_investment_style)
    feature_engineer = IntradayFeatureEngineer(
        horizon_minutes=args.horizon_minutes,
        feature_profile=args.feature_profile,
        recent_window_days=None,
    )
    news_agent = NewsReporterAgent()
    quant_agent = QuantAnalysisAgent()
    judge_agent = JudgeAgent()
    historical_agent = HistoricalComparisonAgent()
    risk_review_agent = RiskReviewAgent()

    account = SimulationAccount(cash=args.initial_cash)
    run_name = f"sim_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    paths = ensure_output_paths(args.output_dir, run_name)
    fills: List[Dict[str, Any]] = []
    decision_count = 0

    with open(paths["decisions_jsonl"], "w", encoding="utf-8") as decisions_fp:
        fill_fieldnames = [
            "trade_date",
            "ticker",
            "action",
            "requested_quantity",
            "limit_price",
            "status",
            "executed_at",
            "executed_price",
            "executed_quantity",
            "cash_after",
            "decision_trace_id",
            "decision_review_id",
        ]
        with open(paths["fills_csv"], "w", encoding="utf-8", newline="") as fills_fp:
            with open(paths["events_jsonl"], "w", encoding="utf-8") as events_fp:
                writer = csv.DictWriter(fills_fp, fieldnames=fill_fieldnames)
                writer.writeheader()

                for ticker in tickers:
                    logger.info("[%s] 1분봉 로드 시작", ticker)
                    ohlcv_df = load_ohlcv_from_csv(ticker=ticker, data_dir=args.quant_data_dir)
                    ohlcv_df["ts"] = pd.to_datetime(ohlcv_df["ts"])
                    ohlcv_df = ohlcv_df.sort_values("ts").reset_index(drop=True)
                    ohlcv_df = ohlcv_df[
                        (ohlcv_df["ts"].dt.date >= start_date - timedelta(days=10))
                        & (ohlcv_df["ts"].dt.date <= end_date)
                    ].copy()

                    trade_dates = sorted(day for day in ohlcv_df["ts"].dt.date.unique() if start_date <= day <= end_date)
                    for idx, trade_date in enumerate(trade_dates):
                        if idx == 0:
                            logger.info("[%s] %s는 이전 거래일 데이터가 없어 스킵", ticker, trade_date)
                            continue

                        base_date = trade_dates[idx - 1]
                        history_df = ohlcv_df[ohlcv_df["ts"].dt.date <= base_date].copy()
                        intraday_df = ohlcv_df[ohlcv_df["ts"].dt.date == trade_date].copy()
                        if history_df.empty or intraday_df.empty:
                            continue

                        feature_batch_ts = datetime.combine(base_date, datetime.min.time()).replace(hour=17)
                        write_event(
                            events_fp,
                            ts=feature_batch_ts,
                            event_type="feature_batch_start",
                            payload={"ticker": ticker, "base_date": base_date.isoformat()},
                        )
                        feat_df = feature_engineer.build(
                            history_df[["ts", "open", "high", "low", "close", "volume"]].copy()
                        )
                        if feat_df.empty:
                            logger.warning("[%s] %s feature row가 없어 스킵", ticker, trade_date)
                            write_event(
                                events_fp,
                                ts=feature_batch_ts,
                                event_type="feature_batch_skipped",
                                payload={"ticker": ticker, "trade_date": trade_date.isoformat(), "reason": "empty_feature_df"},
                            )
                            continue

                        previous_close = int(history_df.iloc[-1]["close"])
                        feature_row = feat_df.iloc[-1].to_dict()
                        write_event(
                            events_fp,
                            ts=feature_batch_ts,
                            event_type="feature_batch_completed",
                            payload={
                                "ticker": ticker,
                                "base_date": base_date.isoformat(),
                                "feature_rows": int(len(feat_df)),
                                "previous_close": previous_close,
                            },
                        )

                        news_batch_ts = datetime.combine(trade_date, datetime.min.time()).replace(hour=8)
                        write_event(
                            events_fp,
                            ts=news_batch_ts,
                            event_type="news_batch_start",
                            payload={"ticker": ticker, "trade_date": trade_date.isoformat()},
                        )
                        source_news_docs = load_news_documents(args.news_dir, ticker, trade_date, args.max_news)
                        collection_name = build_sim_collection_name(ticker, trade_date)
                        try:
                            indexed_count = prepare_rag_collection(collection_name, source_news_docs)
                            write_event(
                                events_fp,
                                ts=news_batch_ts,
                                event_type="news_batch_completed",
                                payload={
                                    "ticker": ticker,
                                    "trade_date": trade_date.isoformat(),
                                    "news_doc_count": len(source_news_docs),
                                    "indexed_count": indexed_count,
                                    "collection_name": collection_name,
                                },
                            )

                            strategy_ts = datetime.combine(trade_date, datetime.min.time()).replace(hour=8, minute=5)
                            order_card = build_order_card(
                                ticker=ticker,
                                trade_date=trade_date,
                                base_date=base_date,
                                previous_close=previous_close,
                                account=account,
                                user_id=0,
                            strategy_slot=args.strategy_slot,
                                strategy_profile=strategy_profile,
                                collection_name=collection_name,
                                feature_row=feature_row,
                                score_gap_threshold=args.score_gap_threshold,
                                news_agent=news_agent,
                                quant_agent=quant_agent,
                                judge_agent=judge_agent,
                                historical_agent=historical_agent,
                                risk_review_agent=risk_review_agent,
                            )
                            write_event(
                                events_fp,
                                ts=strategy_ts,
                                event_type="strategy_generated",
                                payload={
                                    "ticker": ticker,
                                    "trade_date": trade_date.isoformat(),
                                    "action": order_card.get("order", {}).get("action"),
                                    "quantity": order_card.get("order", {}).get("quantity"),
                                    "price": order_card.get("order", {}).get("price"),
                                    "news_doc_count": len(source_news_docs),
                                    "collection_name": collection_name,
                                },
                            )
                            market_open_ts = datetime.combine(trade_date, datetime.min.time()).replace(hour=9)
                            write_event(
                                events_fp,
                                ts=market_open_ts,
                                event_type="market_replay_start",
                                payload={
                                    "ticker": ticker,
                                    "trade_date": trade_date.isoformat(),
                                    "bars": int(len(intraday_df)),
                                },
                            )

                            fill_result = simulate_fill(
                                ticker=ticker,
                                trade_date=trade_date,
                                intraday_df=intraday_df,
                                order_card=order_card,
                                account=account,
                            )
                            decision_artifacts = persist_sim_decision_artifacts(
                                order_card=order_card,
                                fill_result=fill_result,
                                intraday_df=intraday_df,
                            )
                            fill_result["decision_trace_id"] = (
                                decision_artifacts.get("decision_trace") or {}
                            ).get("decision_trace_id")
                            fill_result["decision_review_id"] = (
                                decision_artifacts.get("decision_review") or {}
                            ).get("review_id")
                            decisions_fp.write(
                                json.dumps(
                                    {
                                        "trade_date": trade_date.isoformat(),
                                        "base_date": base_date.isoformat(),
                                        "ticker": ticker,
                                        "previous_close": previous_close,
                                        "news_doc_count": len(source_news_docs),
                                        "collection_name": collection_name,
                                        "decision_trace": decision_artifacts.get("decision_trace"),
                                        "decision_review": decision_artifacts.get("decision_review"),
                                        "market_outcome": decision_artifacts.get("market_outcome"),
                                        "order_card": {
                                            key: value
                                            for key, value in order_card.items()
                                            if key != "_simulation_decision_state"
                                        },
                                    },
                                    ensure_ascii=False,
                                )
                                + "\n"
                            )
                            decision_count += 1
                            fills.append(fill_result)
                            writer.writerow({key: fill_result.get(key) for key in fill_fieldnames})
                            write_event(
                                events_fp,
                                ts=datetime.combine(trade_date, datetime.min.time()).replace(hour=15, minute=30),
                                event_type="market_replay_completed",
                                payload={
                                    "ticker": ticker,
                                    "trade_date": trade_date.isoformat(),
                                    "fill_status": fill_result.get("status"),
                                    "executed_at": fill_result.get("executed_at"),
                                    "executed_price": fill_result.get("executed_price"),
                                    "executed_quantity": fill_result.get("executed_quantity"),
                                    "cash_after": fill_result.get("cash_after"),
                                },
                            )
                        finally:
                            NewsVectorDB(collection_name=collection_name).delete_collection()

    summary = {
        "run_name": run_name,
        "tickers": tickers,
        "start_date": start_date.isoformat(),
        "end_date": end_date.isoformat(),
        "decision_count": decision_count,
        "fill_count": len([item for item in fills if item.get("status") == "filled"]),
        "ending_cash": account.cash,
        "positions": {
            ticker: {
                "quantity": position.quantity,
                "available_quantity": position.available_quantity,
                "average_price": position.average_price,
            }
            for ticker, position in account.positions.items()
        },
        "artifacts": {name: str(path) for name, path in paths.items()},
    }

    daily_summary_rows = build_daily_summary_rows(fills)
    with open(paths["daily_summary_csv"], "w", encoding="utf-8", newline="") as daily_fp:
        daily_fieldnames = [
            "trade_date",
            "ticker",
            "buy_count",
            "sell_count",
            "filled_buy_qty",
            "filled_sell_qty",
            "filled_buy_amount",
            "filled_sell_amount",
            "ending_cash",
            "last_status",
        ]
        writer = csv.DictWriter(daily_fp, fieldnames=daily_fieldnames)
        writer.writeheader()
        for row in daily_summary_rows:
            writer.writerow(row)

    position_timeline_rows = build_position_timeline_rows(fills=fills, final_positions=account.positions)
    with open(paths["position_timeline_csv"], "w", encoding="utf-8", newline="") as timeline_fp:
        timeline_fieldnames = [
            "trade_date",
            "ticker",
            "status",
            "action",
            "executed_at",
            "executed_price",
            "executed_quantity",
            "position_quantity",
            "available_quantity",
            "average_price",
            "cash_after",
        ]
        writer = csv.DictWriter(timeline_fp, fieldnames=timeline_fieldnames)
        writer.writeheader()
        for row in position_timeline_rows:
            writer.writerow(row)

    with open(paths["summary_json"], "w", encoding="utf-8") as summary_fp:
        json.dump(summary, summary_fp, ensure_ascii=False, indent=2)

    logger.info("시뮬레이션 완료 - decisions=%s fills=%s ending_cash=%s", summary["decision_count"], summary["fill_count"], summary["ending_cash"])
    logger.info("결과 디렉터리: %s", paths["run_dir"])


if __name__ == "__main__":
    main()
