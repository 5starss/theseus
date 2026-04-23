# 테세우스(Theseus) 기술 구현안 및 환경 설정 가이드

이 문서는 기획 명세서를 바탕으로, 실제 **Python 3.11 환경**에서 OpenHarness 코어를 어떻게 수정하고 래핑(Wrapping)하여 테세우스 시스템을 구현할지에 대한 구체적인 코드 레벨의 가이드를 제공합니다.

---

## 1. 개발 및 빌드 환경 설정

OpenHarness 코어 래핑 및 Python MSA 서버 구축을 위한 환경 설정입니다.

### 1.1 uv 기반 환경 구성 (가장 권장됨 - 압도적 속도)
`uv`는 Rust로 작성된 Python 패키지 매니저로 개발 속도를 극대화합니다.
```bash
# 가상환경 생성 (Python 3.11 지정)
uv venv --python 3.11
# 가상환경 활성화 (Windows)
.venv\Scripts\activate
# 의존성 설치 (OpenHarness 포함)
uv pip install -r requirements.txt
```

### 1.2 Conda 기반 환경 구성
격리된 환경 관리가 익숙한 데이터/AI 엔지니어를 위한 세팅입니다.
```bash
conda create -n theseus_core python=3.11 -y
conda activate theseus_core
pip install -r requirements.txt
```

### 1.3 Docker 기반 최종 빌드 (프로덕션 배포용)
보안과 샌드박스 실행, 그리고 Spring Boot 백엔드와의 원활한 통신을 위해 컨테이너화합니다.
```dockerfile
# Dockerfile
FROM python:3.11-slim

WORKDIR /app

# uv 설치 (빌드 속도 최적화)
RUN pip install uv

# 의존성 복사 및 설치
COPY requirements.txt .
RUN uv pip install --system -r requirements.txt

# 커스텀 툴이 저장될 디렉토리 생성 및 권한 설정
RUN mkdir -p /app/custom_tools && chmod 755 /app/custom_tools

# 소스코드 복사
COPY src/ /app/src/

# Python Core API 서버 실행 (FastAPI 권장)
CMD ["uvicorn", "src.theseus.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

---

## 2. 핵심 기능별 구체적 구현안 (Python Core)

### 2.1 폴더 구조 및 동적 툴 로딩
기존 OpenHarness의 정적인 툴 로딩 방식을 동적 스캔 방식으로 개편해야 합니다.

```python
# src/theseus/core/tool_loader.py
import importlib.util
import os
from openharness.tools.base import BaseTool

def load_project_tools(project_id: str, user_level: int) -> list[BaseTool]:
    tools = []
    project_tool_path = f"/app/custom_tools/{project_id}/"
    
    # 디렉토리 내의 .py 파일을 스캔하여 동적으로 임포트
    for filename in os.listdir(project_tool_path):
        if filename.endswith(".py"):
            # importlib를 이용해 런타임에 모듈 로드
            spec = importlib.util.spec_from_file_location(filename[:-3], os.path.join(project_tool_path, filename))
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            
            # BaseTool을 상속받은 클래스 찾기
            for attr_name in dir(module):
                attr = getattr(module, attr_name)
                if isinstance(attr, type) and issubclass(attr, BaseTool) and attr is not BaseTool:
                    tool_instance = attr()
                    # RBAC 필터링: 사용자 등급이 툴 권한보다 높거나 같을 때만 로드
                    if tool_instance.permission_level <= user_level:
                        tools.append(tool_instance)
    return tools
