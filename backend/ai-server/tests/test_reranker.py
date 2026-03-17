import numpy as np
from langchain_core.documents import Document

from app.shared.rag.reranker import SolarReranker


def test_remove_redundancy_drops_near_duplicate_document():
    reranker = SolarReranker.__new__(SolarReranker)
    documents = [
        Document(page_content="doc1"),
        Document(page_content="doc2"),
        Document(page_content="doc3"),
    ]
    embeddings = [
        np.array([1.0, 0.0]),
        np.array([0.9999, 0.0001]),
        np.array([0.0, 1.0]),
    ]

    unique_docs, unique_embeddings = reranker._remove_redundancy(documents, embeddings, threshold=0.9)

    assert [doc.page_content for doc in unique_docs] == ["doc1", "doc3"]
    assert len(unique_embeddings) == 2
