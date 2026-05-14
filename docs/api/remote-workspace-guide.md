# Remote Workspace 연동 및 사용 가이드

## 개념

Remote Workspace는 프로젝트가 대상으로 삼는 외부 서버 실행 환경이다.

```text
서버관리 프로젝트
-> 싸피증권 운영서버를 Remote Workspace로 등록
-> ASK / PLAN / AGENT / 생성 Tool 실행에서 선택
-> Core Server가 SSH로 운영서버에 접속
-> 파일, 로그, 리소스, 프로세스, 포트, 명령 결과를 분석
```

Remote Workspace는 ToolPlan 전용 참고자료가 아니다. 생성된 Theseus Tool과 AGENT가 실제 작업을 수행할 외부 서버 환경이다.

## 전체 구조

```text
FE
-> API Server
   - Remote Workspace 등록/조회/수정/삭제
   - 프로젝트 멤버 및 ADMIN 권한 검증
   - Remote Workspace 선택값을 ASK / PLAN / AGENT 요청에 포함
   - Core 연결 테스트 요청 중계

Core Server
   - Remote Workspace payload 수신
   - SSH Connector로 외부 서버 접속
   - basePath 안에서 read_file, glob, grep, bash 등 primitive 실행
   - 생성 Tool runtime helper에서 원격 명령 실행
```

## 역할 구분

| 구분 | 역할 |
| --- | --- |
| Remote Workspace | 프로젝트가 연결할 외부 서버와 작업 기준 경로 |
| Core 내부 primitive | `read_file`, `glob`, `grep`, `bash`, `write_file`, `edit_file` 같은 저수준 실행 재료 |
| Theseus Tool | 프로젝트 Tool 저장소에 저장되고 사용자가 호출하는 생성 Tool |
| ToolPlan | 승인 전 Tool 명세 |
| Tool build | 승인된 ToolPlan을 실제 Theseus Tool 코드로 만드는 과정 |

## 접속 단위와 credential

Remote Workspace는 고객사 환경 전체가 아니라 SSH로 접속 가능한 단일 실행 대상이다.

서버별 접속 키가 다르면 Remote Workspace도 분리해서 등록한다.

```text
싸피증권 운영서버 Remote Workspace
- host: ssafy-stock.kr
- privateKeyPath: 운영서버 접근 pem

싸피증권 DB 접근 서버 Remote Workspace
- host: DB Bastion 또는 DB 접근용 서버
- privateKeyPath: DB 접근 pem

싸피증권 Redis 접근 서버 Remote Workspace
- host: Redis Bastion 또는 Redis 접근용 서버
- privateKeyPath: Redis 접근 pem
```

하나의 요청에서 선택하는 기본 대상은 `remoteWorkspaceId` 하나다. App 서버, DB 서버, Redis 서버를 한 번에 묶어 분석해야 하는 흐름은 별도 workspace profile 또는 복수 workspace 선택 정책이 필요하다.

## API Server 저장 정보

`remote_workspaces`는 프로젝트 단위로 저장된다.

| 필드 | 설명 |
| --- | --- |
| `id` | Remote Workspace ID |
| `project_id` | 소속 프로젝트 ID |
| `created_by_project_member_id` | 등록한 프로젝트 멤버 ID |
| `name` | 화면 표시 이름 |
| `host` | SSH 접속 host |
| `port` | SSH 접속 port |
| `username` | SSH 사용자명 |
| `password` | password 인증 또는 private key passphrase |
| `private_key_path` | Core Server가 접근할 수 있는 private key 경로 |
| `base_path` | 원격 서버 작업 기준 절대경로 |
| `status` | `ACTIVE`, `DELETED` |

`password`는 응답 DTO에 포함되지 않는다. `privateKeyPath`는 응답에 포함되므로 운영 환경에서는 secret path만 저장하고 실제 key 내용은 별도 secret 관리 영역에 둔다.

## 권한

| 기능 | 권한 |
| --- | --- |
| 등록 | 프로젝트 `ADMIN` |
| 수정 | 프로젝트 `ADMIN` |
| 삭제 | 프로젝트 `ADMIN` |
| 연결 테스트 | 프로젝트 `ADMIN` |
| 목록 조회 | 프로젝트 활성 멤버 |
| 상세 조회 | 프로젝트 활성 멤버 |
| 채팅/PLAN 요청에서 선택 | 프로젝트 활성 멤버 |

