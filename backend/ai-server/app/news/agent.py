import os
import json
import logging
import re
from datetime import datetime
from typing import Any, Dict, List, Optional

from dotenv import load_dotenv
from langchain_core.documents import Document
from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import ChatPromptTemplate
from langchain_openai import ChatOpenAI

load_dotenv()
logger = logging.getLogger(__name__)


def _repair_common_json_issues(text: str) -> str:
    repaired = text
    requested_action_pattern = re.compile(
        r'("requested_action"\s*:\s*\{)([\s\S]*?)(\})',
        re.MULTILINE,
    )

    def _fix_requested_action(match: re.Match[str]) -> str:
        prefix, body, suffix = match.groups()
        lines = body.splitlines()
        fixed_lines: List[str] = []
        note_count = 0

        for line in lines:
            stripped = line.strip()
            if not stripped:
                fixed_lines.append(line)
                continue
            if ":" in stripped or stripped in {"{", "}"}:
                fixed_lines.append(line)
                continue

            comma = "," if stripped.endswith(",") else ""
            value = stripped[:-1].strip() if comma else stripped
            if re.fullmatch(r'"[^"]+"', value):
                note_key = "note" if note_count == 0 else f"note_{note_count + 1}"
                indent = line[: len(line) - len(line.lstrip())]
                fixed_lines.append(f'{indent}"{note_key}": {value}{comma}')
                note_count += 1
                continue

            fixed_lines.append(line)

        return prefix + "".join(
            f"{fixed_line}\n" if idx < len(fixed_lines) - 1 else fixed_line
            for idx, fixed_line in enumerate(fixed_lines)
        ) + suffix

    return requested_action_pattern.sub(_fix_requested_action, repaired, count=1)


def _load_json_object(text: str) -> Dict[str, Any]:
    try:
        return json.loads(text)
    except Exception:
        m = re.search(r"\{[\s\S]*\}", text)
        if not m:
            raise
        candidate = m.group(0)
        try:
            return json.loads(candidate)
        except Exception:
            return json.loads(_repair_common_json_issues(candidate))


