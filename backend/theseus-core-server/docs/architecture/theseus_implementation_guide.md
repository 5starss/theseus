# 테세우스(Theseus) 구체적 구현 마스터 가이드

본 문서는 사내 맞춤형 AI 에이전트 통합 시스템 '테세우스(Theseus)' 구축을 위한 최종 마스터 구현 설계서입니다. OpenHarness 래핑부터 Spring Boot 백엔드 연동, RBAC 적용, 메타 툴링 자동화까지 모든 작업의 구체적인 방안을 담고 있습니다.

---

## 1. 빌드 환경 (Build Environment)

Python 3.11 환경을 코어로 하며, 프로덕션에서는 Docker를 통해 배포합니다.

*   **언어 및 코어 엔진**: Python 3.11 (OpenHarness 권장 사양)
*   **패키지 관리 및 가상 환경**: `uv` (빠른 의존성 해결 및 가상환경 구성) 또는 `Conda`
*   **컨테이너 및 배포**: Docker (멀티스테이지 빌드, Python 3.11-slim 사용)
*   **API 미들웨어**: FastAPI (Python 코어를 감싸 Spring Boot와 통신하는 래퍼 역할)
*   **메인 백엔드**: Java Spring Boot (비즈니스 로직, 인증, 프로젝트 관리 총괄)

---

## 2. 필요 의존성 (Required Dependencies)

Python Core (FastAPI 래퍼) 측에 추가로 필요한 의존성 목록입니다.

```toml
# pyproject.toml 또는 requirements.txt 추가 항목
fastapi>=0.100.0        # Spring Boot 연동을 위한 API 서버
uvicorn>=0.22.0         # FastAPI 실행 ASGI 서버
pydantic>=2.0.0         # 툴 생성 시 입력 파라미터 엄격 검증 및 가드레일 용도
langchain-core          # RAG 및 LangSmith 연동을 위한 규격
langsmith               # 에이전트 실행 궤적 및 토큰 소모량 로깅
sse-starlette           # FastAPI에서 SSE(Server-Sent Events) 스트리밍 구현
chromadb                # (추가) KB 기반 RAG 구축을 위한 로컬 Vector DB
sentence-transformers   # (추가) 텍스트 임베딩 처리를 위한 모델 라이브러리
```

---

## 3. 작업 폴더 구조 (Project Folder Structure)

OpenHarness 라이브러리를 의존성(`pip install openharness`)으로 설치하여 코어 엔진으로 활용하고, 테세우스 시스템만의 독립적인 래퍼(Wrapper) 구조를 설계합니다. 즉, OpenHarness 파일이 루트에 존재할 필요가 없습니다.

```text
theseus-core/
├── src/
│   ├── main.py             # FastAPI 엔드포인트 서버 (Spring Boot 통신용)
│   ├── auth/               # JWT 검증 등 Spring Boot 연동 미들웨어
│   ├── builder/            # Tool Maker 에이전트의 Planning & Code Gen 로직
│   └── validators/         # 기능별 세분화된 코드 검증/분석 로직
│       ├── execution_validator.py
│       ├── query_validator.py
│       ├── analysis_validator.py
│       └── suggestion_validator.py
├── basic_tools/                # 테세우스 기본 제공 도구 
│   └── search_knowledge.py     # KB 기반 RAG 검색 도구 (우선순위 상향)
├── custom_tools/               # 프로젝트별 생성된 도구 격리 공간
│   ├── project_A/
│   │   ├── custom_db_query.py  
│   │   └── daily_report.md     
│   └── project_B/
├── .openharness/               # 시스템 설정 및 상태 저장 폴더
│   └── tools/
│       └── pending/            # 1차 검증 통과 후 Admin 승인 대기 중인 코드
├── Dockerfile                  # FastAPI 및 환경 빌드 파일
└── pyproject.toml              # 파이썬 의존성 (openharness 포함)
```

---

## 4. 아이디어 구현 방안 (문서 - Conceptual)

1.  **RBAC (역할 기반 도구 제어)**
    *   모든 툴(`BaseTool`)에 `permission_level` 속성을 부여합니다.
    *   사용자 접속 시 해당 레벨을 검증하고 높은 권한의 툴은 메모리에 아예 적재하지 않습니다.