프로젝트 멤버 상태는 `IN_PROGRESS`여야 한다.

## API 목록

모든 API는 인증 토큰을 사용한다.

```http
Authorization: Bearer {accessToken}
```

응답은 `ApiResponse<T>` 래퍼를 사용한다.

### Remote Workspace 등록

```http
POST /api/v1/projects/{projectId}/remote-workspaces
Content-Type: application/json
```

Request Body:

```json
{
  "name": "싸피증권 운영서버",
  "host": "ssafy-stock.kr",
  "port": 22,
  "username": "ubuntu",
  "password": null,
  "privateKeyPath": "/home/appuser/.ssh/ssafy-ec2-key.pem",
  "basePath": "/home/ubuntu"
}
```

Response Body:

```json
{
  "isSuccess": true,
  "code": "COMMON-201",
  "message": "성공입니다.",
  "result": {
    "remoteWorkspaceId": 1,
    "projectId": 1,
    "createdByProjectMemberId": 3,
    "name": "싸피증권 운영서버",
    "host": "ssafy-stock.kr",
    "port": 22,
    "username": "ubuntu",
    "privateKeyPath": "/home/appuser/.ssh/ssafy-ec2-key.pem",
    "basePath": "/home/ubuntu",
    "status": "ACTIVE",
    "createdAt": "2026-05-14T09:00:00",
    "updatedAt": "2026-05-14T09:00:00"
  }
}
```

### Remote Workspace 목록 조회

```http
GET /api/v1/projects/{projectId}/remote-workspaces
```

Response Body:

```json
{
  "isSuccess": true,
  "code": "COMMON-200",
  "message": "성공입니다.",
  "result": [
    {
      "remoteWorkspaceId": 1,
      "projectId": 1,
      "createdByProjectMemberId": 3,
      "name": "싸피증권 운영서버",
      "host": "ssafy-stock.kr",
      "port": 22,
      "username": "ubuntu",
      "privateKeyPath": "/home/appuser/.ssh/ssafy-ec2-key.pem",
      "basePath": "/home/ubuntu",
      "status": "ACTIVE",
      "createdAt": "2026-05-14T09:00:00",
      "updatedAt": "2026-05-14T09:00:00"
    }
  ]
}
```

### Remote Workspace 상세 조회

```http
GET /api/v1/projects/{projectId}/remote-workspaces/{remoteWorkspaceId}
```

### Remote Workspace 수정

```http
PATCH /api/v1/projects/{projectId}/remote-workspaces/{remoteWorkspaceId}
Content-Type: application/json
```

Request Body:

```json
{
  "name": "싸피증권 운영서버",
  "host": "54.180.80.22",
  "port": 22,
  "username": "ubuntu",
  "password": null,
  "privateKeyPath": "/home/appuser/.ssh/ssafy-ec2-key.pem",
  "basePath": "/home/ubuntu/app"
}
```

수정 요청에서 `null`이거나 누락된 필드는 기존 값을 유지한다. 빈 문자열은 유효하지 않다.

### Remote Workspace 삭제

```http
PATCH /api/v1/projects/{projectId}/remote-workspaces/{remoteWorkspaceId}/delete
```

삭제는 물리 삭제가 아니라 `status = DELETED` 전환이다.

### Remote Workspace 연결 테스트

```http
POST /api/v1/projects/{projectId}/remote-workspaces/{remoteWorkspaceId}/test-connection
```

API Server가 저장된 Remote Workspace 정보를 Core Server로 전달한다. Core Server는 SSH로 접속한 뒤 `basePath` 기준 `pwd` 명령을 실행한다.

Response Body:

```json
{
  "isSuccess": true,
  "code": "COMMON-200",
  "message": "성공입니다.",
  "result": {
    "remoteWorkspaceId": 1,
    "available": true,
    "message": "Remote Workspace connection succeeded."
  }
}
```

실패 예시:

