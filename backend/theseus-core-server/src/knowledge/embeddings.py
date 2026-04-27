from abc import ABC, abstractmethod
from typing import List
from src.config import settings

class EmbeddingProvider(ABC):
    @abstractmethod
    def embed_query(self, text: str) -> List[float]:
        pass
    
    @abstractmethod
    def embed_documents(self, texts: List[str]) -> List[List[float]]:
        pass

class SentenceTransformerEmbeddingProvider(EmbeddingProvider):
    def __init__(self, model_name: str = "all-MiniLM-L6-v2"):
        try:
            from sentence_transformers import SentenceTransformer
            self.model = SentenceTransformer(model_name)
        except ImportError:
            raise ImportError("sentence-transformers is not installed.")
            
    def embed_query(self, text: str) -> List[float]:
        return self.model.encode(text).tolist()
        
    def embed_documents(self, texts: List[str]) -> List[List[float]]:
        return self.model.encode(texts).tolist()

class OpenAIEmbeddingProvider(EmbeddingProvider):
    def __init__(self, model_name: str = "text-embedding-3-small"):
        from langchain_openai import OpenAIEmbeddings
        if not settings.OPENAI_API_KEY:
            raise ValueError("OPENAI_API_KEY is not set.")
        self.embeddings = OpenAIEmbeddings(
            openai_api_key=settings.OPENAI_API_KEY,
            model=model_name
        )
        
    def embed_query(self, text: str) -> List[float]:
        return self.embeddings.embed_query(text)
        
    def embed_documents(self, texts: List[str]) -> List[List[float]]:
        return self.embeddings.embed_documents(texts)

def get_embedding_provider() -> EmbeddingProvider:
    if settings.EMBEDDING_PROVIDER.lower() == "remote":
        return OpenAIEmbeddingProvider(model_name=settings.EMBEDDING_MODEL)
    else:
        return SentenceTransformerEmbeddingProvider(model_name=settings.EMBEDDING_MODEL)
