# 테세우스 (Theseus) - B2B AI Agent Platform Core

## 1. 개요

* **목표:** 엔터프라이즈 환경에서 보안 통제력을 갖추고 토큰 비용을 최적화할 수 있는 사내 맞춤형 AI 에이전트 시스템(Theseus)의 Python 코어 서버 구축.
* **주요 역할:**
  * **Theseus-Native 엔진**: OpenHarness 의존성을 완전히 제거하고 자체 QueryEngine, Tool Primitives, Stream Events를 갖춘 독립적인 에이전트 오케스트레이션 엔진
  * **RBAC 기반 툴 필터링**: 사용자 권한(Level)에 따른 동적 도구 주입으로 보안 강화 및 컨텍스트 압축
  * **메타-툴링 (Meta-Tooling)**: 자연어를 통한 툴 생성 파이프라인 (Planning -> Code Gen -> Validation)
  * **Direct SSE 스트리밍**: 클라이언트와의 실시간 통신 및 Zero-Trust 과금 처리
  * **KB 기반 RAG**: PostgreSQL(`pgvector`) 연동을 통한 사내 지식 베이스 시맨틱 검색
* **비고:** FastAPI 기반 Python 서버이며, 메인 비즈니스/인증을 담당하는 **Java Spring Boot 서버**의 제어 하에 Worker 및 Streaming End-point 역할을 수행합니다.

## 2. 개발 환경 및 공통 설정

* **언어:** Python 3.11 권장
* **서버 프레임워크:** FastAPI
* **환경 관리:** `uv` 패키지 매니저 기반 가상환경 및 의존성 관리 (속도 최적화)
* **컨테이너:** Docker (멀티스테이지 빌드, Python 3.11-slim) / DinD (Docker-in-Docker) 격리 실행
* **관측성 (Observability):** LangSmith (MVP 0순위 적용)

## 3. 사용할 라이브러리 (Tech Stack)

* **Web Framework:** `fastapi`, `uvicorn`, `pydantic` (엄격한 파라미터 검증)
* **Streaming & I/O:** `sse-starlette`, `httpx` (비동기 HTTP 통신)
* **Agent Engine:** `theseus_engine` (자체 구현 코어 엔진 — OpenHarness 의존성 없음)
* **LLM Clients:** `anthropic>=0.40.0`, `openai>=1.0.0` (직접 SDK 호출)
* **Vector DB / RAG:** `psycopg2`, `pgvector`, `sentence-transformers`, `langchain-core`
* **Tracing:** `langsmith`

## 4. 기능 상세 명세

### 4.1. RBAC 기반 프롬프트 필터링
* **역할:** 시스템에 로드되는 도구(Tool)들을 사용자의 권한(`permission_level`)에 따라 동적으로 필터링합니다.
* **효과:** 권한 밖의 작업을 원천 차단(보안 강화)하고, 프롬프트에 불필요한 도구 스키마가 주입되는 것을 막아 **토큰 소모량을 극적으로 절감**합니다.

### 4.2. 메타-툴링 & HITL 파이프라인 (Tool Maker)
* **역할:** 반복적인 복잡한 작업을 단일 캡슐화된 툴로 생성합니다.
* **Interactive Planning**: 코드를 즉시 생성하지 않고, 에이전트가 "구현 계획서"를 먼저 작성하여 사용자의 리뷰와 승인을 받습니다.
* **생명주기 (4단계 파이프라인)**: `Drafting` -> `Review` -> `Executing` -> `Verifying` (자동 검증 단계 추가를 통한 테스트 및 회귀 확인 필수)

### 4.3. 세분화된 자동 검증기 (Domain-Specific Validators)
* **역할:** 툴이 생성된 직후, 위험도와 용도에 따라 4가지 특화된 검증기가 코드를 1차 자동 스캔합니다.
  1. **Execution Validator**: 상태 변경(DB, API) 로직의 안전성 검증
  2. **Query Validator**: 데이터 조회 권한 및 부하 검증
  3. **Analysis Validator**: 정적 분석(AST), SQL Injection 등 취약점 탐지
  4. **Suggestion Validator**: 쿼리 리팩토링 및 성능 개선 제안 (코드 퀄리티 향상)

