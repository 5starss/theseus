# Remote Workspace 연동 및 사용 가이드

## 개념

Remote Workspace는 Theseus가 프로젝트 단위로 등록하는 외부 서버 작업 대상이다.

```text
서버관리 프로젝트
-> 싸피증권 운영서버를 Remote Workspace로 등록
-> ASK / PLAN / AGENT / 생성 Tool 실행에서 remoteWorkspaceId 선택
-> Core Server가 허용된 도구 경계 안에서 원격 서버를 분석하거나 작업
```

Remote Workspace는 ToolPlan 전용 참고자료가 아니다. 생성된 Theseus Tool과 AGENT가 실제로 작업하는 외부 서버 실행 환경이다.

## 역할 구분

| 구분 | 역할 |
| --- | --- |
| Remote Workspace | 프로젝트가 연결할 외부 서버와 작업 기준 경로 |
| Core local tool | Core 서버 로컬 파일시스템/프로세스를 다루는 기본 도구 |
| Core remote tool | Remote Workspace를 SSH로 다루는 `remote_*` 도구 |
| Theseus Tool | ToolPlan 승인 및 build 이후 프로젝트 Tool 저장소에 등록되는 사용자용 Tool |
| ToolPlan | 승인 전 Tool 명세 |

## 저장 정보

`remote_workspaces`는 프로젝트 단위로 저장된다.

| 필드 | 설명 |
| --- | --- |
| `id` | Remote Workspace ID |
| `project_id` | 소속 프로젝트 ID |
| `created_by_project_member_id` | 등록한 프로젝트 멤버 ID |
| `name` | 화면 표시 이름 |
| `host` | SSH host |
| `port` | SSH port |
| `username` | SSH username |
| `password` | password 인증이 필요한 경우의 내부 저장 값 |
| `private_key_path` | Core Server가 접근할 수 있는 private key path |
| `base_path` | 원격 서버 작업 기준 경로 |
| `allow_write_execution` | AGENT/승인 Tool 실행에서 쓰기/명령 실행 허용 여부 |
| `status` | `ACTIVE`, `DELETED` |

`password`는 응답 DTO에 포함하지 않는다. `privateKeyPath`는 key 내용이 아니라 Core Server 내부 경로다.

## 보안 경계

API Server와 Core Server 사이의 공개 계약에는 secret을 싣지 않는다.

```text
Kafka ToolPlan payload: remoteWorkspaceId만 포함
ASK/AGENT stream payload: remoteWorkspaceId만 포함
FE 요청 body: remoteWorkspaceId만 포함
SSE/로그/응답: password 미노출
```

`password`, `privateKeyPath`, full `remoteWorkspace` block을 Kafka/stream payload로 전달하지 않는다. 실제 SSH secret resolution은 별도 설계 후 활성화한다.

## 쓰기/명령 실행 스위치

Remote Workspace의 기본값은 read-only다.

```text
allowWriteExecution = false
```

사용자가 등록/수정 화면에서 `쓰기/명령 실행 허용`을 체크하면 `allowWriteExecution = true`가 저장된다.

모드별 정책:

| 모드 | Remote Workspace 사용 |
| --- | --- |
| `ASK` | 읽기/분석 도구만 사용 |
| `PLAN` | ToolPlan 작성을 위한 읽기/분석 도구만 사용 |
| `AGENT` | 읽기/분석 도구 사용, `allowWriteExecution=true`일 때 쓰기/명령 도구 사용 |
| 승인 Tool 실행 | Tool 권한과 Remote Workspace 설정이 허용할 때 쓰기/명령 도구 사용 |

ASK/PLAN은 `allowWriteExecution=true`여도 쓰기/명령 실행 도구를 노출하지 않는다.

## Core 도구 이름

기존 local 도구를 remote 구현으로 덮어쓰지 않는다.

Local tool:

```text
read_file
grep
bash
write_file
edit_file
```

Remote read-only tool:

```text
remote_read_file
remote_grep
remote_tail_log
remote_check_cpu
remote_check_memory
remote_check_disk
```

Remote write/execute tool:

```text
remote_write_file
remote_edit_file
remote_run_command
```

LLM에는 현재 실행 대상과 모드에 맞는 active registry만 노출한다. Remote Workspace가 선택되면 같은 기능의 local 도구는 기본적으로 숨긴다.

## API 목록

모든 API는 `ApiResponse<T>` 래퍼를 사용한다.

### 등록

```http
POST /api/v1/projects/{projectId}/remote-workspaces
Content-Type: application/json
```

Request:

```json
{
  "name": "싸피증권 운영서버",
  "host": "ssafy-stock.kr",
  "port": 22,
  "username": "ubuntu",
  "password": null,
  "privateKeyPath": "/home/appuser/.ssh/ssafy-ec2-key.pem",
  "basePath": "/home/ubuntu",
  "allowWriteExecution": false
}
```

### 목록 조회

