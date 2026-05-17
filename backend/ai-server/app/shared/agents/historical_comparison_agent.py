import json
import os
import re
from datetime import date, timedelta
from typing import Any, Dict

from dotenv import load_dotenv
from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import ChatPromptTemplate
from langchain_openai import ChatOpenAI

from app.trading.decision_query import LocalDecisionHistoryProvider

load_dotenv()


def _load_json_object(text: str) -> Dict[str, Any]:
    try:
        return json.loads(text)
    except Exception:
        match = re.search(r"\{[\s\S]*\}", text)
        if not match:
            raise
        return json.loads(match.group(0))


def _safe_score(card: Dict[str, Any]) -> Any:
    try:
        return float(card.get("score"))
    except Exception:
        return None


def _nested(mapping: Dict[str, Any], *keys: str) -> Any:
    current: Any = mapping
    for key in keys:
        if not isinstance(current, dict):
            return None
        current = current.get(key)
    return current


class HistoricalComparisonAgent:
    """Compares today's analysis against prior decision traces before final judging."""

    def __init__(self, history_provider: Any = None):
        api_key = os.getenv("GMS_API_KEY")
        if not api_key:
            raise ValueError("GMS_API_KEY is required for HistoricalComparisonAgent.")

        self.history_provider = history_provider or LocalDecisionHistoryProvider()
        self.llm = ChatOpenAI(
            model=os.getenv("HISTORICAL_COMPARISON_MODEL", "gpt-5-mini"),
            openai_api_key=api_key,
            openai_api_base="https://gms.ssafy.io/gmsapi/api.openai.com/v1",
        )
        self.prompt = ChatPromptTemplate.from_messages(
            [
                (
                    "system",
                    """You are a trading memory comparison agent.
Compare today's news/quant setup with prior decision traces.
Use only the provided historical cases. If realized outcome/review is absent, say so and rely on execution/risk history cautiously.

Return ONLY a JSON object with this shape:
{{
  "schema": "historical_comparison_v1",
  "similar_cases_count": 0,
  "historical_bias": "bullish|caution|bearish|neutral|insufficient_history",
  "recommendation": "BUY_MORE|BUY_NORMAL|BUY_LESS|HOLD|SELL_BIAS|INSUFFICIENT_HISTORY",
  "confidence": 0.0,
  "position_size_multiplier": 1.0,
  "reasons": ["short reason"],
  "cases_used": ["decision_trace_id"]
}}

Rules:
- position_size_multiplier must be between 0.0 and 1.5.
- If there are fewer than 2 useful similar cases, use INSUFFICIENT_HISTORY.
- If similar cases were frequently risk-blocked or weakly executed, prefer BUY_LESS or HOLD.
- If similar reviewed winners repeatedly have under_sized_winner or sold_too_early tags, mention it in reasons, but do not upgrade sizing unless losses and drawdowns are clearly controlled.
- If similar reviewed losers have high entry risk, weak confidence, or loss_after_entry tags, prefer BUY_LESS or HOLD.
- Treat NOT_EXECUTED cases as weaker evidence than WIN/LOSS cases.
- Use Historical Search Result.summary as the authoritative count/statistics source when it is present.
- If reviewed winners and losers are balanced, prefer BUY_LESS or HOLD unless average win size clearly exceeds average loss size and drawdowns are controlled.
- SELL_BIAS requires strong similar sell evidence or repeated loss_after_entry/bad_buy_entry evidence. Do not use SELL_BIAS only because some prior cases were holds or not executed.
- If summary.action_tag_counts contains sell:premature_sell or sell:missed_upside_after_sell, be reluctant to recommend SELL_BIAS.
- If summary.action_tag_counts contains hold:missed_upside_after_hold, mention missed opportunity in reasons, but still require strong current evidence before recommending BUY_NORMAL.
- If summary.tag_counts contains under_sized_winner or buy_less_on_winner, compare realized losses and drawdowns before changing BUY_LESS.
- BUY_MORE should be exceptional. Avoid it unless similar reviewed winners clearly exceed losses, drawdowns are controlled, and today's current evidence is strong.
- When evidence is mixed, choose the safer recommendation: BUY_LESS for weak buy setups, HOLD for unclear setups, or INSUFFICIENT_HISTORY for thin history.
- Do not invent profit/loss outcomes when the cases do not include review data.
""",
                ),
                (
                    "human",
                    """[Today]
{today}

[Historical Search Result]
{history}
""",
                ),
            ]
        )
        self.chain = self.prompt | self.llm | StrOutputParser()

    def compare(
        self,
        *,
        ticker: str,
        user_id: int | None,
        strategy_slot: str,
        news_card: Dict[str, Any],
        quant_card: Dict[str, Any],
        quant_state: Dict[str, Any],
        as_of_date: str | None = None,
        base_date: str | None = None,
        lookback_days: int = 30,
        limit: int = 8,
    ) -> Dict[str, Any]:
        try:
            today = date.fromisoformat(str(as_of_date)) if as_of_date else date.today()
        except Exception:
            today = date.today()
        similar_to = {
            "news_stance": news_card.get("stance"),
            "news_score": _safe_score(news_card),
            "quant_stance": quant_card.get("stance"),
            "quant_score": _safe_score(quant_card),
            "market_regime": _nested(quant_state, "market_state", "intraday_trend")
            or _nested(quant_state, "market_state", "trend"),
            "entry_risk": _nested(quant_state, "risk_context", "entry_risk"),
            "signal_confidence": _nested(quant_state, "risk_context", "signal_confidence"),
            "volatility_state": _nested(quant_state, "market_state", "volatility_state"),
            "volume_state": _nested(quant_state, "market_state", "volume_state"),
            "price_vs_vwap": _nested(quant_state, "market_state", "price_vs_vwap"),
            "intraday_position": _nested(quant_state, "market_state", "intraday_position"),
            "mtf_alignment": _nested(quant_state, "multi_timeframe", "alignment_score"),
        }
        history = self.history_provider.search(
            ticker=ticker,
            user_id=user_id,
            strategy_slot=strategy_slot,
            from_date=(today - timedelta(days=lookback_days)).isoformat(),
            to_date=today.isoformat(),
            similar_to=similar_to,
            limit=limit,
        )
        if int(history.get("count") or 0) == 0:
            return {
                "schema": "historical_comparison_v1",
                "similar_cases_count": 0,
                "historical_bias": "insufficient_history",
                "recommendation": "INSUFFICIENT_HISTORY",
                "confidence": 0.0,
                "position_size_multiplier": 1.0,
                "reasons": ["no prior decision traces matched today's setup"],
                "cases_used": [],
                "history_query": {
                    "elapsed_ms": history.get("elapsed_ms"),
                    "filters": history.get("filters"),
                    "provider": self.history_provider.__class__.__name__,
                },
            }

        raw = self.chain.invoke(
            {
                "today": json.dumps(
                    {
                        "ticker": ticker,
                        "user_id": user_id,
                        "strategy_slot": strategy_slot,
                        "as_of_date": today.isoformat(),
                        "base_date": base_date,
                        "history_window": {
                            "from_date": (today - timedelta(days=lookback_days)).isoformat(),
                            "to_date": today.isoformat(),
                            "lookback_days": lookback_days,
                        },
                        "current_setup_features": similar_to,
                        "news_card": news_card,
                        "quant_card": quant_card,
                        "quant_state_summary": quant_state,
                    },
                    ensure_ascii=False,
                    default=str,
                ),
                "history": json.dumps(history, ensure_ascii=False, default=str),
            }
        )
        data = _load_json_object(raw)
        data["schema"] = "historical_comparison_v1"
        data["similar_cases_count"] = int(data.get("similar_cases_count") or len(history.get("items", [])))
        data["confidence"] = max(0.0, min(1.0, float(data.get("confidence") or 0.0)))
        data["position_size_multiplier"] = max(0.0, min(1.5, float(data.get("position_size_multiplier") or 1.0)))
        data["reasons"] = [str(item)[:240] for item in data.get("reasons", [])][:5]
        data["cases_used"] = [str(item) for item in data.get("cases_used", [])][:limit]
        data["history_query"] = {
            "elapsed_ms": history.get("elapsed_ms"),
            "filters": history.get("filters"),
            "provider": self.history_provider.__class__.__name__,
            "returned_count": len(history.get("items", [])),
        }
        return data
