import os
import json
from datetime import datetime
from typing import Any, Dict, List, Optional

from dotenv import load_dotenv
from langchain_core.documents import Document
from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import ChatPromptTemplate
from langchain_upstage import ChatUpstage

load_dotenv()


class NewsReporterAgent:
    """검색된 뉴스/커뮤니티 문서를 바탕으로 최종 분석 답변을 생성합니다."""

    def __init__(self):
        api_key = os.getenv("UPSTAGE_API_KEY")
        if not api_key:
            raise ValueError("UPSTAGE_API_KEY가 설정되어 있지 않습니다.")

        self.llm = ChatUpstage(model="solar-1-mini-chat")
        self.prompt = ChatPromptTemplate.from_messages(
            [
                (
                    "system",
                    """당신은 대한민국 금융 시장의 '주식 전망 예측 전문가'입니다.
제공된 '참고 데이터 목록(뉴스 및 커뮤니티)'을 정밀 분석하여 해당 종목의 향후 전망을 예측하십시오.

핵심 지침:
1. 모든 분석 내용에는 반드시 참고한 데이터의 번호(예: [1], [2])를 붙여 근거를 제시하십시오.
2. 분석 시 다음 단계를 준수하십시오:
- 현재 상황 분석: 핵심 이슈 요약 및 관련 근거 제시.
- 긍정적(Bullish) 요인: 상승 모멘텀 추출 (사실 기반 우선, 투자자 심리 참고).
- 부정적(Bearish) 요인: 하락 리스크 추출 (사실 기반 우선, 투자자 심리 참고).
- 종합 전망 예측: 위 요소들을 결합한 향후 향방 예측.
3. 데이터 출처별 신뢰도 가중치를 엄격히 적용하십시오.
- 뉴스(KIS_NEWS): 신뢰도 1.0 (핵심 근거로 활용, 객관적 사실 판단 기준)
- 커뮤니티(TOSS_COMMUNITY): 신뢰도 0.2 (시장 분위기/투자자 심리 참고용)
4. 커뮤니티 정보는 단독으로 결론을 내리는 근거로 사용하지 마십시오.
5. 투자 판단의 책임은 본인에게 있음을 명시하십시오.

[참고 데이터 목록]
{context}
""",
                ),
                ("human", "{question}"),
            ]
        )
        self.chain = self.prompt | self.llm | StrOutputParser()
        self.card_prompt = ChatPromptTemplate.from_messages(
            [
                (
                    "system",
                    """당신은 뉴스 투자심리 분석 에이전트입니다.
반드시 JSON object 하나만 출력하세요. 코드블록/설명 금지.
필수 키:
$schema, agent, ticker, timestamp, stance, confidence, score, signal_breakdown, top_reasons, risk_flags, requested_action
제약:
- agent는 "news"
- stance는 strong_buy|buy|hold|sell|strong_sell
- confidence는 0.0~1.0
- score는 -30~30 정수
- top_reasons는 최대 3개
- requested_action은 object
""",
                ),
                (
                    "human",
                    """질문: {question}
종목코드: {ticker}
뉴스(신뢰도 높음): {news_count}건
커뮤니티(심리 참고): {community_count}건

참고 데이터:
{context}
""",
                ),
            ]
        )
        self.card_chain = self.card_prompt | self.llm | StrOutputParser()

    def generate_response(
        self,
        question: str,
        news_docs: List[Document],
        community_docs: Optional[List[Document]] = None,
    ) -> str:
        if not news_docs and not community_docs:
            return "관련 정보를 찾지 못해 분석을 생성할 수 없습니다."

        context_parts = []
        if news_docs:
            news_lines = [
                f"[{i+1}] (발행: {doc.metadata.get('published_at', '시간 미상')}) {doc.page_content}"
                for i, doc in enumerate(news_docs)
            ]
            context_parts.append("📰 [뉴스 데이터 - 신뢰도 1.0, 핵심 분석 근거]\n" + "\n".join(news_lines))

        if community_docs:
            comm_lines = [f"[{chr(65+i)}] {doc.page_content}" for i, doc in enumerate(community_docs)]
            context_parts.append("💬 [커뮤니티 여론 - 신뢰도 0.2, 투자자 심리 참고용]\n" + "\n".join(comm_lines))

        context = "\n\n".join(context_parts)
        response = self.chain.invoke({"context": context, "question": question})

        footer = "\n\n[참조 출처 리스트]\n"
        for i, doc in enumerate(news_docs or []):
            footer += f"[{i+1}] [뉴스] {doc.metadata.get('title', '')} ({doc.metadata.get('published_at', '시간 미상')})\n"
        for i, doc in enumerate(community_docs or []):
            footer += f"[{chr(65+i)}] [커뮤니티] {doc.page_content[:30]}...\n"

        return response + footer

    def generate_analysis_card(
        self,
        ticker: str,
        question: str,
        news_docs: List[Document],
        community_docs: Optional[List[Document]] = None,
    ) -> Dict[str, Any]:
        news_docs = news_docs or []
        community_docs = community_docs or []

        if not news_docs and not community_docs:
            return {
                "$schema": "analysis_card_v1",
                "agent": "news",
                "ticker": ticker,
                "timestamp": datetime.now().isoformat(),
                "stance": "hold",
                "confidence": 0.0,
                "score": 0,
                "signal_breakdown": {"disclosure_signal": 0, "news_signal": 0, "community_signal": 0},
                "top_reasons": ["분석 가능한 뉴스/커뮤니티 데이터가 없습니다."],
                "risk_flags": ["no_data"],
                "requested_action": {"preference": "hold", "avoid_if": "unknown"},
            }

        context_parts = []
        if news_docs:
            context_parts.append(
                "\n".join(
                    f"[N{i+1}] ({doc.metadata.get('published_at', '시간 미상')}) {doc.page_content}"
                    for i, doc in enumerate(news_docs)
                )
            )
        if community_docs:
            context_parts.append(
                "\n".join(f"[C{i+1}] {doc.page_content}" for i, doc in enumerate(community_docs))
            )
        context = "\n\n".join(context_parts)

        try:
            raw = self.card_chain.invoke(
                {
                    "question": question,
                    "ticker": ticker,
                    "news_count": len(news_docs),
                    "community_count": len(community_docs),
                    "context": context,
                }
            )
            card = json.loads(raw)
        except Exception:
            card = {
                "$schema": "analysis_card_v1",
                "agent": "news",
                "ticker": ticker,
                "timestamp": datetime.now().isoformat(),
                "stance": "hold",
                "confidence": 0.0,
                "score": 0,
                "signal_breakdown": {"disclosure_signal": 0, "news_signal": 0, "community_signal": 0},
                "top_reasons": ["뉴스 에이전트 분석 응답 파싱 실패"],
                "risk_flags": ["agent_failure"],
                "requested_action": {"preference": "hold", "avoid_if": "unknown"},
            }

        card["$schema"] = "analysis_card_v1"
        card["agent"] = "news"
        card["ticker"] = ticker
        card["timestamp"] = card.get("timestamp") or datetime.now().isoformat()
        card["top_reasons"] = (card.get("top_reasons") or [])[:3]
        card["risk_flags"] = card.get("risk_flags") or []
        card["requested_action"] = card.get("requested_action") or {}
        return card
