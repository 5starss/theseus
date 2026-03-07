import os
from typing import List, Optional

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
                    """당신은 대한민국 금융 시장의 주식 전망 분석가입니다.
제공된 참고 데이터(뉴스/커뮤니티)를 근거로 핵심 이슈, 상승 요인, 하락 요인, 종합 전망을 제시하세요.
근거 번호([1], [2], [A] 등)를 답변에 명시하고, 마지막에 투자 판단 책임 고지를 포함하세요.

[참고 데이터]
{context}
""",
                ),
                ("human", "{question}"),
            ]
        )
        self.chain = self.prompt | self.llm | StrOutputParser()

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
            context_parts.append("[뉴스 데이터 - 신뢰도 1.0]\n" + "\n".join(news_lines))

        if community_docs:
            comm_lines = [f"[{chr(65+i)}] {doc.page_content}" for i, doc in enumerate(community_docs)]
            context_parts.append("[커뮤니티 여론 - 신뢰도 0.2]\n" + "\n".join(comm_lines))

        context = "\n\n".join(context_parts)
        response = self.chain.invoke({"context": context, "question": question})

        footer = "\n\n[참조 출처]\n"
        for i, doc in enumerate(news_docs or []):
            footer += f"[{i+1}] [뉴스] {doc.metadata.get('title', '')} ({doc.metadata.get('published_at', '시간 미상')})\n"
        for i, doc in enumerate(community_docs or []):
            footer += f"[{chr(65+i)}] [커뮤니티] {doc.page_content[:30]}...\n"

        return response + footer