### 4.4. 다이렉트 스트리밍 및 Zero-Trust 과금 처리
* **역할:** 병목 현상 방지를 위해 클라이언트와 Python 코어가 직접 SSE 통신을 수행합니다.
* **안전한 정산**: 클라이언트를 거치지 않고, Python 서버에서 백그라운드 태스크(`BackgroundTasks`)를 통해 스트리밍 종료 직후 Spring Boot의 내부망 API로 토큰 소모량을 직접 전송합니다.

### 4.5. KB 기반 RAG 검색 도구
* **역할:** 에이전트가 필요 시 사내 위키나 과거 해결 사례를 스스로 검색(`search_knowledge_base`)합니다.
* **구조:** 스케일 아웃(Scale-out) 시 데이터 불일치를 막기 위해 독립된 중앙 PostgreSQL 서버(pgvector 활성화)를 바라봅니다.

---

## 5. 데이터 흐름 (Pipeline)

1. **Request (접속 및 인증):** 클라이언트가 Spring Boot에서 발급받은 '1회성 세션 토큰'을 들고 FastAPI `/stream` 엔드포인트로 연결을 요청합니다.
2. **Process (세션 초기화):** 
   * 토큰 검증 후 `user_level`, `project_id` 획득.
   * `custom_tools/{project_id}` 폴더에서 권한에 맞는 툴만 메모리에 동적 로드.
3. **Streaming (에이전트 실행):**
   * Theseus 자체 엔진(`run_query`)이 실행되며, LangSmith를 통해 모든 궤적이 추적됩니다.
   * RAG가 필요하면 `search_knowledge_base` 툴을 호출하여 중앙 PostgreSQL DB에서 임베딩 벡터 기반의 맥락을 가져옵니다.
   * LLM 응답 청크가 생성되는 즉시 클라이언트로 SSE 브로드캐스트됩니다.
4. **Post-Process (과금 및 유지보수):**
   * 스트리밍 종료 시 토큰 `usage` 정보가 Spring Boot 내부망으로 안전하게 전송됩니다.
   * 실행 중 사내 API 스펙 변경 등으로 툴 에러가 지속 발생하면 '자동 복구 제안' 파이프라인이 가동됩니다.

---

## 6. Quick Start (Usage)

### 6.1. 사전 요구사항

* **Python 3.11**
* **uv** (권장 패키지 매니저, `pip install uv`로 설치 가능)
* **Docker** (PostgreSQL 서버 및 배포용)

### 6.2. 리포지터리 클론 및 환경 구성

```bash
git clone <REPOSITORY_URL>
cd theseus-core

# 1. uv 가상환경 생성 및 활성화
uv venv --python 3.11
source .venv/bin/activate  # Windows: .venv\Scripts\activate

# 2. 의존성 설치
uv pip install -r requirements.txt
```

### 6.3. 환경 변수 설정 (`.env`)

프로젝트 루트에 `.env` 파일을 생성합니다.

```bash
# Tracing (MVP 0순위 필수)
LANGCHAIN_TRACING_V2=true
LANGCHAIN_ENDPOINT=https://api.smith.langchain.com
LANGCHAIN_API_KEY=<Your_LangSmith_API_Key>
LANGCHAIN_PROJECT=theseus-core

# Database Settings (PostgreSQL + pgvector)
POSTGRES_HOST=localhost
POSTGRES_PORT=15432
POSTGRES_DB=theseus_core
POSTGRES_USER=root
POSTGRES_PASSWORD=root
POSTGRES_SCHEMA=public

# RAG & Embeddings Settings
EMBEDDING_PROVIDER=local
EMBEDDING_MODEL=all-MiniLM-L6-v2
VECTOR_DIMENSION=384
RAG_TOP_K=5
RAG_MIN_SCORE=0.5

# Spring Boot Internal API
SPRING_BOOT_INTERNAL_URL=http://localhost:8080/internal/billing/usage
```