```json
{
  "isSuccess": true,
  "code": "COMMON-200",
  "message": "성공입니다.",
  "result": {
    "remoteWorkspaceId": 1,
    "available": false,
    "message": "Failed to connect to remote workspace 1."
  }
}
```

## Core 내부 연결 테스트 API

API Server 내부 호출용 endpoint다.

```http
POST /api/v1/remote-workspaces/test-connection
Content-Type: application/json
```

Request Body:

```json
{
  "remoteWorkspaceId": 1,
  "projectId": 1,
  "name": "싸피증권 운영서버",
  "host": "ssafy-stock.kr",
  "port": 22,
  "username": "ubuntu",
  "password": null,
  "privateKeyPath": "/home/appuser/.ssh/ssafy-ec2-key.pem",
  "basePath": "/home/ubuntu",
  "status": "ACTIVE"
}
```

Core 응답은 snake_case를 사용한다.

```json
{
  "remote_workspace_id": 1,
  "available": true,
  "message": "Remote Workspace connection succeeded."
}
```

## ASK / PLAN / AGENT 요청 연결

FE 채팅 화면에서 Remote Workspace를 선택하면 요청에 `remoteWorkspaceId`가 포함된다.

### ASK / AGENT stream

API Server는 Core `/api/v1/stream`에 JSON body로 요청한다. Remote Workspace 상세 정보는 URL query가 아니라 body의 `remoteWorkspace` block으로 전달된다.

```json
{
  "mode": "AGENT",
  "prompt": "싸피증권 운영서버의 CPU와 메모리 상태를 점검해줘.",
  "chatSessionId": 5,
  "projectId": 1,
  "remoteWorkspaceId": 1,
  "remoteWorkspace": {
    "remoteWorkspaceId": 1,
    "projectId": 1,
    "name": "싸피증권 운영서버",
    "host": "ssafy-stock.kr",
    "port": 22,
    "username": "ubuntu",
    "password": null,
    "privateKeyPath": "/home/appuser/.ssh/ssafy-ec2-key.pem",
    "basePath": "/home/ubuntu",
    "status": "ACTIVE"
  }
}
```

### PLAN generate

```http
POST /api/v1/projects/{projectId}/sessions/{sessionId}/tool-plans/generate
Content-Type: application/json
```

Request Body:

```json
{
  "mode": "PLAN",
  "prompt": "싸피증권 운영서버의 리소스 병목을 점검하는 ToolPlan을 만들어줘.",
  "remoteWorkspaceId": 1
}
```

Kafka payload에는 `remoteWorkspaceId`와 `remoteWorkspace` block이 함께 포함된다.

### PLAN regenerate

```http
PATCH /api/v1/projects/{projectId}/sessions/{sessionId}/tool-plans/{toolPlanId}/regenerate
Content-Type: application/json
```

Request Body:

```json
{
  "mode": "PLAN",
  "basePlanVersion": 1,
  "instruction": "프로세스 점검 절차를 더 구체화해줘.",
  "feedbackItems": [
    {
      "blockId": "resource-check",
      "comment": "CPU, memory, disk, port 확인 명령을 분리해줘."
    }
  ],
  "remoteWorkspaceId": 1
}
```

## 모드별 Remote Workspace 사용 정책

| 모드 | Remote Workspace 사용 | 허용 primitive |
| --- | --- | --- |
| `ASK` | 선택 가능 | 읽기/분석 중심 |
| `PLAN` | 선택 가능 | ToolPlan 작성을 위한 읽기/분석 중심 |
| `AGENT` | 선택 가능 | 읽기/분석 + 쓰기/명령 실행 |
| 생성 Tool 실행 | 실행 context에 Remote Workspace가 있으면 사용 | Tool 구현과 권한에 따라 사용 |

`ASK`와 `PLAN`은 원격 서버를 분석 대상으로 사용할 수 있다. 원격 파일 수정, 임의 명령 실행, 패치 작업은 `AGENT` 또는 승인된 생성 Tool 실행에서 사용한다.