class NewsReporterAgent:
    """검색된 뉴스/커뮤니티 문서를 바탕으로 최종 분석 답변을 생성합니다."""

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
                    """당신은 대한민국 금융 시장의 '주식 전망 예측 전문가'입니다.
제공된 '참고 데이터 목록(뉴스 및 커뮤니티)'을 정밀 분석하여 해당 종목의 향후 전망을 예측하십시오.

핵심 지침:
1. 모든 분석 내용에는 반드시 참고한 데이터의 번호(예: [1], [2])를 붙여 근거를 제시하십시오.
2. 분석 시 다음 단계를 준수하십시오:
- 현재 상황 분석: 핵심 이슈 요약 및 관련 근거 제시.
- 긍정적(Bullish) 요인: 상승 모멘텀 추출 (반드시 뉴스 근거 우선, 커뮤니티는 보조 의견만 허용).
- 부정적(Bearish) 요인: 하락 리스크 추출 (반드시 뉴스 근거 우선, 커뮤니티는 보조 의견만 허용).
- 종합 전망 예측: 위 요소들을 결합한 향후 향방 예측.
3. 데이터 출처별 신뢰도 가중치를 엄격히 적용하십시오.
- 뉴스(KIS_NEWS): 신뢰도 1.0 (핵심 근거로 활용, 객관적 사실 판단 기준)
- 커뮤니티(TOSS_COMMUNITY): 신뢰도 0.2 (시장 분위기/투자자 심리 참고용)
4. 커뮤니티 정보는 반드시 별도 보조 섹션에서만 다루고, 뉴스 근거를 보완하는 용도로만 사용하십시오.
5. 뉴스 근거가 없는 방향성 판단, 목표가 제시, 상승/하락 모멘텀 단정은 금지합니다.
6. 뉴스가 없거나 뉴스 근거가 약하면 결론은 반드시 중립적 관망으로 제한하고, 커뮤니티는 심리 참고 사항으로만 요약하십시오.
7. 투자 판단의 책임은 본인에게 있음을 명시하십시오.

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
- requested_action은 반드시 아래 스키마의 object
  {{"preference":"buy|hold|sell","avoid_if":"문장"}}
- requested_action에 다른 키를 만들지 마세요
- 모든 문자열 필드는 한국어로 작성
- timestamp는 현재 시각 기준 ISO 형식
- 뉴스(N*)는 핵심 근거, 커뮤니티(C*)는 보조 근거로만 사용하세요
- C*만으로 stance/score/confidence를 결정하지 마세요
- stance가 buy/sell/strong_buy/strong_sell 이려면 반드시 top_reasons에 N* 근거가 포함되어야 합니다
- 뉴스 근거가 전혀 없으면 stance는 hold, requested_action.preference는 hold로 제한하세요
- 뉴스 근거가 1건으로 제한적이거나 후속 확인이 부족하면 strong 계열은 금지하고, 필요하면 낮은 confidence의 buy/sell 또는 hold만 허용하세요
- 커뮤니티는 투자심리 보조 정보일 뿐이며, top_reasons의 주근거가 되어서는 안 됩니다
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

    @staticmethod
    def _build_empty_analysis_card(ticker: str, reason: str, risk_flag: str) -> Dict[str, Any]:
        return {
            "$schema": "analysis_card_v1",
            "agent": "news",
            "ticker": ticker,
            "timestamp": datetime.now().isoformat(),
            "stance": "hold",
            "confidence": 0.0,
            "score": 0,
            "signal_breakdown": {"disclosure_signal": 0, "news_signal": 0, "community_signal": 0},
            "top_reasons": [reason],
            "risk_flags": [risk_flag],
            "requested_action": {"preference": "hold", "avoid_if": "unknown"},
        }

    @staticmethod
    def _build_response_context(
        news_docs: List[Document],
        community_docs: List[Document],
    ) -> str:
        context_parts: List[str] = []
        if news_docs:
            news_lines = [
                f"[{i+1}] (발행: {doc.metadata.get('published_at', '시간 미상')}) {doc.page_content}"
                for i, doc in enumerate(news_docs)
            ]
            context_parts.append("📰 [뉴스 데이터 - 신뢰도 1.0, 핵심 분석 근거]\n" + "\n".join(news_lines))

        if community_docs:
            comm_lines = [f"[{chr(65+i)}] {doc.page_content}" for i, doc in enumerate(community_docs)]
            context_parts.append("💬 [커뮤니티 여론 - 신뢰도 0.2, 투자자 심리 참고용]\n" + "\n".join(comm_lines))

        return "\n\n".join(context_parts)

    @staticmethod
    def _build_card_context(
        news_docs: List[Document],
        community_docs: List[Document],
    ) -> str:
        context_parts: List[str] = []
        if news_docs:
            context_parts.append(
                "[뉴스 - 핵심 근거]\n"
                + "\n".join(
                    f"[N{i+1}] ({doc.metadata.get('published_at', '시간 미상')}) {doc.page_content}"
                    for i, doc in enumerate(news_docs)
                )
            )
        if community_docs:
            context_parts.append(
                "[커뮤니티 - 보조 참고, 단독 결론 금지]\n"
                + "\n".join(f"[C{i+1}] {doc.page_content}" for i, doc in enumerate(community_docs))
            )
        return "\n\n".join(context_parts)

    @staticmethod
    def _normalize_card_payload(card: Dict[str, Any], ticker: str) -> Dict[str, Any]:
        card["$schema"] = "analysis_card_v1"
        card["agent"] = "news"
        card["ticker"] = ticker
        card["timestamp"] = card.get("timestamp") or datetime.now().isoformat()
        card["top_reasons"] = (card.get("top_reasons") or [])[:3]
        card["risk_flags"] = card.get("risk_flags") or []
        requested_action = card.get("requested_action")
        if not isinstance(requested_action, dict):
            requested_action = {}
        preference = str(requested_action.get("preference") or "").strip().lower()
        if preference not in {"buy", "hold", "sell"}:
            stance = str(card.get("stance") or "hold").strip().lower()
            if stance in {"strong_buy", "buy"}:
                preference = "buy"
            elif stance in {"strong_sell", "sell"}:
                preference = "sell"
            else:
                preference = "hold"
        avoid_if = str(
            requested_action.get("avoid_if")
            or requested_action.get("note")
            or requested_action.get("note_2")
            or "unknown"
        ).strip() or "unknown"
        card["requested_action"] = {"preference": preference, "avoid_if": avoid_if}
        return card

    @staticmethod
    def _count_news_references(top_reasons: List[Any]) -> int:
        count = 0
        for reason in top_reasons:
            if not isinstance(reason, str):
                continue
            if re.search(r"\[N\d+\]", reason):
                count += 1
        return count

    @classmethod
    def _enforce_news_evidence_guard(
        cls,
        card: Dict[str, Any],
        news_docs: List[Document],
    ) -> Dict[str, Any]:
        stance = str(card.get("stance") or "hold").strip().lower()
        if stance not in {"strong_buy", "buy", "sell", "strong_sell"}:
            return card

        top_reasons = card.get("top_reasons")
        if not isinstance(top_reasons, list):
            top_reasons = []
        unique_titles = {
            str(doc.metadata.get("title") or "").strip()
            for doc in news_docs
            if str(doc.metadata.get("title") or "").strip()
        }
        has_news_reference = cls._count_news_references(top_reasons) > 0
        has_minimum_news_docs = len(unique_titles) >= 2

        if has_news_reference and has_minimum_news_docs:
            return card

        risk_flags = card.get("risk_flags")
        if not isinstance(risk_flags, list):
            risk_flags = []
        if "insufficient_news_evidence" not in risk_flags:
            risk_flags.append("insufficient_news_evidence")
        card["risk_flags"] = risk_flags
        try:
            current_confidence = float(card.get("confidence") or 0.0)
        except (TypeError, ValueError):
            current_confidence = 0.0
        try:
            current_score = int(float(card.get("score") or 0))
        except (TypeError, ValueError):
            current_score = 0
        existing_reasons = [reason for reason in top_reasons if isinstance(reason, str)]

        if not has_news_reference:
            card["stance"] = "hold"
            card["confidence"] = min(current_confidence, 0.35)
            card["score"] = 0
            card["requested_action"] = {
                "preference": "hold",
                "avoid_if": "핵심 뉴스 근거가 부족하면 방향성 판단을 보류",
            }
            guard_reason = "핵심 뉴스 근거가 약해 방향성 판단을 보류합니다."
            card["top_reasons"] = [guard_reason, *existing_reasons][:3]
            return card

        # 뉴스 근거가 1건뿐이어도 방향성이 명확하면 약한 의견은 허용하되,
        # 과도한 확신과 strong stance는 제한합니다.
        if stance == "strong_buy":
            card["stance"] = "buy"
        elif stance == "strong_sell":
            card["stance"] = "sell"

        card["confidence"] = min(current_confidence, 0.55)
        if current_score > 0:
            card["score"] = min(current_score, 12)
        elif current_score < 0:
            card["score"] = max(current_score, -12)
        else:
            card["score"] = 0
        card["requested_action"] = {
            "preference": "buy" if card["stance"] in {"strong_buy", "buy"} else "sell",
            "avoid_if": "핵심 뉴스의 후속 확인이 부족하면 비중을 낮춰 접근",
        }
        guard_reason = "핵심 뉴스 근거가 제한적이어서 확신도와 점수를 보수적으로 낮췄습니다."
        card["top_reasons"] = [guard_reason, *existing_reasons][:3]
        return card

    def generate_response(
        self,
        question: str,
        news_docs: List[Document],
        community_docs: Optional[List[Document]] = None,
    ) -> str:
        normalized_community_docs = community_docs or []
        if not news_docs and not normalized_community_docs:
            return "관련 정보를 찾지 못해 분석을 생성할 수 없습니다."

        context = self._build_response_context(news_docs, normalized_community_docs)
        response = self.chain.invoke({"context": context, "question": question})

        footer = "\n\n[참조 출처 리스트]\n"
        for i, doc in enumerate(news_docs or []):
            footer += f"[{i+1}] [뉴스] {doc.metadata.get('title', '')} ({doc.metadata.get('published_at', '시간 미상')})\n"
        for i, doc in enumerate(normalized_community_docs):
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
            return self._build_empty_analysis_card(
                ticker=ticker,
                reason="분석 가능한 뉴스/커뮤니티 데이터가 없습니다.",
                risk_flag="no_data",
            )

        if not news_docs and community_docs:
            return self._build_empty_analysis_card(
                ticker=ticker,
                reason="뉴스 근거가 없어 커뮤니티만으로는 방향성 판단을 보류합니다.",
                risk_flag="no_news_core_evidence",
            )

        context = self._build_card_context(news_docs, community_docs)

        card: Dict[str, Any] | None = None
        last_error: Exception | None = None
        last_raw = ""
        payload = {
            "question": question,
            "ticker": ticker,
            "news_count": len(news_docs),
            "community_count": len(community_docs),
            "context": context,
        }

        for attempt in range(2):
            try:
                raw = self.card_chain.invoke(payload)
                last_raw = str(raw)
                if not last_raw.strip():
                    raise ValueError("empty_response")
                card = _load_json_object(last_raw)
                break
            except Exception as exc:
                last_error = exc
                logger.warning(
                    "news analysis card parsing failed | attempt=%s error=%s raw=%r",
                    attempt + 1,
                    exc,
                    last_raw[:500],
                )

        if card is None:
            card = self._build_empty_analysis_card(
                ticker=ticker,
                reason="뉴스 에이전트 분석 응답 파싱 실패",
                risk_flag="agent_failure",
            )
            if last_error is not None:
                card["risk_flags"].append(f"parse_error:{type(last_error).__name__}")

        normalized = self._normalize_card_payload(card, ticker=ticker)
        return self._enforce_news_evidence_guard(normalized, news_docs=news_docs)