```http
GET /api/v1/projects/{projectId}/remote-workspaces
```

Response result item:

```json
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
  "allowWriteExecution": false,
  "status": "ACTIVE",
  "createdAt": "2026-05-14T09:00:00",
  "updatedAt": "2026-05-14T09:00:00"
}
```

### 상세 조회

```http
GET /api/v1/projects/{projectId}/remote-workspaces/{remoteWorkspaceId}
```

### 수정

```http
PATCH /api/v1/projects/{projectId}/remote-workspaces/{remoteWorkspaceId}
Content-Type: application/json
```

Request:

```json
{
  "name": "싸피증권 운영서버",
  "host": "54.180.80.22",
  "port": 22,
  "username": "ubuntu",
  "password": null,
  "privateKeyPath": "/home/appuser/.ssh/ssafy-ec2-key.pem",
  "basePath": "/home/ubuntu/app",
  "allowWriteExecution": true
}
```

`null` 또는 생략한 필드는 기존 값을 유지한다. 빈 문자열은 허용하지 않는다.

### 삭제

```http
PATCH /api/v1/projects/{projectId}/remote-workspaces/{remoteWorkspaceId}/delete
```

물리 삭제가 아니라 `status = DELETED`로 전환한다.

### 연결 테스트

```http
POST /api/v1/projects/{projectId}/remote-workspaces/{remoteWorkspaceId}/test-connection
```

현재 연결 테스트는 secret resolver가 준비될 때까지 비활성 응답을 반환한다. API Server는 Core로 secret payload를 전달하지 않는다.

Response result:

```json
{
  "remoteWorkspaceId": 1,
  "available": false,
  "message": "Remote Workspace connection test is not enabled until secure secret resolution is ready."
}
```

## ASK / PLAN / AGENT 요청 연결

FE는 선택된 Remote Workspace의 ID만 요청에 포함한다.

ASK/AGENT stream:

```json
{
  "mode": "AGENT",
  "prompt": "싸피증권 운영서버의 CPU와 메모리 상태를 확인해줘.",
  "remoteWorkspaceId": 1
}
```

PLAN generate:

```json
{
  "mode": "PLAN",
  "prompt": "싸피증권 운영서버의 리소스 병목을 확인하는 ToolPlan을 만들어줘.",
  "remoteWorkspaceId": 1
}
```

ToolPlan Kafka request payload에는 `remoteWorkspaceId`만 포함한다.

## private key path 기준

FE에 입력하는 `privateKeyPath`는 사용자 PC 경로가 아니라 Core Server가 접근할 수 있는 경로다.

Windows PC key 예시:

```text
C:\Users\SSAFY\.ssh\ssafy-ec2-key.pem
```

Core 컨테이너 내부 경로 예시:

```text
/home/appuser/.ssh/ssafy-ec2-key.pem
```

로컬 Docker에서 key를 사용할 경우 read-only volume으로 mount한다.

```yaml
services:
  theseus-core-server:
    volumes:
      - C:/Users/SSAFY/.ssh/ssafy-ec2-key.pem:/home/appuser/.ssh/ssafy-ec2-key.pem:ro
```

## 싸피증권 운영서버 등록 예시

```text
이름: 싸피증권 운영서버
Host: ssafy-stock.kr 또는 54.180.80.22
Port: 22
Username: ubuntu
Password:
Private Key Path: /home/appuser/.ssh/ssafy-ec2-key.pem
Base Path: /home/ubuntu
allowWriteExecution: false
```

DB/Redis가 다른 pem으로 접근되는 구조라면 운영서버 Remote Workspace를 재사용하지 않는다. DB/Redis 접근 Bastion 또는 접근 서버를 별도 Remote Workspace로 등록한다.

MVP 기준 DB/Redis는 조회와 진단 중심으로 사용한다. `UPDATE`, `DELETE`, `DROP`, `FLUSHALL`, `CONFIG SET`처럼 운영 데이터나 인프라 상태를 변경하는 작업은 별도 승인, 감사 로그, rollback 정책 전까지 자동화 범위에 포함하지 않는다.

## 관련 구현 파일

API Server:

```text
backend/theseus-api-server/src/main/java/com/theseus/api/domain/remoteworkspace/
backend/theseus-api-server/src/main/java/com/theseus/api/domain/chat/service/ChatStreamService.java
backend/theseus-api-server/src/main/java/com/theseus/api/domain/toolgeneration/service/ToolPlanGenerationService.java
```

Core Server:

```text
backend/theseus-core-server/src/remote_workspace/
backend/theseus-core-server/src/builder/engine.py
backend/theseus-core-server/src/tool_plan/planner.py
backend/theseus-core-server/src/routes/stream.py
```

Frontend:

```text
frontend/src/features/projects/api/remoteWorkspace.ts
frontend/src/features/projects/components/settings/RemoteWorkspaceManagement.tsx
frontend/src/features/projects/components/chat/ChatArea.tsx
```
