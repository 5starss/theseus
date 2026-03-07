import logging
from typing import Any, Dict, List

from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import ChatPromptTemplate
from langchain_upstage import ChatUpstage

logger = logging.getLogger(__name__)


class RAGEvaluator:
    """LLM-as-a-Judge 기반 RAG 답변 정량 평가기."""

    def __init__(self):
        self.llm = ChatUpstage(model="solar-1-mini-chat")

    def _robust_parse(self, result: Any) -> Dict[str, Any]:
        import json
        import re

        res_dict: Dict[str, Any] = {}
        if hasattr(result, "dict"):
            res_dict = result.dict()
        elif isinstance(result, dict):
            res_dict = result
        elif isinstance(result, str):
            try:
                res_dict = json.loads(result)
            except Exception:
                match = re.search(r"\{.*\}", result, re.DOTALL)
                if match:
                    try:
                        res_dict = json.loads(match.group())
                    except Exception:
                        pass

        final = {
            "score": 0.0,
            "reason": "평가 결과 해석 실패",
            "strengths": [],
            "weaknesses": [],
            "action_items": [],
        }
        for alias in ["score", "Score", "점수"]:
            if alias in res_dict:
                try:
                    final["score"] = float(res_dict[alias])
                except Exception:
                    pass
                break
        for alias in ["reason", "Reason", "근거", "이유"]:
            if alias in res_dict:
                final["reason"] = str(res_dict[alias])
                break
        for alias in ["strengths", "강점"]:
            if alias in res_dict and isinstance(res_dict[alias], list):
                final["strengths"] = [str(x) for x in res_dict[alias]]
                break
        for alias in ["weaknesses", "약점"]:
            if alias in res_dict and isinstance(res_dict[alias], list):
                final["weaknesses"] = [str(x) for x in res_dict[alias]]
                break
        for alias in ["action_items", "개선사항", "개선_액션"]:
            if alias in res_dict and isinstance(res_dict[alias], list):
                final["action_items"] = [str(x) for x in res_dict[alias]]
                break
        return final

    def evaluate_faithfulness(self, response: str, normalized_context: str) -> Dict[str, Any]:
        prompt = ChatPromptTemplate.from_messages(
            [
                (
                    "system",
                    """당신은 인공지능 답변의 신뢰성을 검증하는 금융 데이터 감사관입니다.
제공된 참고 문헌에 기반해 답변의 사실 부합도를 평가하십시오.
평가 시 아래를 확인하세요:
- 근거 문헌에 없는 사실/수치(환각) 여부
- 과장/단정 표현 여부
- 출처 인용의 일관성

반드시 JSON만 출력하세요:
{{"score": 1.0, "reason": "...", "strengths": ["..."], "weaknesses": ["..."], "action_items": ["..."]}}""",
                ),
                ("human", "참고 문헌:\n{contexts}\n\n답변:\n{response}"),
            ]
        )
        try:
            chain = prompt | self.llm | StrOutputParser()
            raw_text = chain.invoke({"contexts": normalized_context, "response": response})
            return self._robust_parse(raw_text)
        except Exception as exc:
            logger.error("Faithfulness 평가 오류: %s", exc)
            return {"score": 0.0, "reason": f"평가 시스템 오류: {exc}"}

    def evaluate_relevancy(self, question: str, response: str) -> Dict[str, Any]:
        prompt = ChatPromptTemplate.from_messages(
            [
                (
                    "system",
                    """당신은 답변의 적절성을 평가하는 전문가입니다.
질문 대비 답변의 유용성과 명확성을 평가하세요.
평가 시 아래를 확인하세요:
- 질문 의도 충족 여부
- 구조(핵심 이슈/상승 요인/하락 요인/종합 전망) 충족 여부
- 실질적 의사결정에 도움이 되는 구체성

반드시 JSON만 출력하세요:
{{"score": 1.0, "reason": "...", "strengths": ["..."], "weaknesses": ["..."], "action_items": ["..."]}}""",
                ),
                ("human", "질문: {question}\n\n답변: {response}"),
            ]
        )
        try:
            chain = prompt | self.llm | StrOutputParser()
            raw_text = chain.invoke({"question": question, "response": response})
            return self._robust_parse(raw_text)
        except Exception as exc:
            logger.error("Relevancy 평가 오류: %s", exc)
            return {"score": 0.0, "reason": f"평가 시스템 오류: {exc}"}

    def evaluate_source_balance(self, response: str) -> Dict[str, Any]:
        prompt = ChatPromptTemplate.from_messages(
            [
                (
                    "system",
                    """당신은 금융 RAG 답변의 출처 균형을 검사하는 심사자입니다.
원칙:
- 뉴스(KIS_NEWS)는 핵심 근거(신뢰도 1.0)
- 커뮤니티(TOSS_COMMUNITY)는 투자자 심리 참고(신뢰도 0.2)
- 커뮤니티 단독으로 결론이 형성되면 감점

반드시 JSON만 출력하세요:
{{"score": 1.0, "reason": "...", "strengths": ["..."], "weaknesses": ["..."], "action_items": ["..."]}}""",
                ),
                ("human", "답변:\n{response}"),
            ]
        )
        try:
            chain = prompt | self.llm | StrOutputParser()
            raw_text = chain.invoke({"response": response})
            return self._robust_parse(raw_text)
        except Exception as exc:
            logger.error("Source balance 평가 오류: %s", exc)
            return {"score": 0.0, "reason": f"평가 시스템 오류: {exc}"}

    def run_full_eval(self, question: str, response: str, retrieved_docs: List[Any]) -> Dict[str, Dict[str, Any]]:
        news_docs = [d for d in retrieved_docs if d.metadata.get("source") == "KIS_NEWS"]
        comm_docs = [d for d in retrieved_docs if d.metadata.get("source") == "TOSS_COMMUNITY"]

        context_parts = []
        if news_docs:
            news_lines = [f"[{i+1}] {d.page_content}" for i, d in enumerate(news_docs)]
            context_parts.append("[뉴스 리스트]\n" + "\n".join(news_lines))
        if comm_docs:
            comm_lines = [f"[{chr(65+i)}] {d.page_content}" for i, d in enumerate(comm_docs)]
            context_parts.append("[커뮤니티 리스트]\n" + "\n".join(comm_lines))
        normalized_context = "\n\n".join(context_parts)

        faith = self.evaluate_faithfulness(response=response, normalized_context=normalized_context)
        rel = self.evaluate_relevancy(question=question, response=response)
        source_balance = self.evaluate_source_balance(response=response)

        overall_score = round(
            (faith.get("score", 0.0) * 0.4)
            + (rel.get("score", 0.0) * 0.4)
            + (source_balance.get("score", 0.0) * 0.2),
            4,
        )

        return {
            "faithfulness": faith,
            "relevancy": rel,
            "source_balance": source_balance,
            "overall_score": overall_score,
        }
