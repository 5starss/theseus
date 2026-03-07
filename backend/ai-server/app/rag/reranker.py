import logging
import time
from typing import List

import numpy as np
from langchain_core.documents import Document as LangChainDocument
from langchain_core.output_parsers import JsonOutputParser
from langchain_core.prompts import ChatPromptTemplate
from langchain_upstage import ChatUpstage

from app.rag.embedder import UpstageEmbedder

logger = logging.getLogger(__name__)


class SolarReranker:
    """질문-문서 관련성을 LLM으로 재평가하고 중복 문서를 제거합니다."""

    def __init__(self):
        self.llm = ChatUpstage(model="solar-1-mini-chat")
        self.embedder = UpstageEmbedder()

        self.prompt = ChatPromptTemplate.from_messages(
            [
                (
                    "system",
                    """
                    당신은 정보 검색 전문가입니다.
                    질문(Query)과 문서(Document) 목록을 비교해 각 문서의 관련성을 0~1 점수로 평가하세요.
                    반드시 JSON 리스트로만 응답하세요.
                    형식 예시:
                    [{"index": 0, "score": 0.9, "reason": "..."}]
                    """,
                ),
                ("human", "질문: {query}\n\n문서 목록:\n{documents}"),
            ]
        )
        self.chain = self.prompt | self.llm | JsonOutputParser()

    def _remove_redundancy(self, documents: List[LangChainDocument], threshold: float = 0.9) -> List[LangChainDocument]:
        if len(documents) <= 1:
            return documents

        texts = [doc.page_content for doc in documents]
        start_ts = time.perf_counter()
        embeddings = self.embedder.embed_documents(texts)
        elapsed = time.perf_counter() - start_ts
        logger.info("[API 시간] 리랭커 중복제거 임베딩: %s건, %.2f초", len(texts), elapsed)

        unique_docs: List[LangChainDocument] = []
        kept_embeddings = []

        for doc, emb in zip(documents, embeddings):
            emb_arr = np.array(emb)
            is_redundant = False
            for kept_emb in kept_embeddings:
                norm_kept = np.linalg.norm(kept_emb)
                norm_current = np.linalg.norm(emb_arr)
                if norm_kept > 0 and norm_current > 0:
                    similarity = np.dot(kept_emb, emb_arr) / (norm_kept * norm_current)
                    if similarity > threshold:
                        is_redundant = True
                        break

            if not is_redundant:
                unique_docs.append(doc)
                kept_embeddings.append(emb_arr)

        logger.info("중복 제거 결과: %s건 -> %s건", len(documents), len(unique_docs))
        return unique_docs

    def rerank(self, query: str, documents: List[LangChainDocument], top_n: int = 5) -> List[LangChainDocument]:
        if not documents:
            return []

        documents = self._remove_redundancy(documents, threshold=0.9)
        doc_texts = "\n".join([f"[{i}] {doc.page_content}" for i, doc in enumerate(documents)])

        try:
            start_ts = time.perf_counter()
            response = self.chain.invoke({"query": query, "documents": doc_texts})
            elapsed = time.perf_counter() - start_ts
            logger.info("[API 시간] 리랭크 LLM 호출: %.2f초", elapsed)

            if not isinstance(response, list):
                logger.warning("리랭커 응답 형식 불일치, 원 순서 사용")
                return documents[:top_n]

            for item in response:
                try:
                    item["score"] = float(item.get("score", 0.0))
                except (ValueError, TypeError):
                    item["score"] = 0.0
                try:
                    item["index"] = int(item.get("index", 0))
                except (ValueError, TypeError):
                    item["index"] = 0

            scored_indices = {item.get("index") for item in response}
            for i in range(len(documents)):
                if i not in scored_indices:
                    response.append({"index": i, "score": 0.0, "reason": "LLM 미평가"})

            sorted_results = sorted(response, key=lambda x: x.get("score", 0.0), reverse=True)
            top_indices = [item["index"] for item in sorted_results[:top_n]]

            final_docs: List[LangChainDocument] = []
            for idx in top_indices:
                if 0 <= idx < len(documents):
                    doc = documents[idx]
                    score_info = next((item for item in sorted_results if item["index"] == idx), {})
                    doc.metadata["rerank_score"] = score_info.get("score", 0.0)
                    final_docs.append(doc)

            return final_docs
        except Exception as exc:
            logger.error("리랭킹 중 오류: %s", exc)
            return documents[:top_n]
