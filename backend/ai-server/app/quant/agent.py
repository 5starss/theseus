import json
import os
from datetime import datetime
from typing import Any, Dict, Optional

from dotenv import load_dotenv
from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import ChatPromptTemplate
from langchain_upstage import ChatUpstage

load_dotenv()


class QuantAnalysisAgent:
    """정량 근거 JSON을 해석해 analysis_card_v1 형식의 Quant 의견을 생성합니다."""

    def __init__(self):
        api_key = os.getenv("UPSTAGE_API_KEY")
        if not api_key:
            raise ValueError("UPSTAGE_API_KEY가 설정되어 있지 않습니다.")

        self.llm = ChatUpstage(model="solar-1-mini-chat")
        self.prompt = ChatPromptTemplate.from_messages(
            [
                (
                    "system",
                    """당신은 한국 주식 시계열 정량분석 전문가입니다.
입력으로 제공된 quant_evidence_v1 JSON만 사용해 판단하십시오. 추측 금지.
편향 방지 규칙:
1) quality_flags에 LOW_SAMPLE_SIZE 또는 LOW_EXPOSURE가 있으면 stance는 hold 또는 conditional 성격만 허용.
2) directional_accuracy_all < directional_baseline_all 이면 strong_buy/strong_sell 금지.
3) 과도한 수익률/샤프 수치가 있어도 reliability가 낮으면 신뢰도를 낮춰야 함.
4) 숫자와 플래그가 충돌하면 플래그를 우선.

출력 규칙:
- JSON object 하나만 출력(설명/코드블록 금지)
- 아래 키를 반드시 포함:
  $schema, agent, ticker, timestamp, stance, confidence, score, signal_breakdown, top_reasons, risk_flags, requested_action
- score 범위: -30~30 정수, confidence: 0.0~1.0
- top_reasons는 한국어 짧은 문장 최대 3개
""",
                ),
                (
                    "human",
                    """[Quant Evidence]
{quant_evidence}

[News Card - optional]
{news_card}
""",
                ),
            ]
        )
        self.chain = self.prompt | self.llm | StrOutputParser()

    def generate_analysis_card(
        self,
        ticker: str,
        quant_evidence: Dict[str, Any],
        news_card: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        news_payload = news_card if news_card is not None else {}
        raw = self.chain.invoke(
            {
                "quant_evidence": json.dumps(quant_evidence, ensure_ascii=False),
                "news_card": json.dumps(news_payload, ensure_ascii=False),
            }
        )
        card = json.loads(raw)
        card["$schema"] = "analysis_card_v1"
        card["agent"] = "quant"
        card["ticker"] = ticker
        card["timestamp"] = card.get("timestamp") or datetime.now().isoformat()
        card["top_reasons"] = (card.get("top_reasons") or [])[:3]
        card["risk_flags"] = card.get("risk_flags") or []
        card["requested_action"] = card.get("requested_action") or {}
        return card