### 6.4. 서버 실행 (개발 모드)

```bash
uvicorn src.main:app --reload --host 0.0.0.0 --port 8000
```

### 6.5. DB 스키마 초기화

현재 Core Server는 Alembic 기반 마이그레이션이 아니라 SQLAlchemy 메타데이터의
`create_all()`로 필요한 테이블을 자동 생성합니다. 서버 시작 시 자동으로 실행되며,
수동 초기화가 필요하면 아래 스크립트를 사용할 수 있습니다.

```bash
python scratch/create_db.py
```

이 경로는 `tool_plans`를 포함한 Core Server 로컬 DB 테이블을 생성합니다.

---

## 7. 배포/운영 시 특이사항 (Porting Guide)

### 7.1. 샌드박스 기반 실행 격리 (Security)
* 사용자가 생성한 커스텀 `.py` 도구들은 메인 FastAPI 프로세스 메모리에 직접 로드되어 실행되어서는 안 됩니다.
* 프로덕션 환경에서는 툴 실행 요청 시 **Docker-in-Docker(DinD) 환경**이나 **Serverless Function (AWS Lambda 등)**을 통해 격리된(Sandboxed) 공간에서 원격 실행(Remote Execution)되도록 배포해야 합니다.

### 7.2. PostgreSQL 서버 분리
* 다중 FastAPI 컨테이너 스케일링을 위해 로컬 디렉토리 모드(`PersistentClient`)를 금지하고, 반드시 클라이언트-서버 모드(`HttpClient`)를 사용해 중앙 데이터베이스를 바라보도록 구성해야 합니다.

### 7.3. Zero-Trust 과금 아키텍처
* 토큰 소모량은 철저히 백엔드 내부망을 통해 전송되어야 합니다. 클라이언트에게 노출되거나 클라이언트가 API를 호출하게 해서는 안 됩니다.

---

## 8. 폴더 구조 (Directory Structure)

```plaintext
theseus-core/
├── theseus_engine/         # Theseus-Native 코어 엔진 및 에이전트 로직
│   ├── core/               # Engine Builder, Context Compressor 등 핵심 구성 요소
│   ├── engine/             # QueryEngine, Stream Events 등 자체 실행 엔진
│   ├── models/             # 상태, 세션, 메시지, RBAC 등 데이터 모델
│   ├── tools/              # 자체 Tool Primitives 및 기본 제공 도구 모음
│   ├── wrappers/           # LLM Clients, Hooks 등 외부 API/통제 로직 연동
│   └── custom_tools/       # 메타-툴링으로 생성된 동적 도구 격리 공간
├── theseus_cli/            # CLI 파서, UI, 의도 분류기(Intent) 등 독립 패키지
│   ├── commands.py         # 슬래시 명령어 라우터
│   ├── intent.py           # 다국어 지원 LLM 기반 승인 의도 분류기
│   ├── parsers.py          # 피드백 파싱 및 프롬프트 조립
│   └── ui.py               # UI 컴포넌트 렌더링
├── src/                    # FastAPI 엔드포인트 및 서버 뼈대
│   ├── main.py             # 다이렉트 SSE 스트리밍 엔드포인트
│   ├── auth/               # Spring Boot 연동 세션 토큰 검증 미들웨어
│   └── validators/         # 기능별 세분화된 도구 검증기 4종
├── scratch/                # 디버그 덤프 및 스크립트 공간
├── docs/                   # 프로젝트 관련 문서, CHANGELOG 등
├── theseus_cli.py          # CLI 엔트리포인트
├── Dockerfile              # FastAPI 및 프로덕션 환경 빌드 파일
├── requirements.txt        # 파이썬 의존성
└── README.md               # 현재 문서
```
---

