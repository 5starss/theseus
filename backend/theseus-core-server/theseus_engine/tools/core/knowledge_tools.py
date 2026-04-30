"""Theseus Knowledge Base Tools: RAG-based search and ingestion."""

import logging
from pydantic import BaseModel, Field
from openharness.tools.base import BaseTool, ToolExecutionContext, ToolResult

log = logging.getLogger(__name__)

try:
    from theseus_engine.rag.service import get_rag_service
    _RAG_AVAILABLE = True
except ImportError:
    _RAG_AVAILABLE = False
    log.warning("RAG service unavailable (psycopg2/pgvector not installed). Knowledge tools will return errors at runtime.")


class SearchKnowledgeBaseInput(BaseModel):
    """Input for searching the knowledge base."""
    query: str = Field(description="The search query to find relevant information in the knowledge base.")
    top_k: int = Field(default=3, description="Number of top relevant results to return.")


class SearchKnowledgeBaseTool(BaseTool):
    """Search for relevant documents in the Theseus knowledge base using vector similarity."""
    name = "search_knowledge_base"
    description = "Searches the internal knowledge base for documents matching the query. Useful for retrieving company-specific docs, manuals, or past project info."
    input_model = SearchKnowledgeBaseInput
    permission_level = 1

    async def execute(self, arguments: SearchKnowledgeBaseInput, context: ToolExecutionContext) -> ToolResult:
        if not _RAG_AVAILABLE:
            return ToolResult(output="Knowledge base unavailable: psycopg2 not installed. Run: pip install psycopg2-binary", is_error=True)
        try:
            rag = get_rag_service()
            results = rag.search(arguments.query, top_k=arguments.top_k)
            
            if not results:
                return ToolResult(output="No relevant documents found in the knowledge base.")
            
            formatted = "\n\n".join([
                f"--- Result {i+1} (Score: {res['score']:.4f}) ---\n{res['content']}"
                for i, res in enumerate(results)
            ])
            return ToolResult(output=formatted)
        except Exception as e:
            log.error("Knowledge search failed: %s", e)
            return ToolResult(output=f"Error searching knowledge base: {e}", is_error=True)


class IngestDocumentInput(BaseModel):
    """Input for ingesting a document into the knowledge base."""
    content: str = Field(description="The text content to ingest.")
    metadata: dict = Field(default_factory=dict, description="Optional metadata (source, title, etc.).")


class IngestDocumentTool(BaseTool):
    """Ingest new text content into the Theseus knowledge base (Vector DB)."""
    name = "ingest_document"
    description = "Adds new information to the knowledge base. Use this to remember important project details or documentations for future sessions."
    input_model = IngestDocumentInput
    permission_level = 2

    async def execute(self, arguments: IngestDocumentInput, context: ToolExecutionContext) -> ToolResult:
        if not _RAG_AVAILABLE:
            return ToolResult(output="Knowledge base unavailable: psycopg2 not installed. Run: pip install psycopg2-binary", is_error=True)
        try:
            rag = get_rag_service()
            rag.ingest(arguments.content, metadata=arguments.metadata)
            return ToolResult(output="Successfully ingested document into the knowledge base.")
        except Exception as e:
            log.error("Knowledge ingestion failed: %s", e)
            return ToolResult(output=f"Error ingesting document: {e}", is_error=True)
