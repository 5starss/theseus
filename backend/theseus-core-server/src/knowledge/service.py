from typing import List
from sqlalchemy.orm import Session
from src.knowledge.embeddings import get_embedding_provider
from src.knowledge.repository import KnowledgeRepository
from src.knowledge.schemas import KnowledgeSearchResult
from src.config import settings

class KnowledgeService:
    def __init__(self, db: Session):
        self.db = db
        self.repository = KnowledgeRepository(db)
        self.embedding_provider = get_embedding_provider()

    def search_knowledge(self, project_id: str, query: str, top_k: int = None) -> List[KnowledgeSearchResult]:
        if top_k is None:
            top_k = settings.RAG_TOP_K
            
        # 1. 쿼리 임베딩 생성
        query_embedding = self.embedding_provider.embed_query(query)
        
        # 2. 유사도 검색 수행
        results = self.repository.search_similar_chunks(
            project_id=project_id,
            query_embedding=query_embedding,
            top_k=top_k,
            min_score=settings.RAG_MIN_SCORE
        )
        
        # 3. 결과 포맷팅
        search_results = []
        for chunk, document, score in results:
            search_results.append(
                KnowledgeSearchResult(
                    chunk_id=chunk.id,
                    document_id=document.id,
                    title=document.title,
                    source_uri=document.source_uri,
                    content=chunk.content,
                    metadata_json=chunk.metadata_json,
                    similarity_score=score
                )
            )
            
        return search_results
