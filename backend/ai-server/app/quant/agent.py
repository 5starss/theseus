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
            model="gpt-5-mini",
            openai_api_key=api_key,
            openai_api_base="https://gms.ssafy.io/gmsapi/api.openai.com/v1"
        )
        self.prompt = ChatPromptTemplate.from_messages(
            [
                (
                    "system",
                    """당신은 한국 주식 퀀트 애널리스트입니다.
입력은 raw 지표가 아니라 해석된 상태(State) 스키마입니다. 다음 5개 블록으로 구성됩니다.

1. market_state: 장중 실시간 시장 상태 묘사
   - intraday_trend (up/neutral/down), momentum_strength (strong/moderate/weak)
   - volatility_state (expanding/normal/contracting), volume_state (high/moderate/normal)
   - price_vs_vwap (above/near/below), overheat_state (high/moderate/low)
   - intraday_position (near_high/mid/near_low), session_phase (opening/midday/late_midday/closing)

2. multi_timeframe: 타임프레임 방향 정렬
   - m1, m5, m15, h1, d1 각각 up/neutral/down
   - alignment_score: 0~1 (1에 가까울수록 모든 타임프레임이 같은 방향)

3. symbol_profile: 종목 구조적 성격
   - trend_efficiency (high/medium/low), drawdown_risk (low/medium/high)
   - volatility_character (stable/moderate/volatile), mean_reversion_tendency (low/medium/high)

4. risk_context: 진입 타이밍 메타 평가
   - entry_risk (low/medium/high), reward_risk_quality (good/fair/poor)
   - signal_confidence (high/medium/low)

5. supporting_metrics: 참조용 핵심 수치 (mom_5, rsi_14, dist_vwap, volume_z20, mtf_15m_trend)

6. today_intraday_context: 선택적 오전장 보조 문맥
   - window, bars, open_price, last_price, high_price, low_price
   - change_pct, range_pct, total_volume, trend, as_of
   - 값이 있으면 당일 09:00~12:00 흐름을 보조적으로 반영하세요.

판단 규칙:
1) alignment_score가 높고 signal_confidence가 high이면 강한 의견(buy 또는 sell).
2) entry_risk가 high이면 보수적으로 hold 의견을 내세요.
3) intraday_trend와 상위 타임프레임(h1, d1)의 방향이 일치할 때 확신도를 높이세요.
4) reward_risk_quality가 poor이면 진입을 피하세요.
5) stance는 buy, sell, hold 중 하나여야 합니다.
6) today_intraday_context.trend와 change_pct가 뚜렷하면 당일 단기 흐름 확인용 보조 근거로 사용하세요. 단, alignment_score와 signal_confidence를 뒤집을 정도로 과대평가하지 마세요.

출력:
- JSON object 하나만 출력
- 필수 키: $schema, agent, ticker, timestamp, stance, confidence, score, signal_breakdown, top_reasons, risk_flags, requested_action
- score는 -30~30 정수, confidence는 0.0 ~ 1.0 실수
- top_reasons는 한국어 짧은 문장 최대 3개로 작성하며, 상태 블록의 값과 supporting_metrics 수치를 근거로 제시할 것.
  예: "alignment_score 0.9로 전 타임프레임 상승 정렬, momentum_strength strong (mom_5=0.014)"
""",
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