2.  **메타 툴링 파이프라인 (Interactive Planning -> Code -> HITL)**
    *   툴 생성 시 "계획서(Plan) 리뷰 -> 코드 생성 -> 세분화된 자동 검증 -> 관리자 승인(Approved)" 파이프라인을 거칩니다.
3.  **샌드박스 기반 실행 환경 (Sandboxed Execution)**
    *   **[중요]** AST 정적 분석만으로는 악의적인 우회 스크립트(`__import__('o'+'s')` 등)를 막을 수 없습니다. 따라서 실행 승인을 받은 커스텀 도구라도 실제 실행 시에는 권한이 극도로 제한된 **Docker-in-Docker(DinD) 컨테이너 내부**나 **WASM 샌드박스**에서 격리 구동되도록 Python 코어를 보강합니다.
4.  **툴 유지보수 및 자동 복구 (Tool Auto-Healing)**
    *   사내 API 스펙이나 DB 스키마가 변경되어 툴이 에러를 뿜을 경우, 실패율 모니터링을 통해 고장을 감지하고 에이전트가 "코드를 수정 제안"하는 라이프사이클 관리 루프를 구현합니다.
5.  **가드레일 및 다이렉트 스트리밍 통신**
    *   Pydantic을 통한 파라미터 강제 검증을 적용합니다.
    *   스트리밍 통신 시 Spring Boot를 거치지 않고, Python 코어(FastAPI)와 클라이언트가 **Direct SSE** 연결을 맺어 커넥션 풀 고갈을 방지합니다.

---

## 5. 아이디어 구현 방안 (코드 - Code Snippets)

### 5.1 RBAC 기반 동적 툴 로더
```python
# src/theseus/core/loader.py
import importlib.util, os
from openharness.tools.base import BaseTool

def load_allowed_tools(project_id: str, user_level: int) -> list[BaseTool]:
    allowed = []
    path = f"./custom_tools/{project_id}"
    for filename in os.listdir(path):
        if filename.endswith(".py"):
            spec = importlib.util.spec_from_file_location(filename[:-3], os.path.join(path, filename))
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            for attr in dir(module):
                cls = getattr(module, attr)
                if isinstance(cls, type) and issubclass(cls, BaseTool) and cls is not BaseTool:
                    tool_instance = cls()
                    if tool_instance.permission_level <= user_level:
                        allowed.append(tool_instance)
    return allowed
```

### 5.2 세분화된 도구 검증기 (Domain-Specific Validators)
생성된 도구를 단순히 하나의 툴로 검증하는 것이 아니라, 용도와 위험도에 따라 여러 검증 툴로 나누어 다각도로 분석합니다.

1. **Execution Validator Tool**: 배치 실행, DB 업데이트(INSERT/UPDATE/DELETE), API 호출 등 상태 변경이 일어나는 로직의 안전성을 검증합니다.
2. **Query Validator Tool**: SELECT 위주의 데이터 조회나 모니터링 쿼리의 효율성, 권한 침해 여부, 과도한 부하 여부를 체크합니다.
3. **Analysis Validator Tool (중요)**: Git Diff, 코드 정적 분석, SQL 분석, 보안 취약점(Injection 등) 탐지를 담당하는 분석기입니다.
4. **Suggestion Validator Tool (핵심 차별화)**: 단순 검증을 넘어, 작성된 코드나 쿼리의 리팩토링, 성능 개선 방향을 제안(Suggestion)하여 최종 코드가 더 높은 퀄리티를 갖게 만듭니다.

```python
# src/validators/analysis_validator.py (예시)
from openharness.tools.base import BaseTool

class AnalysisValidatorTool(BaseTool):
    name = "validate_analysis_logic"
    permission_level = 3
    
    def execute(self, code: str) -> str:
        # 1. 정적 분석 (AST)
        # 2. 취약점 탐지 (ex. raw SQL 쿼리 내 문자열 포매팅 검출)
        if "f\"SELECT" in code or "f'SELECT" in code:
            return "FAIL: SQL Injection 취약점 발견 (Raw String Formatting 사용됨). Parameterized Query를 사용하세요."
        return "PASS: 분석 완료"
```

