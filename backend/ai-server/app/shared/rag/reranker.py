import logging
import os
import time
from typing import List

import numpy as np
from langchain_core.documents import Document as LangChainDocument
from langchain_core.output_parsers import JsonOutputParser
from langchain_core.prompts import ChatPromptTemplate
from langchain_openai import ChatOpenAI

from app.shared.rag.embedder import UpstageEmbedder

logger = logging.getLogger(__name__)


def build_llm_rerank_prompt() -> ChatPromptTemplate:
    return ChatPromptTemplate.from_messages(
        [
            (
                "system",
                """
                당신은 정보 검색 전문가입니다.
                질문(Query)과 문서(Document) 목록을 비교해 각 문서의 관련성을 0~1 점수로 평가하세요.
                반드시 JSON 리스트로만 응답하세요.
                형식 예시:
                [{{"index": 0, "score": 0.9, "reason": "..."}}]
                """,
            ),
            ("human", "질문: {query}\n\n문서 목록:\n{documents}"),
        ]
    )


class SolarReranker:
    """질문-문서 관련성을 LLM으로 재정렬합니다."""

    @staticmethod
    def deduplicate_documents(
        documents: List[LangChainDocument],
        threshold: float = 0.9,
    ) -> List[LangChainDocument]:
        if not documents:
            return []

        embedder = UpstageEmbedder()
        doc_embeddings = [np.array(emb) for emb in embedder.embed_documents([doc.page_content for doc in documents])]
        reranker = SolarReranker.__new__(SolarReranker)
        unique_docs, _ = reranker._remove_redundancy(documents, doc_embeddings, threshold=threshold)
        return unique_docs

    def __init__(self, llm_model: str = "gpt-4.1-nano"):
        self.embedder = UpstageEmbedder()
        api_key = os.getenv("GMS_API_KEY")
        self.llm = ChatOpenAI(
            model=llm_model,
            openai_api_key=api_key,
            openai_api_base="https://gms.ssafy.io/gmsapi/api.openai.com/v1",
        )
        self.chain = build_llm_rerank_prompt() | self.llm | JsonOutputParser()

    def _remove_redundancy(
        self,
        documents: List[LangChainDocument],
        embeddings: List[np.ndarray],
        threshold: float = 0.9,
    ) -> tuple[List[LangChainDocument], List[np.ndarray]]:
        if len(documents) <= 1:
            return documents, embeddings

        unique_docs: List[LangChainDocument] = []
        unique_embeddings: List[np.ndarray] = []

        for doc, emb in zip(documents, embeddings):
            is_redundant = False
            for kept_emb in unique_embeddings:
                norm_kept = np.linalg.norm(kept_emb)
                norm_current = np.linalg.norm(emb)
                if norm_kept > 0 and norm_current > 0:
                    similarity = float(np.dot(kept_emb, emb) / (norm_kept * norm_current))
                    if similarity > threshold:
                        is_redundant = True
                        break

            if not is_redundant:
                unique_docs.append(doc)
                unique_embeddings.append(emb)

        logger.info("중복 제거 결과: %s건 -> %s건", len(documents), len(unique_docs))
        return unique_docs, unique_embeddings

    def rerank(self, query: str, documents: List[LangChainDocument], top_n: int = 5) -> List[LangChainDocument]:
        if not documents:
            return []

        doc_texts = [doc.page_content for doc in documents]
        doc_embeddings = [np.array(emb) for emb in self.embedder.embed_documents(doc_texts)]
        dedup_docs, _ = self._remove_redundancy(documents, doc_embeddings, threshold=0.9)
        doc_payload = "\n".join(f"[{idx}] {doc.page_content}" for idx, doc in enumerate(dedup_docs))

        start_ts = time.perf_counter()
        response = self.chain.invoke({"query": query, "documents": doc_payload})
        elapsed = time.perf_counter() - start_ts
        logger.info("[API 시간] LLM 리랭커(%s): %.2f초", self.llm.model_name if self.llm else "unknown", elapsed)

        if not isinstance(response, list):
            logger.warning("LLM 리랭커 응답 형식 불일치, 원 순서 사용")
            return dedup_docs[:top_n]

        normalized = []
        for item in response:
            try:
                idx = int(item.get("index", 0))
            except (TypeError, ValueError):
                idx = 0
            try:
                score = float(item.get("score", 0.0))
            except (TypeError, ValueError):
                score = 0.0
            normalized.append({"index": idx, "score": score})

        normalized.sort(key=lambda item: item["score"], reverse=True)
        final_docs = []
        for item in normalized[:top_n]:
            idx = item["index"]
            if 0 <= idx < len(dedup_docs):
                doc = dedup_docs[idx]
                doc.metadata["rerank_score"] = round(item["score"], 4)
                doc.metadata["rerank_mode"] = "llm"
                final_docs.append(doc)
        return final_docs or dedup_docs[:top_n]
