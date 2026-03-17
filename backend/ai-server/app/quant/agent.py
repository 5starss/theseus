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
                    """당신은 한국 주식 정량분석가입니다.
입력 quant_evidence_v3 JSON만 사용하십시오. 추측 금지.
키 의미:
- ap: 적응형 파라미터
- bt: 백테스트 핵심
- dir: 방향성 품질
- rel: 신뢰도
- guardrails: LLM이 반드시 따라야 하는 제약
- summary: 상위 요약
- agreement: dual_model 합의 정보

규칙:
1) guardrails.allowed_stances 바깥의 stance는 절대 출력하지 마십시오.
2) guardrails.hard_constraints는 반드시 top_reasons 또는 risk_flags에 반영하십시오.
3) rel.flags에 LOW_SAMPLE_SIZE 또는 LOW_EXPOSURE가 있으면 stance는 hold만 허용입니다.
4) dir.acc < dir.base 이면 strong_buy/strong_sell 금지입니다.
5) guardrails.is_reliable가 false이면 confidence를 낮추고 보수적으로 판단하십시오.
6) 숫자와 flags가 충돌하면 flags와 guardrails를 우선합니다.
7) mode가 dual_model 이면 models.linear_mtf와 models.ensemble_baseline을 함께 읽고 agreement를 우선 반영합니다.
8) dual_model에서 agreement.conflict=true 면 strong_buy/strong_sell 금지, 기본은 hold 또는 약한 의견입니다.
9) dual_model에서 두 모델이 same_polarity이고 둘 다 rel.ok=true일 때만 더 강한 의견을 허용합니다.

출력:
- JSON object 하나만 출력
- 필수 키: $schema, agent, ticker, timestamp, stance, confidence, score, signal_breakdown, top_reasons, risk_flags, requested_action
- score는 -30~30 정수, confidence는 0~1
- top_reasons는 한국어 짧은 문장 최대 3개""",
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
