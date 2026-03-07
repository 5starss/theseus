import os
import time
import logging
from typing import List, Optional, Dict
from langchain_chroma import Chroma
from app.rag.embedder import UpstageEmbedder
from app.schemas import Document as AppDocument
from langchain_core.documents import Document as LangChainDocument
from rank_bm25 import BM25Okapi

# 로깅 설정
logger = logging.getLogger(__name__)

class NewsVectorDB:
    """
    텍스트 벡터 데이터를 저장하고 검색하는 '기억 장치' 역할을 합니다.
    기존 벡터 검색에 더해 키워드 기반의 BM25 검색을 결합한 하이브리드 검색을 지원하도록 업그레이드되었습니다.
    """
    def __init__(self, collection_name: str = "kis_news_titles"):
        base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "../.."))
        self.persist_directory = os.path.join(base_dir, "chroma_db")
        self.embedder = UpstageEmbedder()
        self.collection_name = collection_name
        
        # ChromaDB 초기화
        self.vector_store = Chroma(
            collection_name=self.collection_name,
            embedding_function=self.embedder.get_embedding_model(),
            persist_directory=self.persist_directory
        )
        self.bm25 = None
        self.all_docs = []

    def _prepare_bm25(self, documents: List[LangChainDocument]):
        """
        BM25 검색을 위한 인덱스를 준비합니다. 
        뉴스 제목을 형태소 분석 대신 간단하게 공백으로 토큰화하여 처리합니다.
        """
        if not documents:
            return
        
        self.all_docs = documents
        # 뉴스 제목(page_content)을 공백 기준으로 나눠서 가벼운 토큰화를 진행합니다.
        tokenized_corpus = [doc.page_content.split() for doc in documents]
        self.bm25 = BM25Okapi(tokenized_corpus)
        logger.info(f"BM25 인덱스 생성 완료 (문서 수: {len(documents)})")

    def _load_all_documents(self) -> List[LangChainDocument]:
        """
        ChromaDB에서 모든 문서를 직접 가져옵니다. BM25 인덱싱을 위해 필요합니다.
        """
        results = self.vector_store.get()
        docs = []
        for i in range(len(results['ids'])):
            docs.append(LangChainDocument(
                page_content=results['documents'][i],
                metadata=results['metadatas'][i]
            ))
        return docs

    def add_documents(self, documents: List[AppDocument]):
        """
        문서를 벡터 DB에 추가하고, BM25 인덱스도 갱신할 수 있도록 준비합니다.
        """
        if not documents:
            logger.warning("색인할 문서가 없습니다. (빈 리스트)")
            return
            
        lc_docs = [
            LangChainDocument(
                page_content=doc.body,
                metadata={
                    "id": doc.id,
                    "source": doc.source,
                    "published_at": doc.published_at,
                    "title": doc.title,
                    "url": doc.url,
                    "source_rank": doc.source_rank
                }
            )
            for doc in documents
        ]
        start_ts = time.perf_counter()
        self.vector_store.add_documents(lc_docs)
        elapsed = time.perf_counter() - start_ts
        logger.info(f"[API 시간] 벡터 색인(Chroma add_documents/임베딩 포함): {len(lc_docs)}건, {elapsed:.2f}초")
        logger.info(f"ChromaDB에 {len(lc_docs)}건 색인 완료.")
        
    def query(self, query_text: str, k: int = 5) -> List[LangChainDocument]:
        """기존의 단순 벡터 검색입니다."""
        start_ts = time.perf_counter()
        results = self.vector_store.similarity_search(query_text, k=k)
        elapsed = time.perf_counter() - start_ts
        logger.info(f"[API 시간] 벡터 검색(similarity_search/쿼리 임베딩 포함): k={k}, {elapsed:.2f}초")
        return results

    def hybrid_query(self, query_text: str, k: int = 5, source_filter: Optional[str] = None) -> List[LangChainDocument]:
        """
        벡터 검색(Dense)과 BM25 검색(Sparse)을 결합한 하이브리드 검색을 수행합니다.
        Reciprocal Rank Fusion(RRF) 알고리즘을 사용하여 순위를 재항목화합니다.
        
        Args:
            source_filter: 특정 출처만 검색 (예: 'KIS_NEWS', 'TOSS_COMMUNITY'). None이면 전체 검색.
        """
        # 1. 모든 문서를 로드하여 BM25 준비 (실제 서비스에서는 캐싱 필요)
        if not self.bm25:
            all_docs = self._load_all_documents()
            self._prepare_bm25(all_docs)

        if not self.bm25:
            return self.query(query_text, k=k)

        # 2. 벡터 검색 결과
        # source_filter가 지정되면 ChromaDB의 where 조건으로 출처별 필터링
        search_kwargs = {"k": k * 3}
        if source_filter:
            start_ts = time.perf_counter()
            vector_results = self.vector_store.similarity_search(
                query_text, k=k * 3,
                filter={"source": source_filter}
            )
            elapsed = time.perf_counter() - start_ts
        else:
            start_ts = time.perf_counter()
            vector_results = self.vector_store.similarity_search(query_text, k=k * 3)
            elapsed = time.perf_counter() - start_ts
        logger.info(
            f"[API 시간] 하이브리드 벡터 검색(similarity_search/쿼리 임베딩 포함)"
            f"{' [필터: ' + source_filter + ']' if source_filter else ''}: {elapsed:.2f}초"
        )
        
        # 3. BM25 검색 결과 (source_filter 적용)
        tokenized_query = query_text.split()
        bm25_scores = self.bm25.get_scores(tokenized_query)
        bm25_top_indices = sorted(range(len(bm25_scores)), key=lambda i: bm25_scores[i], reverse=True)
        
        bm25_results = []
        for i in bm25_top_indices:
            if bm25_scores[i] <= 0:
                continue
            doc = self.all_docs[i]
            if source_filter and doc.metadata.get('source') != source_filter:
                continue
            bm25_results.append(doc)
            if len(bm25_results) >= k * 3:
                break

        # 4. RRF (Reciprocal Rank Fusion) 결합
        rrf_scores = {}
        
        for rank, doc in enumerate(vector_results):
            doc_id = doc.metadata.get('id')
            rrf_scores[doc_id] = rrf_scores.get(doc_id, 0) + 1.0 / (rank + 60)
            
        for rank, doc in enumerate(bm25_results):
            doc_id = doc.metadata.get('id')
            rrf_scores[doc_id] = rrf_scores.get(doc_id, 0) + 1.0 / (rank + 60)

        sorted_ids = sorted(
            rrf_scores.keys(), 
            key=lambda x: rrf_scores[x], 
            reverse=True
        )[:k]
        
        # 최종 문서 리스트 구성
        id_to_doc = {doc.metadata.get('id'): doc for doc in vector_results + bm25_results}
        final_results = [id_to_doc[doc_id] for doc_id in sorted_ids if doc_id in id_to_doc]
        
        filter_label = f" [필터: {source_filter}]" if source_filter else ""
        logger.info(f"하이브리드 검색 완료{filter_label}: {len(final_results)}건 추출")
        return final_results

    def delete_collection(self):
        """데이터 초기화"""
        self.vector_store.delete_collection()
        self.vector_store = Chroma(
            collection_name=self.collection_name,
            embedding_function=self.embedder.get_embedding_model(),
            persist_directory=self.persist_directory
        )
        self.bm25 = None
        self.all_docs = []
