import json
import os
from datetime import datetime, timedelta, timezone
from typing import Any, Dict

from dotenv import load_dotenv
from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import ChatPromptTemplate
from langchain_openai import ChatOpenAI

load_dotenv()
KST = timezone(timedelta(hours=9))


def _kst_now_iso() -> str:
    return datetime.now(KST).isoformat()


def _to_kst_iso(value: Any) -> str:
    if value is None:
        return _kst_now_iso()
    try:
        s = str(value).strip()
        if s.endswith("Z"):
            s = s[:-1] + "+00:00"
        dt = datetime.fromisoformat(s)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=KST)
        return dt.astimezone(KST).isoformat()
    except Exception:
        return _kst_now_iso()


def _safe_int(value: Any, default: int = 0) -> int:
    try:
        if value is None:
            return default
        if isinstance(value, str) and not value.strip():
            return default
        return int(float(value))
    except Exception:
        return default


class JudgeAgent:
    """News/Quant 카드를 종합해 실행 가능한 주문 카드를 생성합니다."""

    def __init__(self):
        api_key = os.getenv("GMS_API_KEY")
        if not api_key:
            raise ValueError("GMS_API_KEY가 설정되어 있지 않습니다.")

        self.llm = ChatOpenAI(
            model="gpt-5-nano",
            openai_api_key=api_key,
            openai_api_base="https://gms.ssafy.io/gmsapi/api.openai.com/v1"
        )
        self.prompt = ChatPromptTemplate.from_messages(
            [
                (
                    "system",
                   """당신은 한국 주식 매매 의사결정 에이전트(Judge)입니다.
입력된 News/Quant 카드와 시장값만 사용하여 주문 결정을 생성하세요.
signal_weights를 반드시 반영하세요. 예를 들어 news_weight=60, quant_weight=40이면 뉴스 판단을 더 강하게, news_weight=40, quant_weight=60이면 퀀트 판단을 더 강하게 반영하세요.
strategy_slot이 morning이면 뉴스 비중이 더 높고, afternoon이면 퀀트 비중이 더 높아야 합니다.

quant_state_summary가 포함되어 있으면 반드시 참조하세요.
이 필드에는 market_state, multi_timeframe, symbol_profile, risk_context, supporting_metrics가 있습니다.
- QuantAgent의 quant_card는 1차 해석 결과입니다.
- quant_state_summary는 해석 전 원본 상태이므로, QuantAgent 판단이 맞는지 교차 검증에 활용하세요.
- 특히 risk_context.entry_risk, risk_context.signal_confidence, multi_timeframe.alignment_score를 주문 결정에 반영하세요.

반드시 JSON object 하나만 출력하세요.
모든 설명 문자열은 한국어로 작성하세요.
verdict는 비워두지 말고 최종 판단 이유를 1문장으로 작성하세요.
""",
                ),
                ("human", "[Input]\n{payload}"),
            ]
        )
        self.chain = self.prompt | self.llm | StrOutputParser()

    def generate_order_card(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        raw = self.chain.invoke({"payload": json.dumps(payload, ensure_ascii=False)})
        card = json.loads(raw)

        card["$schema"] = "order_card_v1"
        card["ticker"] = str(card.get("ticker") or payload.get("ticker") or "000000")
        card["timestamp"] = _kst_now_iso()
        card["final_stance"] = str(card.get("final_stance") or "hold")
        card["final_score"] = max(-30, min(30, _safe_int(card.get("final_score", 0))))

        order = card.get("order") if isinstance(card.get("order"), dict) else {}
        action = str(order.get("action", "hold"))
        if action not in {"buy", "sell", "hold"}:
            action = "hold"
        order_type = str(order.get("order_type", "limit"))
        if order_type not in {"market", "limit"}:
            order_type = "limit"
        price = max(0, _safe_int(order.get("price", payload.get("current_price", 0))))
        quantity = max(0, _safe_int(order.get("quantity", 0)))
        if action == "hold":
            quantity = 0
        card["order"] = {
            "action": action,
            "order_type": order_type,
            "price": price,
            "quantity": quantity,
            "time_in_force": "day",
        }

        risk = card.get("risk_management") if isinstance(card.get("risk_management"), dict) else {}
        card["risk_management"] = {
            "stop_loss_price": max(0, _safe_int(risk.get("stop_loss_price", 0))),
            "take_profit_price": max(0, _safe_int(risk.get("take_profit_price", 0))),
        }
        card["verdict"] = str(card.get("verdict") or "").strip() or self._build_default_verdict(
            final_stance=card["final_stance"],
            final_score=card["final_score"],
            action=card["order"]["action"],
        )

        # 허용된 스키마 키만 남기고 나머지 top-level 키 제거
        allowed_keys = {
            "$schema", "ticker", "timestamp", "final_stance", "final_score",
            "order", "risk_management", "verdict"
        }
        card = {k: v for k, v in card.items() if k in allowed_keys}

        return card

    @staticmethod
    def _build_default_verdict(final_stance: str, final_score: int, action: str) -> str:
        if action == "hold":
            return f"뉴스와 퀀트 신호를 종합했을 때 확신이 부족해 관망이 적절합니다. (score={final_score})"
        if action == "buy":
            return f"뉴스와 퀀트 신호를 종합했을 때 매수 우위 판단입니다. (score={final_score})"
        if action == "sell":
            return f"뉴스와 퀀트 신호를 종합했을 때 매도 우위 판단입니다. (score={final_score})"
        return f"종합 점수 기준 {final_stance} 판단입니다. (score={final_score})"
