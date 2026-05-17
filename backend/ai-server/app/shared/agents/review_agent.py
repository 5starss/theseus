import json
import os
import re
from typing import Any, Dict, List

from dotenv import load_dotenv
from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import ChatPromptTemplate
from langchain_openai import ChatOpenAI

load_dotenv()


def _load_json_object(text: str) -> Dict[str, Any]:
    try:
        return json.loads(text)
    except Exception:
        match = re.search(r"\{[\s\S]*\}", text)
        if not match:
            raise
        return json.loads(match.group(0))


def _safe_float(value: Any) -> float | None:
    try:
        if value is None:
            return None
        return float(value)
    except Exception:
        return None


def _normalize_outcome(value: Any) -> str:
    normalized = str(value or "UNKNOWN").upper()
    if normalized in {"WIN", "LOSS", "FLAT", "NOT_EXECUTED", "UNKNOWN"}:
        return normalized
    return "UNKNOWN"


class ReviewAgent:
    """Evaluates a completed trading decision and extracts reusable lessons."""

    def __init__(self):
        api_key = os.getenv("GMS_API_KEY")
        if not api_key:
            raise ValueError("GMS_API_KEY is required for ReviewAgent.")

        self.llm = ChatOpenAI(
            model=os.getenv("REVIEW_AGENT_MODEL", "gpt-5-mini"),
            openai_api_key=api_key,
            openai_api_base="https://gms.ssafy.io/gmsapi/api.openai.com/v1",
        )
        self.prompt = ChatPromptTemplate.from_messages(
            [
                (
                    "system",
                    """You are a post-trade review agent.
Evaluate whether the original trading decision was supported by the evidence and outcome.
Use only the provided decision trace and market outcome. Do not invent missing fills or prices.

Return ONLY a JSON object:
{{
  "outcome": "WIN|LOSS|FLAT|NOT_EXECUTED|UNKNOWN",
  "mistake_tags": ["short_tag"],
  "lesson": "one concise reusable lesson in Korean",
  "signal_assessment": {{
    "news_helped": true,
    "quant_helped": true,
    "historical_comparison_helped": true,
    "risk_review_helped": true
  }},
  "review_summary": "one sentence in Korean"
}}

Guidelines:
- If execution_status indicates no execution, outcome should be NOT_EXECUTED unless market_outcome proves otherwise.
- If pnl_pct is positive, outcome is usually WIN; negative is usually LOSS; near zero is FLAT.
- mistake_tags should be compact snake_case tags, max 5.
- lesson must be useful for future HistoricalComparisonAgent decisions.
""",
                ),
                (
                    "human",
                    """[Decision Trace]
{decision_trace}

[Market Outcome]
{market_outcome}
""",
                ),
            ]
        )
        self.chain = self.prompt | self.llm | StrOutputParser()

    def generate_review(self, *, decision_trace: Dict[str, Any], market_outcome: Dict[str, Any]) -> Dict[str, Any]:
        raw = self.chain.invoke(
            {
                "decision_trace": json.dumps(decision_trace, ensure_ascii=False, default=str),
                "market_outcome": json.dumps(market_outcome, ensure_ascii=False, default=str),
            }
        )
        data = _load_json_object(raw)
        mistake_tags: List[str] = []
        for item in data.get("mistake_tags", []) or []:
            tag = str(item).strip().lower().replace(" ", "_")
            if tag:
                mistake_tags.append(tag[:64])

        assessment = data.get("signal_assessment") if isinstance(data.get("signal_assessment"), dict) else {}
        return {
            "outcome": _normalize_outcome(data.get("outcome")),
            "mistake_tags": mistake_tags[:5],
            "lesson": str(data.get("lesson") or "").strip()[:1000],
            "signal_assessment": {
                "news_helped": bool(assessment.get("news_helped")),
                "quant_helped": bool(assessment.get("quant_helped")),
                "historical_comparison_helped": bool(assessment.get("historical_comparison_helped")),
                "risk_review_helped": bool(assessment.get("risk_review_helped")),
            },
            "review_summary": str(data.get("review_summary") or "").strip()[:1000],
            "pnl_pct": _safe_float(market_outcome.get("pnl_pct")),
            "max_drawdown_pct": _safe_float(market_outcome.get("max_drawdown_pct")),
            "holding_minutes": market_outcome.get("holding_minutes"),
            "execution_status": market_outcome.get("execution_status"),
        }
