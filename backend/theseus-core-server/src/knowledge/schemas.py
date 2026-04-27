from pydantic import BaseModel, Field
from typing import Optional, Dict, Any, List
from datetime import datetime

class KnowledgeDocumentBase(BaseModel):
    project_id: str
    source_type: str
    source_uri: str
    title: str

class KnowledgeDocumentCreate(KnowledgeDocumentBase):
    pass

class KnowledgeDocumentResponse(KnowledgeDocumentBase):
    id: str
    created_at: datetime

    class Config:
        from_attributes = True

class KnowledgeChunkBase(BaseModel):
    project_id: str
    document_id: str
    chunk_index: int
    content: str
    metadata_json: Optional[Dict[str, Any]] = None

class KnowledgeChunkCreate(KnowledgeChunkBase):
    embedding: List[float]

class KnowledgeChunkResponse(KnowledgeChunkBase):
    id: str
    created_at: datetime

    class Config:
        from_attributes = True

class KnowledgeSearchResult(BaseModel):
    chunk_id: str
    document_id: str
    title: str
    source_uri: str
    content: str
    metadata_json: Optional[Dict[str, Any]] = None
    similarity_score: float