## 9. 세부 업무 분장 (Task Division for 2 Developers)

프로젝트를 2인이 병렬로 개발할 수 있도록 인프라 통신망과 AI 에이전트 로직으로 분리하여 업무를 배분합니다.

### 👨‍💻 개발자 A: 플랫폼 & 인프라 엔지니어 (Platform & Infra)
FastAPI 서버 구축, Spring Boot와의 통신, Vector DB 연동 등 시스템의 '뼈대와 통신망'을 책임집니다.

* **API 서버 뼈대 구축 및 인증 (Core Server & Auth)**
  * Python 3.11 + `uv` 가상환경 세팅 및 `fastapi` 기반 기본 서버 구성.
  * Spring Boot 세션 토큰 검증 미들웨어(`src/auth/`) 및 권한 파싱 로직 구현.
* **다이렉트 스트리밍 및 과금 통신 (SSE & Billing)**
  * 클라이언트 대상 `/stream` GET 엔드포인트 구축 및 `StreamingResponse` 구현.
  * `BackgroundTasks`와 `httpx`를 사용한 Zero-Trust Server-to-Server 과금 로직 구현.
* **RAG 및 Vector DB 인프라 (Knowledge Base)**
  * PostgreSQL 도커 컨테이너 구축 및 FastAPI에서의 `HttpClient` 연동.
  * 지식 검색 도구 뼈대(`search_knowledge.py`) 작성 및 데이터 입출력 연동.
* **배포 및 샌드박스 인프라 (Security & Docker)**
  * FastAPI 서버를 위한 멀티스테이지 Dockerfile 작성.
  * DinD (Docker-in-Docker) 샌드박스 실행 환경 또는 Serverless 원격 실행 환경(Remote Execution) 인프라 구축.

### 👨‍💻 개발자 B: AI 에이전트 & 툴링 엔지니어 (AI & Tooling)
OpenHarness 엔진 래핑, 프롬프트 엔지니어링, 권한 필터링, 그리고 코드 검증을 책임집니다.

* **엔진 연동 및 관측성 (Engine & Observability)**
  * Theseus-native `QueryEngine`(`theseus_engine/engine/query_engine.py`) 실행 제너레이터(`run_query`)를 스트리밍 엔드포인트 내부에 연동.
  * 시스템 전반에 LangSmith `@traceable` 데코레이터를 주입하여 에이전트 궤적 완벽 추적.
* **동적 권한 필터링 로직 (RBAC Loader)**
  * `theseus_engine/custom_tools/` 폴더의 `.py` 파일들을 런타임에 동적으로 주입.
  * 유저의 `user_level`과 툴의 `permission_level`을 비교하여 권한 밖의 툴을 Drop하는 로직 구현.
* **메타-툴링 파이프라인 (Interactive Planning)**
  * `Drafting` -> `Review` -> `Executing` -> `Verifying` 4단계 상태 제어를 위한 State Machine 및 다국어 지원 파서 구축.
  * 코드를 바로 짜지 않고 구현 계획서를 먼저 출력하도록 시스템 프롬프트 및 JSON 스키마 엔지니어링.
  * `create_tool` 성공 시 자동 등록 알림 및 `/tools custom` 커맨드로 커스텀 툴 목록 조회 가능.
* **세분화된 자동 검증기 4종 (`src/validators/`)**
  * Execution & Query 검증기: DB/API 호출 안전성 및 권한 판별 로직 구현.
  * Analysis 검증기 (보안): `ast` 파싱을 통한 금지된 라이브러리(`os`, `subprocess`) 호출 및 취약점 방어 로직.
  * Suggestion 검증기 (퀄리티): 생성된 코드를 기반으로 Pythonic한 리팩토링 방안을 제시하는 프롬프트 작성.