DB/Redis 접근은 별도 pem 또는 Bastion이 필요한 경우 별도 Remote Workspace로 등록한다. MVP 기준 DB/Redis는 조회와 진단 중심으로 사용한다. `UPDATE`, `DELETE`, `DROP`, `FLUSHALL`, `CONFIG SET`처럼 운영 데이터나 인프라 상태를 변경하는 작업은 별도 승인, allowlist, 감사 로그, rollback 정책이 마련되기 전까지 자동화 범위에 포함하지 않는다.

## Core primitive 연결

Remote Workspace가 선택되면 Core는 기존 tool name을 유지하면서 backend만 SSH 기반으로 바꾼다.

읽기/분석 primitive:

```text
read_file
glob
grep
bash
```

쓰기/명령 primitive:

```text
write_file
edit_file
bash
```

경로 접근은 `basePath` 내부로 제한된다. `../`, `/etc/passwd`처럼 `basePath` 밖으로 나가는 경로는 거부된다.

## 생성 Tool runtime helper

생성된 Theseus Tool은 직접 `paramiko`, `subprocess`, `os.system`을 사용하지 않고 Core helper를 사용한다.

```python
from src.remote_workspace.runtime import run_remote_command

result = run_remote_command(
    context,
    "df -h && free -m",
    cwd=".",
    timeout_seconds=180,
)
```

`context.metadata["remote_workspace"]`가 없으면 helper는 명확한 runtime error를 발생시킨다.

## 로컬 Docker 설정

Core Docker 환경에서 ToolPlan Kafka consumer와 vLLM 연결을 사용할 때 필요한 값이다.

```env
CORE_KAFKA_CONSUMER_ENABLED=true
CORE_TOOL_PLAN_CONSUMER_ENABLED=true
CORE_LEGACY_TOOL_GENERATION_CONSUMER_ENABLED=false
THESEUS_TOOL_PLAN_RUN_TIMEOUT_SCHEDULER_ENABLED=false

THESEUS_MODEL=vllm/{model-name}
OPENAI_BASE_URL=http://{vllm-server}/v1
OPENAI_API_KEY=vllm
```

`OPENAI_API_KEY=vllm`은 OpenAI-compatible vLLM 서버용 더미 값이다. `THESEUS_MODEL`은 `vllm/` prefix로 시작해야 vLLM 분기를 사용한다.

Docker 재기동:

```powershell
docker compose --env-file infra\docker\local\.env.local `
  -f infra\docker\local\docker-compose.infra.yml `
  -f infra\docker\local\docker-compose.core.yml `
  -f infra\docker\local\docker-compose.api.yml `
  up -d --build
```

## private key path 설정

FE에 입력하는 `privateKeyPath`는 사용자 PC 경로가 아니라 Core Server가 접근할 수 있는 경로다.

Windows PC의 key:

```text
C:\Users\SSAFY\.ssh\ssafy-ec2-key.pem
```

Core 컨테이너 내부 경로 예시:

```text
/home/appuser/.ssh/ssafy-ec2-key.pem
```

로컬 override compose 예시:

```yaml
services:
  theseus-core-server:
    volumes:
      - C:/Users/SSAFY/.ssh/ssafy-ec2-key.pem:/home/appuser/.ssh/ssafy-ec2-key.pem:ro
```

실행 시 override 파일을 함께 지정한다.

```powershell
docker compose --env-file infra\docker\local\.env.local `
  -f infra\docker\local\docker-compose.infra.yml `
  -f infra\docker\local\docker-compose.core.yml `
  -f infra\docker\local\docker-compose.api.yml `
  -f infra\docker\local\docker-compose.remote-workspace.override.yml `
  up -d --build
