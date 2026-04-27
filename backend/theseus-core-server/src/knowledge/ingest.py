import argparse
import sys
import uuid
from typing import List
from src.db.postgres import SessionLocal, engine, Base
from src.knowledge.embeddings import get_embedding_provider
from src.knowledge.repository import KnowledgeRepository
from src.knowledge.schemas import KnowledgeDocumentCreate, KnowledgeChunkCreate

def create_tables():
    """DB 테이블 생성 (마이그레이션 도구가 없을 때 임시 사용)"""
    Base.metadata.create_all(bind=engine)
    print("Tables created successfully.")

def chunk_text(text: str, chunk_size: int = 1000, overlap: int = 200) -> List[str]:
    """간단한 텍스트 청킹 로직"""
    chunks = []
    start = 0
    while start < len(text):
        end = start + chunk_size
        chunks.append(text[start:end])
        start += chunk_size - overlap
    return chunks

def ingest_file(file_path: str, project_id: str, source_type: str = "txt", title: str = None):
    """지정된 파일을 읽어 DB에 적재합니다."""
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            content = f.read()
    except Exception as e:
        print(f"Error reading file {file_path}: {e}")
        return

    if not title:
        title = file_path.split("/")[-1]

    db = SessionLocal()
    try:
        repo = KnowledgeRepository(db)
        provider = get_embedding_provider()

        # 1. Document 레코드 생성
        doc_data = KnowledgeDocumentCreate(
            project_id=project_id,
            source_type=source_type,
            source_uri=file_path,
            title=title
        )
        doc = repo.create_document(doc_data)
        print(f"Created Document: {doc.id} - {title}")

        # 2. Chunking
        texts = chunk_text(content)
        print(f"Created {len(texts)} chunks.")

        # 3. Embedding 생성
        print("Generating embeddings...")
        embeddings = provider.embed_documents(texts)

        # 4. Chunk 적재
        chunks_data = []
        for i, (text, emb) in enumerate(zip(texts, embeddings)):
            chunks_data.append(
                KnowledgeChunkCreate(
                    project_id=project_id,
                    document_id=doc.id,
                    chunk_index=i,
                    content=text,
                    embedding=emb
                )
            )
        
        repo.bulk_insert_chunks(chunks_data)
        print("Successfully ingested all chunks.")

    except Exception as e:
        print(f"Error during ingestion: {e}")
        db.rollback()
    finally:
        db.close()

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Knowledge Base Ingestion Script")
    parser.add_argument("--init-db", action="store_true", help="Initialize DB tables")
    parser.add_argument("--file", type=str, help="Path to text file to ingest")
    parser.add_argument("--project", type=str, help="Project ID to attach knowledge")
    parser.add_argument("--title", type=str, default="", help="Document title (optional)")
    
    args = parser.parse_args()

    if args.init_db:
        create_tables()
        sys.exit(0)
        
    if args.file and args.project:
        ingest_file(args.file, args.project, title=args.title)
    else:
        parser.print_help()
