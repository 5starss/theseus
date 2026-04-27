import uuid
from typing import List, Dict, Any, Tuple
from sqlalchemy.orm import Session
from sqlalchemy import select
from src.db.models import KnowledgeDocument, KnowledgeChunk
from src.knowledge.schemas import KnowledgeDocumentCreate, KnowledgeChunkCreate

class KnowledgeRepository:
    def __init__(self, db: Session):
        self.db = db

    def create_document(self, doc_data: KnowledgeDocumentCreate) -> KnowledgeDocument:
        doc_id = str(uuid.uuid4())
        db_doc = KnowledgeDocument(
            id=doc_id,
            project_id=doc_data.project_id,
            source_type=doc_data.source_type,
            source_uri=doc_data.source_uri,
            title=doc_data.title
        )
        self.db.add(db_doc)
        self.db.commit()
        self.db.refresh(db_doc)
        return db_doc

    def bulk_insert_chunks(self, chunks_data: List[KnowledgeChunkCreate]) -> None:
        db_chunks = [
            KnowledgeChunk(
                id=str(uuid.uuid4()),
                project_id=chunk.project_id,
                document_id=chunk.document_id,
                chunk_index=chunk.chunk_index,
                content=chunk.content,
                metadata_json=chunk.metadata_json,
                embedding=chunk.embedding
            )
            for chunk in chunks_data
        ]
        self.db.add_all(db_chunks)
        self.db.commit()

    def search_similar_chunks(
        self, 
        project_id: str, 
        query_embedding: List[float], 
        top_k: int = 5,
        min_score: float = 0.5
    ) -> List[Tuple[KnowledgeChunk, KnowledgeDocument, float]]:
        """
        주어진 벡터와 가장 유사한 Chunk들을 반환합니다.
        Cosine Distance를 사용하여 유사도를 계산합니다.
        (1 - Cosine Distance = Cosine Similarity)
        """
        # pgvector의 l2_distance (<->), max_inner_product (<#>), cosine_distance (<=>)
        # 보통 cosine_distance를 많이 사용합니다.
        
        similarity = 1 - KnowledgeChunk.embedding.cosine_distance(query_embedding)
        
        stmt = (
            select(KnowledgeChunk, KnowledgeDocument, similarity.label('similarity_score'))
            .join(KnowledgeDocument, KnowledgeChunk.document_id == KnowledgeDocument.id)
            .filter(KnowledgeChunk.project_id == project_id)
            .filter(similarity >= min_score)
            .order_by(KnowledgeChunk.embedding.cosine_distance(query_embedding))
            .limit(top_k)
        )
        
        results = self.db.execute(stmt).all()
        return results