```

## 싸피증권 운영서버 등록 예시

```text
이름: 싸피증권 운영서버
Host: ssafy-stock.kr
Port: 22
Username: ubuntu
Password:
Private Key Path: /home/appuser/.ssh/ssafy-ec2-key.pem
Base Path: /home/ubuntu
```

IP로 직접 접속할 때는 `Host`에 `54.180.80.22`를 입력한다.

`basePath`는 반드시 원격 서버의 절대경로여야 한다. 처음에는 `/home/ubuntu`로 연결 테스트를 통과시킨 뒤 실제 서비스 경로로 좁힌다.

DB 또는 Redis가 운영서버와 다른 pem으로 접근되는 구조라면 운영서버 Remote Workspace를 재사용하지 않는다. DB/Redis 접근용 Bastion 또는 접근 서버를 별도 Remote Workspace로 등록하고, 해당 workspace를 선택한 요청에서는 조회와 진단 목적의 명령만 사용한다.

## FE 사용 절차

1. 프로젝트 설정으로 이동한다.
2. `Remote Workspace` 탭을 연다.
3. Remote Workspace 정보를 등록한다.
4. 연결 테스트를 실행한다.
5. 채팅 화면으로 이동한다.
6. 입력창 위 Remote Workspace 선택 박스에서 대상 서버를 선택한다.
7. `ASK`, `PLAN`, `AGENT` 중 하나를 선택해 요청한다.

## 실사용 검증 시나리오

### 연결 검증

```text
Remote Workspace 등록
-> 연결 테스트
-> available = true 확인
```

### ASK

```text
Remote Workspace 선택
-> ASK 모드
-> "이 서버의 프로젝트 구조를 간단히 파악해줘."
-> 원격 읽기/분석 결과 기반 답변 확인
```

### PLAN

```text
Remote Workspace 선택
-> PLAN 모드
-> "CPU, 메모리, 디스크, 프로세스를 점검하는 ToolPlan을 만들어줘."
-> ToolPlan completed
-> PLAN 패널 표시
```

### Tool build 및 실행

```text
ToolPlan 승인 요청
-> Admin 승인
-> Tool build completed
-> Tool 저장소에 생성 Tool 등록
-> AGENT 또는 Tool 실행 흐름에서 Remote Workspace 선택
-> 생성 Tool이 원격 서버에서 리소스 점검 명령 실행
```

## 장애 확인표

| 증상 | 확인 항목 |
| --- | --- |
| 연결 테스트 endpoint가 404 | Core Docker 이미지가 최신 코드로 재빌드되었는지 확인 |
| `Remote basePath must be an absolute path.` | `basePath`가 `/home/ubuntu` 같은 절대경로인지 확인 |
| `Failed to connect to remote workspace` | host, port, username, password/privateKeyPath, 보안그룹, 네트워크 접근 확인 |
| `Failed to load private key` | private key path가 Core 컨테이너 내부 경로인지 확인 |
| `ToolPlan Kafka consumer is disabled` | `CORE_TOOL_PLAN_CONSUMER_ENABLED=true` 확인 |
| `OpenAI API key is not configured` | `THESEUS_MODEL=vllm/...`와 `OPENAI_BASE_URL` 확인 |
| PLAN 요청 후 응답 없음 | Kafka topic, Core consumer, API consumer, Redis/SSE 로그 확인 |
| 생성 Tool이 Remote Workspace를 못 씀 | 실행 context에 `remoteWorkspace` metadata가 포함되는지 확인 |
| DB/Redis 접근이 실패함 | 운영서버 pem과 DB/Redis pem이 같은지 확인하지 말고, DB/Redis 접근용 Remote Workspace가 별도로 등록되어 있는지 확인 |
| DB/Redis 변경 작업이 필요함 | MVP 범위에서는 자동 실행하지 않고 별도 승인/감사/rollback 정책을 먼저 정의 |

## 관련 구현 파일

API Server:

```text
backend/theseus-api-server/src/main/java/com/theseus/api/domain/remoteworkspace/
backend/theseus-api-server/src/main/java/com/theseus/api/domain/toolgeneration/event/ToolPlanRemoteWorkspacePayload.java
backend/theseus-api-server/src/main/java/com/theseus/api/domain/chat/service/ChatStreamService.java
```

Core Server:

```text
backend/theseus-core-server/src/routes/remote_workspace.py
backend/theseus-core-server/src/remote_workspace/
backend/theseus-core-server/src/routes/stream.py
backend/theseus-core-server/src/tool_plan/planner.py
backend/theseus-core-server/src/builder/engine.py
```

FE:

```text
frontend/src/features/projects/api/remoteWorkspace.ts
frontend/src/features/projects/components/settings/RemoteWorkspaceManagement.tsx
frontend/src/features/projects/components/chat/ChatArea.tsx
frontend/src/features/projects/components/chat/InspectorPanel.tsx
```
