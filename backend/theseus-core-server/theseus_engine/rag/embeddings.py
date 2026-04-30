"""임베딩 프로바이더 모듈.

로컬(sentence-transformers)과 원격(OpenAI) 임베딩을
환경 설정에 따라 자동 선택합니다.
"""

from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from typing import List

from theseus_engine.rag.config import EmbeddingConfig

log = logging.getLogger(__name__)


class BaseEmbeddingProvider(ABC):
    """임베딩 프로바이더 추상 클래스."""

    @abstractmethod
    def embed_text(self, text: str) -> List[float]:
        """단일 텍스트를 벡터로 변환합니다.

        Args:
            text: 변환할 텍스트.

        Returns:
            임베딩 벡터 리스트.
        """

    @abstractmethod
    def embed_texts(
        self, texts: List[str],
    ) -> List[List[float]]:
        """다수의 텍스트를 벡터 배치로 변환합니다.

        Args:
            texts: 변환할 텍스트 리스트.

        Returns:
            임베딩 벡터 리스트의 리스트.
        """

    @property
    @abstractmethod
    def dimension(self) -> int:
        """임베딩 벡터의 차원 수."""


class LocalEmbeddingProvider(BaseEmbeddingProvider):
    """sentence-transformers 기반 로컬 임베딩 프로바이더.

    Args:
        model_name: HuggingFace 모델 식별자.
        expected_dimension: 기대 벡터 차원 수.
    """

    def __init__(
        self,
        model_name: str = "all-MiniLM-L6-v2",
        expected_dimension: int = 384,
    ) -> None:
        self._model_name = model_name
        self._expected_dimension = expected_dimension
        self._model = None

    def _load_model(self) -> None:
        """모델을 Lazy-load합니다."""
        if self._model is not None:
            return
        try:
            from sentence_transformers import (
                SentenceTransformer,
            )

            self._model = SentenceTransformer(
                self._model_name,
            )
            log.info(
                "[Embedding] Loaded local model: %s",
                self._model_name,
            )
        except ImportError as e:
            raise ImportError(
                "sentence-transformers 패키지가 "
                "설치되어 있지 않습니다. "
                "`pip install sentence-transformers`를 "
                "실행하세요."
            ) from e

    def embed_text(self, text: str) -> List[float]:
        """단일 텍스트를 벡터로 변환합니다."""
        self._load_model()
        vector = self._model.encode(
            text, normalize_embeddings=True,
        )
        return vector.tolist()

    def embed_texts(
        self, texts: List[str],
    ) -> List[List[float]]:
        """다수의 텍스트를 벡터 배치로 변환합니다."""
        self._load_model()
        vectors = self._model.encode(
            texts, normalize_embeddings=True,
        )
        return [v.tolist() for v in vectors]

    @property
    def dimension(self) -> int:
        """임베딩 벡터의 차원 수."""
        return self._expected_dimension


class RemoteEmbeddingProvider(BaseEmbeddingProvider):
    """OpenAI API 기반 원격 임베딩 프로바이더.

    Args:
        model_name: OpenAI 임베딩 모델 이름.
        expected_dimension: 기대 벡터 차원 수.
    """

    def __init__(
        self,
        model_name: str = "text-embedding-3-small",
        expected_dimension: int = 1536,
    ) -> None:
        self._model_name = model_name
        self._expected_dimension = expected_dimension
        self._client = None

    def _get_client(self) -> object:
        """OpenAI 클라이언트를 Lazy-load합니다."""
        if self._client is not None:
            return self._client
        try:
            import os

            from openai import OpenAI

            self._client = OpenAI(
                api_key=os.getenv("OPENAI_API_KEY"),
            )
            log.info(
                "[Embedding] Initialized OpenAI "
                "embedding client: %s",
                self._model_name,
            )
            return self._client
        except ImportError as e:
            raise ImportError(
                "openai 패키지가 설치되어 있지 않습니다. "
                "`pip install openai`를 실행하세요."
            ) from e

    def embed_text(self, text: str) -> List[float]:
        """단일 텍스트를 벡터로 변환합니다."""
        client = self._get_client()
        response = client.embeddings.create(
            input=text,
            model=self._model_name,
        )
        return response.data[0].embedding

    def embed_texts(
        self, texts: List[str],
    ) -> List[List[float]]:
        """다수의 텍스트를 벡터 배치로 변환합니다."""
        client = self._get_client()
        response = client.embeddings.create(
            input=texts,
            model=self._model_name,
        )
        return [
            item.embedding for item in response.data
        ]

    @property
    def dimension(self) -> int:
        """임베딩 벡터의 차원 수."""
        return self._expected_dimension


def create_embedding_provider(
    config: EmbeddingConfig,
) -> BaseEmbeddingProvider:
    """설정에 따라 적절한 임베딩 프로바이더를 생성합니다.

    Args:
        config: 임베딩 설정 객체.

    Returns:
        BaseEmbeddingProvider 구현체.

    Raises:
        ValueError: 알 수 없는 프로바이더 유형일 경우.
    """
    provider = config.provider.lower()

    if provider == "local":
        return LocalEmbeddingProvider(
            model_name=config.model,
            expected_dimension=config.dimension,
        )
    elif provider == "remote":
        return RemoteEmbeddingProvider(
            model_name=config.model,
            expected_dimension=config.dimension,
        )
    else:
        raise ValueError(
            f"Unknown EMBEDDING_PROVIDER: "
            f"'{config.provider}'. "
            f"Use 'local' or 'remote'."
        )
