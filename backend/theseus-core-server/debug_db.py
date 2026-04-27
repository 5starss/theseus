from src.db.postgres import SessionLocal
from src.knowledge.repository import KnowledgeRepository
from src.knowledge.embeddings import get_embedding_provider
from sqlalchemy import select
from src.db.models import KnowledgeChunk
from pgvector.sqlalchemy import Vector

def debug_db():
    db = SessionLocal()
    provider = get_embedding_provider()
    query = "Theseus가 뭐야?"
    query_emb = provider.embed_query(query)
    
    print(f"--- DB Debug Start ---")
    # 1. 전체 데이터 개수 확인
    count = db.query(KnowledgeChunk).count()
    print(f"Total chunks in DB: {count}")
    
    # 2. 유사도 필터 없이 전체 조회 (점수 확인용)
    similarity = 1 - KnowledgeChunk.embedding.cosine_distance(query_emb)
    stmt = select(KnowledgeChunk.content, similarity.label('score')).order_by(similarity.desc())
    results = db.execute(stmt).all()
    
    for row in results:
        print(f"Score: {row.score:.4f} | Content: {row.content[:50]}...")
    print(f"--- DB Debug End ---")
    db.close()

if __name__ == "__main__":
    debug_db()