### 5.3 클라이언트 - Python Core 다이렉트 스트리밍 (Direct SSE) 및 안전한 과금 처리
트래픽 병목을 막기 위해 Spring Boot 서버를 바이패스하고 클라이언트가 Python 코어와 직접 통신합니다. **단, 토큰 소모량과 같은 과금 데이터는 클라이언트를 믿지 않고(Zero-Trust) Python 백엔드에서 Spring Boot로 직접(Server-to-Server) 비동기 전송합니다.**

```python
# src/theseus/main.py
from fastapi import FastAPI, Depends, HTTPException, BackgroundTasks
from fastapi.responses import StreamingResponse
import httpx # 비동기 HTTP 통신

app = FastAPI()

async def report_usage_to_spring(project_id: str, user_level: int, usage_data: dict):
    # 내부망을 통해 Spring Boot의 토큰 과금 API를 직접 호출 (클라이언트 개입/변조 원천 차단)
    async with httpx.AsyncClient() as client:
        await client.post("http://spring-boot-server:8080/internal/billing/usage", json={
            "project_id": project_id,
            "user_level": user_level,
            "usage": usage_data
        })

async def verify_temp_token(token: str):
    # Spring Boot에서 발급한 1회성/단기 세션 토큰을 검증하고 
    # 해당하는 user_level과 project_id를 반환 (Redis 등 활용)
    pass

@app.get("/stream")
async def stream_agent(token: str, background_tasks: BackgroundTasks):
    session_data = await verify_temp_token(token)
    if not session_data: 
        raise HTTPException(status_code=401, detail="Invalid Session Token")
        
    tools = load_allowed_tools(session_data["project_id"], session_data["user_level"])
    
    async def event_generator():
        usage_data = {}
        # OpenHarness 엔진 실행 루프 연동 (메타데이터 추출 기능 추가 가정)
        async for chunk, meta in run_openharness_with_meta(session_data["prompt"], tools=tools):
            if chunk:
                yield f"data: {chunk}\n\n"
            if meta and "usage" in meta:
                usage_data = meta["usage"] # 마지막에 추출된 토큰 정보 캐싱
                
        # 스트리밍이 끝나면 백그라운드 태스크로 과금 정보를 안전하게 전송
        background_tasks.add_task(
            report_usage_to_spring, 
            session_data["project_id"], 
            session_data["user_level"], 
            usage_data
        )
            
    return StreamingResponse(event_generator(), media_type="text/event-stream")
```

### 5.4 KB 기반 RAG 검색 도구 (Knowledge Base RAG Tool)
에이전트가 사내 위키나 이전 세션의 지식을 스스로 검색할 수 있도록 지원하는 핵심 도구입니다. **스케일 아웃(Scale-out) 시 데이터 불일치를 방지하기 위해 로컬 파일 기반이 아닌 클라이언트-서버 구조로 연동합니다.**

```python
# basic_tools/search_knowledge.py
from openharness.tools.base import BaseTool
import chromadb

class SearchKnowledgeTool(BaseTool):
    name = "search_knowledge_base"
    description = "사내 프로젝트 위키 및 과거 해결 사례를 시맨틱 검색하여 반환합니다."
    permission_level = 1
    
    def execute(self, query: str, project_id: str) -> str:
        # Scale-out 대응을 위해 로컬 저장이 아닌 독립된 중앙 ChromaDB 서버 인스턴스에 연결
        client = chromadb.HttpClient(host="chroma-db-server", port=8000)
        collection = client.get_or_create_collection(name=f"kb_{project_id}")
        
        # 쿼리와 가장 유사한 상위 3개 문서 검색
        results = collection.query(query_texts=[query], n_results=3)
        
        if not results['documents'][0]:
            return "해당 쿼리와 관련된 지식을 찾을 수 없습니다."
            
        return "\n\n".join(results['documents'][0])
```

---

## 6. 작업 순서 (Workflow Steps)