```

### 2.2 Interactive Planning 루프 구현
단순한 챗봇이 아닌, "사용자 승인 대기(Human-in-the-loop)" 상태를 관리하는 State Machine을 구현해야 합니다.

*   **상태 관리**: 에이전트의 현재 상태를 `PLANNING`, `WAITING_USER_REVIEW`, `CODING`, `VALIDATING`으로 나눕니다.
*   **프롬프트 설계 (PLANNING 상태)**:
    ```markdown
    당신은 테세우스의 Tool Maker 에이전트입니다. 코드를 절대 바로 작성하지 마십시오.
    대신, 사용자의 요구사항을 분석하여 1단계부터 N단계까지의 [구현 계획서]를 작성하십시오.
    마지막에 "이 계획으로 진행할까요?"라고 물어보십시오.
    ```
*   **실행 로직**: 사용자가 "네" 또는 "승인"이라고 입력하면 백엔드에서 상태를 `CODING`으로 변경하고, 이전까지 작성된 계획서를 컨텍스트에 담아 코드를 작성하게 만듭니다.

### 2.3 세분화된 도구 검증기 (Domain-Specific Validators) 구현
보안과 퀄리티를 위해 AI가 작성한 코드를 단일 검증기가 아닌 4종(Execution, Query, Analysis, Suggestion)으로 나누어 다각도로 분석합니다.

```python
# src/validators/analysis_validator.py
import ast
from openharness.tools.base import BaseTool

class AnalysisValidatorTool(BaseTool):
    name = "validate_analysis_logic"
    description = "생성된 Python 코드의 문법, 취약점, SQL Injection 등을 스캔합니다."
    permission_level = 3
    
    def execute(self, code_string: str) -> str:
        try:
            # 1. 문법 검사 및 보안 임포트 차단
            tree = ast.parse(code_string)
            banned_modules = ['os', 'sys', 'subprocess', 'shutil']
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    for alias in node.names:
                        if alias.name in banned_modules:
                            return f"FAIL: 금지된 모듈({alias.name}) 임포트 시도 발견"
            
            # 2. 취약점 탐지 로직
            if "f\"SELECT" in code_string or "f'SELECT" in code_string:
                return "FAIL: SQL Injection 취약점 발견. Parameterized Query를 사용하세요."
                
            return "PASS: 분석 완료"
        except SyntaxError as e:
            return f"FAIL: 문법 오류 발생 - {str(e)}"
```

### 2.4 다이렉트 스트리밍 (Direct SSE) 및 Zero-Trust 과금 처리
트래픽 병목을 막기 위해 Spring Boot 서버를 바이패스하고 클라이언트가 Python 코어와 직접 통신합니다. 토큰 소모량은 클라이언트를 거치지 않고 내부망을 통해 직접 전송합니다.

*   **스트리밍 및 과금 구현 (SSE)**:
    ```python
    # src/theseus/main.py (FastAPI)
    from fastapi import FastAPI, Depends, HTTPException, BackgroundTasks
    from fastapi.responses import StreamingResponse
    import httpx
    
    app = FastAPI()
    
    async def report_usage_to_spring(project_id: str, user_level: int, usage_data: dict):
        # 내부망으로 직접 API 호출
        async with httpx.AsyncClient() as client:
            await client.post("http://spring-boot-server:8080/internal/billing/usage", json={
                "project_id": project_id,
                "user_level": user_level,
                "usage": usage_data
            })
    
    @app.get("/api/v1/agent/stream")
    async def stream_agent_response(token: str, background_tasks: BackgroundTasks):
        # 토큰 검증 및 세션 정보 획득 (구현 생략)
        session_data = await verify_temp_token(token)
        if not session_data: raise HTTPException(status_code=401)
            
        allowed_tools = load_project_tools(session_data["project_id"], session_data["user_level"])
        
        async def event_generator():
            usage_data = {}
            # 메타데이터 파싱이 포함된 제너레이터 가정
            async for chunk, meta in run_openharness_with_meta(session_data["prompt"], tools=allowed_tools):
                if chunk:
                    yield f"data: {chunk}\n\n"
                if meta and "usage" in meta:
                    usage_data = meta["usage"]
                    
            # 스트리밍 종료 시 과금 정보 안전 전송
            background_tasks.add_task(
                report_usage_to_spring, 
                session_data["project_id"], 
                session_data["user_level"], 
                usage_data
            )
                
        return StreamingResponse(event_generator(), media_type="text/event-stream")
    ```
