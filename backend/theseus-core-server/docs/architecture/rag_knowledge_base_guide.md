# 지식 베이스(KB) 및 RAG 아키텍처 가이드

**작성일**: 2026-04-28
**관련 세션**: Session 11 (Phase 4)

본 문서는 Theseus 에이전트가 사내 지식 베이스를 활용할 수 있도록 구축된 **PostgreSQL 기반 RAG (Retrieval-Augmented Generation)** 시스템의 아키텍처와 주요 구성 요소에 대해 설명합니다.

---

## 1. 아키텍처 개요 (Architecture Overview)

기존 `ChromaDB` 사용 계획에서 **`PostgreSQL + pgvector`**로 아키텍처를 변경하여, 관계형 데이터와 벡터 데이터를 단일 데이터베이스에서 관리하도록 설계되었습니다. 이를 통해 트랜잭션 무결성을 유지하고 운영 복잡성을 낮췄습니다.

### 전체 흐름 (Pipeline)

1.  **문서 적재 (Ingestion)**: 사용자가 문서를 시스템에 전달하면 (`ingest_document` 도구 사용).
2.  **청킹 및 임베딩 (Chunking & Embedding)**: `RAGService`가 텍스트를 의미 단위(문장 경계 및 오버랩)로 분할(Chunking)하고, `EmbeddingProvider`를 통해 임베딩 벡터로 변환합니다.
3.  **데이터 저장 (Storage)**: `DatabaseManager`가 벡터와 원본 텍스트, 메타데이터를 PostgreSQL의 `knowledge_documents` 테이블에 적재합니다.
4.  **유사도 검색 (Retrieval)**: 에이전트가 지식이 필요할 때 (`search_knowledge_base` 도구 사용), 질문을 벡터화한 뒤 데이터베이스에서 코사인 유사도(Cosine Similarity)를 기준으로 가장 관련성 높은 문서를 검색해 컨텍스트로 반환합니다.

---

## 2. 핵심 모듈 구성 (`theseus_engine/rag/`)

| 파일명 | 역할 및 특징 |
| :--- | :--- |
| **`config.py`** | `.env` 환경 변수에서 데이터베이스, 임베딩 모델, RAG 검색 조건(Top-K, Min-Score) 등을 로드하는 불변 `dataclass`를 제공합니다. |
| **`database.py`** | PostgreSQL `psycopg2` 연결, `pgvector` 확장 로드, `knowledge_documents` 테이블 및 `IVFFlat` 인덱스 생성, 벡터 CRUD 기능을 담당합니다. `<=>` 연산자를 사용하여 코사인 유사도를 계산합니다. |
| **`embeddings.py`** | 임베딩 제공자에 대한 추상화 클래스(`BaseEmbeddingProvider`)입니다. `sentence-transformers`를 이용한 로컬 임베딩(`LocalEmbeddingProvider`)과 OpenAI API를 이용한 원격 임베딩(`RemoteEmbeddingProvider`)을 지원하며, Lazy-Loading을 통해 메모리를 최적화합니다. |
| **`service.py`** | `DatabaseManager`와 `EmbeddingProvider`를 결합하여 문서 청킹, 임베딩, DB 적재, 그리고 유사도 검색을 수행하는 RAG 비즈니스 로직의 진입점(Facade)입니다. |

---

## 3. 에이전트 도구 (Agent Tools)

에이전트는 `theseus_engine/tools/knowledge_tool.py`에 정의된 2개의 도구를 통해 지식 베이스와 상호작용합니다.

### 3.1. `search_knowledge_base` (권한: RBAC Lv.1)
-   **용도**: 자연어 쿼리를 사용하여 사내 규정, API 명세, 문제 해결 가이드 등을 검색합니다.
-   **특징**: 읽기 전용 도구(Read-only)이며, 에이전트가 특정 도메인 지식이 필요할 때 능동적으로 호출합니다.
-   **반환값**: 상위 K개의 문서 내용을 유사도 점수(Score)와 함께 반환합니다.

