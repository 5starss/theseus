import json
import os
import re
from typing import Any, Dict

from dotenv import load_dotenv
from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import ChatPromptTemplate
from langchain_openai import ChatOpenAI

load_dotenv()


def _load_json_object(text: str) -> Dict[str, Any]:
    try:
        return json.loads(text)
    except Exception:
        m = re.search(r"\{[\s\S]*\}", text)
        if not m:
            raise
        return json.loads(m.group(0))


class RebuttalAgent:
    """News/Quant 카드 간 1회 반박 메시지를 생성합니다."""

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
                    """당신은 투자 분석 카드 충돌 조정자입니다.
반드시 JSON object 하나만 출력하세요. 설명/코드블록 금지.

출력 스키마(예시):
{{"news_rebuttal":"문장","quant_rebuttal":"문장"}}

규칙:
1) news_rebuttal: Quant 카드의 약점/모순 1문장
2) quant_rebuttal: News 카드의 약점/모순 1문장
3) 각 문장은 최대 25 토큰
4) 공격적 표현 금지, 근거 기반만
""",
                ),
                (
                    "human",
                    """[News Card]
{news_card}

[Quant Card]
{quant_card}
""",
                ),
            ]
        )
        self.chain = self.prompt | self.llm | StrOutputParser()

    def generate_rebuttal(self, news_card: Dict[str, Any], quant_card: Dict[str, Any]) -> Dict[str, str]:
        raw = self.chain.invoke(
            {
                "news_card": json.dumps(news_card, ensure_ascii=False),
                "quant_card": json.dumps(quant_card, ensure_ascii=False),
            }
        )
        data = _load_json_object(raw)
        news_text = str(data.get("news_rebuttal", "")).strip()
        quant_text = str(data.get("quant_rebuttal", "")).strip()
        return {"news_rebuttal": news_text[:200], "quant_rebuttal": quant_text[:200]}