1.  **환경 구성 및 MVP 코어 뼈대 (Week 1)**
    *   Python 3.11 기반 `uv` 가상환경 구축 및 `openharness` 패키지 설치.
    *   FastAPI 뼈대 생성 및 기존 엔진 연동 테스트.
    *   **LangSmith 추적(Tracing) 코드 초기 삽입 (MVP 0순위 적용)**: 초기부터 에이전트의 사고 흐름을 완벽히 모니터링하여 이후 검증 로직 개발 시 디버깅 활용.
2.  **RBAC 로직 및 KB 기반 RAG 파이프라인 구축 (Week 2)**
    *   `BaseTool` 수정 로직 주입 및 `custom_tools/{project}` 구조 세팅.
    *   `load_allowed_tools` 동적 로더 함수 작성.
    *   **VectorDB(ChromaDB) 세팅 및 `search_knowledge_base` RAG 도구 연동 (우선순위 상향 적용)**.
3.  **메타 툴링 파이프라인 및 세분화 검증기 구축 (Week 3)**
    *   Interactive Planning 모드 로직 분기.
    *   Execution, Query, Analysis, Suggestion 등 **세분화된 도구 검증기 4종** 설계 및 작성.
    *   Pending -> Approved 상태 관리를 위한 임시 격리 폴더 쓰기 로직 구현.
4.  **백엔드(Spring Boot) 연동 및 스트리밍 처리 (Week 4)**
    *   FastAPI의 `/stream` 엔드포인트와 Spring Boot의 실시간 토큰 전송 연동.
    *   웹 UI/CLI 연동 통합 테스트.
5.  **가드레일 및 최종 성능 튜닝 (Week 5)**
    *   Pydantic 입력 검증 로직 추가 및 도메인별 검증 도구 성능 고도화.

---

## 7. 검증 방법 (Verification Methods)

*   **RBAC 필터링 검증**: Spring Boot에서 `user_level=1`로 접속했을 때, `prompt_extract/` JSON 파일의 `tools` 목록에 Level 2 이상의 도구 스키마가 완벽히 누락되어 있는지 육안으로 확인.
*   **Validator 성능 검증**: 고의로 `import os; os.system('rm -rf /')`가 포함된 코드를 에이전트가 생성하게 유도한 뒤, `ToolValidator`가 이를 즉각 차단하여 `FAIL` 상태로 반환하는지 테스트.
*   **스트리밍 지연 테스트**: CLI 접속 후 응답이 시작되기까지의 TTFB(Time To First Byte)가 2초 미만인지 측정.

---

## 8. 작업 주요 내용 (Key Tasks)

*   OpenHarness 내부 `run_query` 루프를 해치지 않으면서 **외부 래퍼(FastAPI)에서 tools 인자를 동적으로 주입**하는 연결 고리 만들기.
*   Tool 생성 과정에서 곧바로 파이썬 코드를 내뱉지 않고 **"마크다운 기반의 계획서"를 먼저 출력하게 만드는 시스템 프롬프트 엔지니어링**.
*   Java Spring Boot가 Python FastAPI로 요청을 보낼 때 **JWT 등 인증 정보를 안전하게 넘기고 세션 상태를 유지하는 방법 확립**.

---

## 9. 확인 사항 (Checklist & Considerations)

*   [ ] **보안 이슈**: 1번 피드백에서 지적된 샌드박싱 로직 분리(Remote Execution 등)는 추후 최우선 보강 과제로 보류됨.
*   [ ] **토큰 추적 (결함 해결)**: 토큰 사용량을 클라이언트가 응답받아 보고하도록 하면 변조(어뷰징) 위험이 있습니다. SSE 스트리밍이 종료된 직후 FastAPI가 `BackgroundTasks`를 통해 Spring Boot 내부망 API로 과금 데이터를 직접 전송하는 **Zero-Trust Server-to-Server** 로직이 완벽히 적용되어 있습니까?
*   [ ] **Vector DB 스케일링 (결함 해결)**: 트래픽 급증으로 FastAPI 인스턴스가 여러 대로 증설(Scale-out)되었을 때, 로컬 `./vector_store` 경로를 참조하여 발생하는 지식 파편화 문제를 막기 위해 **ChromaDB 컨테이너를 단일 중앙 인스턴스(Http/gRPC 클라이언트)로 분리**했습니까?
