import json
import os
from datetime import datetime, timedelta, timezone
from typing import Any, Dict

from dotenv import load_dotenv
from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import ChatPromptTemplate
from langchain_upstage import ChatUpstage

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


class JudgeAgent:
    """News/Quant 카드를 종합해 실행 가능한 주문 카드를 생성합니다."""

    def __init__(self):
        api_key = os.getenv("UPSTAGE_API_KEY")
        if not api_key:
            raise ValueError("UPSTAGE_API_KEY가 설정되어 있지 않습니다.")

        self.llm = ChatUpstage(model="solar-1-mini-chat")
        self.prompt = ChatPromptTemplate.from_messages(
            [
                (
                    "system",
                    """당신은 한국 주식 매매 의사결정 에이전트(Judge)입니다.
입력된 News/Quant 카드와 시장값만 사용하여 주문 결정을 생성하세요.

출력은 JSON object 하나만:
{
  "$schema":"order_card_v1",
  "ticker":"000000",
  "timestamp":"ISO8601",
  "final_stance":"strong_buy|buy|hold|sell|strong_sell|conditional_buy|conditional_sell",
  "final_score":-30~30,
  "order":{"action":"buy|sell|hold","order_type":"market|limit","price":0,"quantity":0,"time_in_force":"day"},
  "risk_management":{"stop_loss_price":0,"take_profit_price":0},
  "verdict":"짧은 판단 근거"
}

제약:
1) quantity는 정수, 음수 금지
2) hold일 때 quantity=0
3) price는 현재가 기반 합리적 값
4) 과도한 확신 금지 (리스크 플래그 반영)
""",
                ),
                (
                    "human",
                    """[Input]
{payload}
""",
                ),
            ]
        )
        self.chain = self.prompt | self.llm | StrOutputParser()

    def generate_order_card(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        raw = self.chain.invoke({"payload": json.dumps(payload, ensure_ascii=False)})
        card = json.loads(raw)

        card["$schema"] = "order_card_v1"
        card["ticker"] = str(card.get("ticker") or payload.get("ticker") or "000000")
        card["timestamp"] = _to_kst_iso(card.get("timestamp"))
        card["final_stance"] = str(card.get("final_stance") or "hold")
        card["final_score"] = int(max(-30, min(30, int(card.get("final_score", 0)))))

        order = card.get("order") if isinstance(card.get("order"), dict) else {}
        action = str(order.get("action", "hold"))
        if action not in {"buy", "sell", "hold"}:
            action = "hold"
        order_type = str(order.get("order_type", "limit"))
        if order_type not in {"market", "limit"}:
            order_type = "limit"
        price = int(max(0, int(float(order.get("price", payload.get("current_price", 0))))))
        quantity = int(max(0, int(float(order.get("quantity", 0)))))
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
            "stop_loss_price": int(max(0, int(float(risk.get("stop_loss_price", 0))))),
            "take_profit_price": int(max(0, int(float(risk.get("take_profit_price", 0))))),
        }
        card["verdict"] = str(card.get("verdict") or "")
        return card