### 3.2. `ingest_document` (권한: RBAC Lv.2)
-   **용도**: 새로운 기술 문서나 가이드를 시스템에 추가합니다.
-   **특징**: 청킹, 임베딩 생성, DB 적재 과정을 모두 자동화하여 처리합니다.
-   **파라미터**: `content` (문서 내용), `source` (출처 식별자), `tags` (분류 태그).

---

## 4. 환경 변수 설정

시스템 구동 전 `.env` 파일에 다음 설정이 필요합니다.

```env
# Database Settings (PostgreSQL + pgvector)
POSTGRES_HOST=localhost
POSTGRES_PORT=15432
POSTGRES_DB=theseus_core
POSTGRES_USER=root
POSTGRES_PASSWORD=root
POSTGRES_SCHEMA=public

# RAG & Embeddings Settings
EMBEDDING_PROVIDER=local           # 'local' (sentence-transformers) 또는 'remote' (OpenAI)
EMBEDDING_MODEL=all-MiniLM-L6-v2 # 사용할 임베딩 모델
VECTOR_DIMENSION=384               # 벡터 차원 (모델에 맞게 설정. OpenAI text-embedding-3-small의 경우 1536)
RAG_TOP_K=5                        # 검색 시 반환할 최대 문서 수
RAG_MIN_SCORE=0.5                  # 유의미하다고 판단할 최소 유사도 점수 (0~1)
```

## 5. 보안 및 데이터 무결성
-   모든 RAG 도구는 **RBAC (Role-Based Access Control)**의 통제를 받으며, 지정된 권한 레벨 이상의 사용자만 문서를 주입(`ingest`)할 수 있습니다.
-   유사도 검색은 SQL Injection을 방지하기 위해 `psycopg2`의 파라미터화된 쿼리(Parameterized Query)를 엄격히 준수합니다.

---

## 6. 향후 고도화 방안 (Advanced Strategies)
현재 시스템은 문장 경계 기반의 글자 수 자르기(Sliding Window Overlap) 방식을 사용하고 있으나, B2B 도메인의 복잡한 문맥 파악을 위해 다음과 같은 고도화 전략을 단계적으로 도입할 계획입니다.

### 6.1. Parent-Child Chunking (부모-자식 청킹)
- **개념**: 문서를 '작은 단위(자식)'로 쪼개어 임베딩/검색하되, 실제 LLM에게는 그 자식이 속해있던 '큰 문단(부모)' 전체를 컨텍스트로 넘겨줍니다.
- **기대 효과**: 벡터 검색의 높은 **정확도**와 LLM에게 필요한 충분한 **문맥(Context)**을 동시에 확보할 수 있습니다.

### 6.2. 하이브리드 검색 (메타데이터 필터링 결합)
- **개념**: 벡터 유사도 검색(`<=>`)을 수행하기 전, PostgreSQL의 관계형 특징을 살려 `metadata` JSON 컬럼을 기준으로 먼저 필터링(`WHERE metadata->>'domain' = 'auth'`)합니다.
- **기대 효과**: 엉뚱한 부서나 다른 도메인의 유사한 단어가 섞이는 것을 원천 차단하여 검색의 신뢰성을 극대화합니다.

### 6.3. 의미 기반 분할 (Semantic / Markdown Chunking)
- **개념**: 단순 글자 수가 아닌, 마크다운의 헤더(`#`, `##`)나 소스 코드의 `class`, `def` 단위를 인식하여 의미가 끊어지지 않게 분할합니다. (예: `Langchain`의 `MarkdownHeaderTextSplitter` 활용)
- **기대 효과**: API 명세서나 개발 가이드 적재 시, 함수 정의부와 매개변수 설명이 서로 다른 청크로 찢어져 문맥이 유실되는 문제를 방지합니다.
