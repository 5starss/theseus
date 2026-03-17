import json
import os
from datetime import datetime
from typing import Any, Dict

from dotenv import load_dotenv
from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import ChatPromptTemplate
from langchain_openai import ChatOpenAI

load_dotenv()


class QuantAnalysisAgent:
    """정량 근거 JSON을 해석해 analysis_card_v1 형식의 Quant 의견을 생성합니다."""

    def __init__(self):
        api_key = os.getenv("GMS_API_KEY")
        if not api_key:
            raise ValueError("GMS_API_KEY가 설정되어 있지 않습니다.")

        self.llm = ChatOpenAI(
            model="gpt-4.1-nano",
            openai_api_key=api_key,
            openai_api_base="https://gms.ssafy.io/gmsapi/api.openai.com/v1"
        )
        self.prompt = ChatPromptTemplate.from_messages(
            [
                (
                    "system",
                    """당신은 한국 주식 퀀트 애널리스트입니다.
입력된 다중 시간 프레임(Multi-Timeframe) 기술적 지표 JSON만을 사용하여 판단하십시오. 추측은 금지합니다.
키 의미:
- 1분봉 지표: rsi_14, macd, bb_pct_b (볼린저밴드 위치), vwap 등
- 다중 시간 프레임 지표 (mtf_*): mtf_5m_rsi_14, mtf_1d_trend 등 (5분, 15분, 60분, 일봉)

규칙:
1) 단기 지표(1분/5분)와 장기 지표(60분/일봉)의 추세가 일치할 때 강한 의견(buy/sell)을 제시하십시오.
2) 장단기 추세가 엇갈리거나 변동성이 비정상적으로 높으면 보수적으로 hold 의견을 냅니다.
3) 지표상 명확한 퀀트 시그널(예: RSI 과매도/과매수, MACD 크로스, 볼린저 밴드 이탈 등)을 근거로 삼으십시오.
4) 방향성(stance)은 buy, sell, hold 중 하나여야 합니다.

출력:
- JSON object 하나만 출력
- 필수 키: $schema, agent, ticker, timestamp, stance, confidence, score, signal_breakdown, top_reasons, risk_flags, requested_action
- score는 -30~30 정수, confidence는 0.0 ~ 1.0 실수
- top_reasons는 한국어 짧은 문장 최대 3개로 작성하며, 예: "일봉상 장기 상승 추세 속에서 5분봉 기준 단기 과매도(RSI 28) 진입"과 같이 구체적 지표를 언급할 것.""",
                ),
                (
                    "human",
                    "{quant_evidence}",
                ),
            ]
        )
        self.chain = self.prompt | self.llm | StrOutputParser()

    @staticmethod
    def _fallback_card(ticker: str, reason: str) -> Dict[str, Any]:
        return {
            "$schema": "analysis_card_v1",
            "agent": "quant",
            "ticker": ticker,
            "timestamp": datetime.now().isoformat(),
            "stance": "hold",
            "confidence": 0.0,
            "score": 0,
            "signal_breakdown": {},
            "top_reasons": [reason],
            "risk_flags": ["agent_failure"],
            "requested_action": {"preference": "hold", "avoid_if": "low_reliability"},
        }

    def generate_analysis_card(
        self,
        ticker: str,
        quant_evidence: Dict[str, Any],
    ) -> Dict[str, Any]:
        try:
            raw = self.chain.invoke({"quant_evidence": json.dumps(quant_evidence, ensure_ascii=False)})
            card = json.loads(raw)
        except Exception:
            card = self._fallback_card(ticker=ticker, reason="quant evidence 해석 실패")
        card["$schema"] = "analysis_card_v1"
        card["agent"] = "quant"
        card["ticker"] = ticker
        card["timestamp"] = card.get("timestamp") or datetime.now().isoformat()
        card["top_reasons"] = (card.get("top_reasons") or [])[:3]
        card["risk_flags"] = card.get("risk_flags") or []
        card["requested_action"] = card.get("requested_action") or {}
        return card
