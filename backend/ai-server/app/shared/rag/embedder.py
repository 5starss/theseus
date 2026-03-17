import logging
import os
import time
from typing import List

from dotenv import load_dotenv
from langchain_openai import OpenAIEmbeddings

load_dotenv()
logger = logging.getLogger(__name__)


class UpstageEmbedder:
    """GMS 임베딩 래퍼."""

    def __init__(self):
        api_key = os.getenv("GMS_API_KEY")
        if not api_key:
            raise ValueError("GMS_API_KEY가 설정되어 있지 않습니다.")

        self.embeddings = OpenAIEmbeddings(
            model="text-embedding-3-large",
            openai_api_key=api_key,
            openai_api_base="https://gms.ssafy.io/gmsapi/api.openai.com/v1"
        )

    def embed_documents(self, texts: List[str]) -> List[List[float]]:
        start_ts = time.perf_counter()
        vectors = self.embeddings.embed_documents(texts)
        elapsed = time.perf_counter() - start_ts
        logger.info("[API 시간] 임베딩(embed_documents): %s건, %.2f초", len(texts), elapsed)
        return vectors

    def embed_query(self, text: str) -> List[float]:
        start_ts = time.perf_counter()
        vector = self.embeddings.embed_query(text)
        elapsed = time.perf_counter() - start_ts
        logger.info("[API 시간] 임베딩(embed_query): %.2f초", elapsed)
        return vector

    def get_embedding_model(self):
        return self.embeddings
