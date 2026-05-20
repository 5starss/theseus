# Theseus 포팅 매뉴얼

본 문서는 GitLab 프로젝트 `S14P31A308` 레포지토리를 기준으로 작성한 SSAFY 제출용 포팅 매뉴얼이다. 문서의 경로, 파일명, 빌드 명령, Docker Compose 서비스명은 레포에서 직접 확인한 내용을 기준으로 한다. 민감정보는 평문으로 작성하지 않고 `<입력 필요>`, `<SECRET>`, `<발급받은 값>` 형태로 마스킹했다.

## 1. GitLab 소스 클론 이후 빌드 및 배포 문서

### 1-1. 프로젝트 개요

- 프로젝트명: Theseus
- 한 줄 설명: 자연어 요청을 기반으로 프로젝트 분석, ToolPlan 생성, 승인 및 Tool 실행을 지원하는 AI Agent as a Service 플랫폼
- 전체 구성:
  - Frontend: React / Vite
  - API Server: Spring Boot
  - Core Server: Python FastAPI
  - Infra: MySQL, PostgreSQL, Redis, Kafka, Nginx, Docker Compose, Jenkins
- 주요 아키텍처:
  - Frontend -> Nginx -> API Server
  - API Server <-> Kafka <-> Core Server
  - API Server -> MySQL / Redis
  - Core Server -> PostgreSQL / pgvector
  - Remote Workspace -> SSH 기반 외부 서버 분석

확인 근거:

- Frontend: `frontend/package.json`, `frontend/Dockerfile`
- API Server: `backend/theseus-api-server/build.gradle`, `backend/theseus-api-server/Dockerfile`
- Core Server: `backend/theseus-core-server/requirements.txt`, `backend/theseus-core-server/Dockerfile`
- Infra: `infra/docker/local/docker-compose.infra.yml`, `infra/docker/prod/docker-compose.prod.yml`
- CI/CD: `Jenkinsfile`

### 1-2. 개발 및 실행 환경

| 항목 | 확인된 내용 | 근거 |
| --- | --- | --- |
| OS | Docker 기반 Linux 컨테이너 실행. 운영 호스트 OS 상세 버전은 확인 필요 | `infra/docker/prod/docker-compose.prod.yml`, 각 Dockerfile |
| Java | Java 21 | `backend/theseus-api-server/build.gradle`, `backend/theseus-api-server/Dockerfile` |
| Gradle | Gradle Wrapper 사용, Gradle 8.14.4 | `backend/theseus-api-server/gradle/wrapper/gradle-wrapper.properties` |
| Node.js | Node 24 Alpine 이미지 사용 | `frontend/Dockerfile` |
| npm | npm 사용, `npm ci`, `npm run build` | `frontend/package.json`, `frontend/Dockerfile` |
| Python | Python 3.11 slim 이미지 사용 | `backend/theseus-core-server/Dockerfile` |
| FastAPI 실행 방식 | `python -m uvicorn src.main:app --host 0.0.0.0 --port 8086 --workers 1` | `backend/theseus-core-server/Dockerfile`, `infra/docker/local/docker-compose.core.yml` |
| Docker | Docker 사용. 정확한 Docker Engine 버전은 확인 필요 | `Jenkinsfile`, `infra/docker/*` |
| Docker Compose | `docker compose -f ...` 방식 사용 | `infra/README.md`, `Jenkinsfile` |
| API DB | MySQL. 로컬은 `mysql:8.4`, 운영은 MySQL 호환 RDS | `infra/docker/local/docker-compose.infra.yml`, `infra/docker/prod/.env.example` |
| Core DB | PostgreSQL + pgvector. 로컬은 `pgvector/pgvector:pg16`, 운영은 PostgreSQL RDS | `infra/docker/local/docker-compose.infra.yml`, `backend/theseus-core-server/requirements.txt` |
| Redis | 로컬 `redis:7.2-alpine`, 운영 ElastiCache Redis | `infra/docker/local/docker-compose.infra.yml`, `infra/docker/prod/.env.example` |
| Kafka | `confluentinc/cp-kafka:7.6.1` | `infra/docker/local/docker-compose.infra.yml`, `infra/docker/prod/docker-compose.prod.yml` |
| Nginx | Frontend 정적 서빙 및 운영 reverse proxy 사용 | `frontend/Dockerfile`, `infra/docker/prod/nginx/Dockerfile` |
| IDE | 권장 IDE 버전은 레포에서 확인되지 않음. IntelliJ IDEA, VS Code 사용 가능 | 확인 필요 |

주요 런타임 포트:

| 구성요소 | 로컬/운영 포트 | 근거 |
| --- | --- | --- |
| Frontend dev server | 기본 Vite 포트 5173 또는 수동 지정 포트 | `frontend/package.json` |
| API Server | 8080 | `backend/theseus-api-server/src/main/resources/application-local.yml`, prod compose |
| Core Server | 8086 | `backend/theseus-core-server/Dockerfile`, prod compose |
| MySQL local | host 13306 -> container 3306 | `infra/docker/local/docker-compose.infra.yml` |
| PostgreSQL local | host 15432 -> container 5432 | `infra/docker/local/docker-compose.infra.yml` |
| Redis local | host 16379 -> container 6379 | `infra/docker/local/docker-compose.infra.yml` |
| Kafka local/prod external | 19092 | `infra/docker/local/docker-compose.infra.yml`, prod compose |
| Kafka UI local | 18080 | `infra/docker/local/docker-compose.infra.yml` |
| Kafka UI prod | 127.0.0.1:8091 기본값 | `infra/docker/prod/docker-compose.prod.yml` |
| Nginx prod | 80, 443 | `infra/docker/prod/docker-compose.prod.yml` |

### 1-3. 레포지토리 구조

실제 레포 루트 기준 주요 구조:

```text
S14P31A308/
├── frontend/
│   ├── src/
│   ├── public/
│   ├── Dockerfile
│   ├── nginx.conf
│   ├── package.json
│   └── vite.config.ts
├── backend/
│   ├── theseus-api-server/
│   │   ├── src/
│   │   ├── Dockerfile
│   │   ├── build.gradle
│   │   ├── gradlew
│   │   └── settings.gradle
│   └── theseus-core-server/
│       ├── src/
│       ├── theseus_engine/
│       ├── tests/
│       ├── vscode-extension/
│       ├── Dockerfile
│       ├── Dockerfile.sandbox
│       ├── requirements.txt
│       └── .env.example
├── infra/
│   └── docker/
│       ├── local/
│       │   ├── docker-compose.infra.yml
│       │   ├── docker-compose.api.yml
│       │   └── docker-compose.core.yml
│       └── prod/
│           ├── docker-compose.prod.yml
│           ├── .env.example
│           └── nginx/
├── docs/
├── exec/
├── tools/
├── Jenkinsfile
└── .env.example
```

주의: 사용자 요청 예시의 `backend/api-server/`, `core-server/` 구조가 아니라 실제 레포는 `backend/theseus-api-server/`, `backend/theseus-core-server/` 구조이다.

## 2. 로컬 실행 방법

### 2-1. GitLab clone

```bash
git clone <GitLab 저장소 URL>
cd S14P31A308
```

GitLab 저장소 URL, 접근 토큰, SSH key는 `<입력 필요>`이다.

### 2-2. 로컬 인프라 실행

로컬 MySQL, PostgreSQL, Redis, Kafka, Kafka UI 실행:

```bash
docker compose \
  -f infra/docker/local/docker-compose.infra.yml \
  up -d
```

Kafka topic 초기화는 `theseus-local-kafka-init` 서비스가 수행한다.

Kafka UI:

```text
http://localhost:18080
```

Redis 확인:

```bash
docker exec -it theseus-local-redis redis-cli ping
```

Kafka topic 확인:

```bash
docker exec -it theseus-local-kafka kafka-topics \
  --bootstrap-server theseus-local-kafka:29092 \
  --list
```

### 2-3. API Server 로컬 실행

API Server 경로:

```bash
cd backend/theseus-api-server
```

Gradle Wrapper 기반 빌드:

```bash
./gradlew bootJar
```

Windows:

```powershell
.\gradlew.bat bootJar
```

로컬 실행 시 주요 환경변수:

```env
SPRING_DATASOURCE_URL=jdbc:mysql://localhost:13306/theseus
SPRING_DATASOURCE_USERNAME=<입력 필요>
SPRING_DATASOURCE_PASSWORD=<SECRET>
SPRING_KAFKA_BOOTSTRAP_SERVERS=localhost:19092
SPRING_DATA_REDIS_HOST=localhost
SPRING_DATA_REDIS_PORT=16379
THESEUS_CORE_BASE_URL=http://localhost:8086
JWT_SECRET=<SECRET>
INTERNAL_API_KEY=<SECRET>
```

실행:

```bash
./gradlew bootRun
```

주의:

- `infra/README.md`에 따르면 IDE에서 API Server를 실행하는 경우 `theseus-local-api-server` 컨테이너를 동시에 실행하지 않는다. 둘 다 기본 포트 8080을 사용한다.
- `backend/theseus-api-server/src/main/resources/application-local.yml`은 `.env.local` 또는 `infra/docker/local/.env.local` import를 지원한다.

### 2-4. Core Server 로컬 실행

Core Server 경로:

```bash
cd backend/theseus-core-server
```

Python 가상환경 생성 및 의존성 설치:

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

Windows PowerShell:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

주요 환경변수:

```env
ENV=dev
AUTH_MODE=spring
CORE_KAFKA_CONSUMER_ENABLED=true
CORE_TOOL_PLAN_CONSUMER_ENABLED=true
CORE_KAFKA_BOOTSTRAP_SERVERS=localhost:19092
CORE_POSTGRES_HOST=localhost
CORE_POSTGRES_PORT=15432
CORE_POSTGRES_DB=theseus_core
CORE_POSTGRES_USER=<입력 필요>
CORE_POSTGRES_PASSWORD=<SECRET>
SPRING_BOOT_INTERNAL_URL=http://localhost:8080
SPRING_BOOT_AUTH_VERIFY_URL=http://localhost:8080/api/internal/auth/verify
SPRING_BOOT_PROJECT_PERMISSIONS_URL=http://localhost:8080/api/internal/project/permissions
SPRING_BOOT_BILLING_USAGE_URL=http://localhost:8080/api/internal/billing/usage
SPRING_BOOT_TOOL_PLAN_URL=http://localhost:8080/api/internal/tool-plan/save
SPRING_BOOT_INTERNAL_HISTORY_MESSAGES_URL=http://localhost:8080/api/internal/history/messages
SPRING_BOOT_REMOTE_WORKSPACE_CONFIG_URL=http://localhost:8080/api/internal/remote-workspaces/connection-config
SPRING_BOOT_INTERNAL_API_KEY=<SECRET>
OPENAI_API_KEY=<SECRET>
ANTHROPIC_API_KEY=<SECRET>
GEMINI_API_KEY=<SECRET>
THESEUS_MODEL=<입력 필요>
```

실행:

```bash
python -m uvicorn src.main:app --host 0.0.0.0 --port 8086 --workers 1
```

Docker 기반 전체 로컬 통합 실행:

```bash
docker compose \
  -f infra/docker/local/docker-compose.infra.yml \
  -f infra/docker/local/docker-compose.api.yml \
  -f infra/docker/local/docker-compose.core.yml \
  up -d
```

### 2-5. Frontend 로컬 실행

Frontend 경로:

```bash
cd frontend
```

의존성 설치:

```bash
npm ci
```

환경변수:

```env
VITE_API_BASE_URL=http://localhost:8080
```

개발 서버 실행:

```bash
npm run dev
```

Windows에서 Vite 기본 포트 5173 권한 문제가 발생하면 다음처럼 포트를 지정한다.

```bash
npm run dev -- --host 127.0.0.1 --port 3000
```

빌드:

```bash
npm run build
```

## 3. 운영 배포 방법

### 3-1. 운영 Docker Compose 파일

운영 compose 파일:

```text
infra/docker/prod/docker-compose.prod.yml
```

운영 env 예시:

```text
infra/docker/prod/.env.example
```

실제 운영 env 파일:

```text
infra/docker/prod/.env
```

주의: `.env`에는 DB password, JWT secret, API key, LLM API key 등 민감정보가 포함되므로 Git에 커밋하지 않는다.

### 3-2. 운영 환경변수 목록

아래는 `infra/docker/prod/.env.example`, `backend/theseus-core-server/src/config.py`, `backend/theseus-api-server/src/main/resources/application-local.yml`, `Jenkinsfile` 기준으로 확인한 주요 변수이다.

#### 공통 / Frontend

```env
SPRING_PROFILES_ACTIVE=prod
TZ=Asia/Seoul
ENV=prod
ALLOWED_ORIGINS=<운영 도메인>
VITE_API_BASE_URL=<운영 API base URL>
```

#### API Server / MySQL / Redis

```env
SPRING_DATASOURCE_URL=jdbc:mysql://<RDS_HOST>:3306/<DB_NAME>?useSSL=false&allowPublicKeyRetrieval=true&serverTimezone=Asia/Seoul&characterEncoding=UTF-8
SPRING_DATASOURCE_USERNAME=<입력 필요>
SPRING_DATASOURCE_PASSWORD=<SECRET>
SPRING_DATA_REDIS_HOST=<ElastiCache Redis Host>
SPRING_DATA_REDIS_PORT=6379
SPRING_DATA_REDIS_PASSWORD=<SECRET 또는 비워둠>
JWT_SECRET=<SECRET>
INTERNAL_API_KEY=<SECRET>
```

#### Tool generation / SSE / timeout

```env
THESEUS_TOOL_GENERATION_STATE_TTL_MINUTES=30
THESEUS_TOOL_GENERATION_SSE_TIMEOUT_MILLIS=1800000
THESEUS_TOOL_PLAN_RUN_TIMEOUT_MINUTES=30
THESEUS_TOOL_PLAN_RUN_TIMEOUT_CHECK_DELAY_MILLIS=60000
CORE_TOOL_BUILD_MAX_REPAIR_ATTEMPTS=2
CORE_TOOL_BUILD_RUN_TIMEOUT_SECONDS=1800
```

참고: `backend/theseus-core-server/src/config.py`의 현재 기본값은 `CORE_TOOL_BUILD_RUN_TIMEOUT_SECONDS=180`으로 확인된다. 운영에서 30분 timeout을 원하면 `.env`에 `CORE_TOOL_BUILD_RUN_TIMEOUT_SECONDS=1800`을 명시해야 한다. 코드 기본값 변경 여부는 확인 필요.

#### PostgreSQL / pgvector

```env
CORE_POSTGRES_HOST=<PostgreSQL RDS Host>
CORE_POSTGRES_PORT=5432
CORE_POSTGRES_DB=<입력 필요>
CORE_POSTGRES_USER=<입력 필요>
CORE_POSTGRES_PASSWORD=<SECRET>
CORE_POSTGRES_SCHEMA=public
```

#### Kafka

```env
KAFKA_CLUSTER_ID=<발급 또는 생성한 값>
KAFKA_EXTERNAL_HOST=<운영 Kafka 외부 Host>
KAFKA_UI_HOST_PORT=8091
SPRING_KAFKA_BOOTSTRAP_SERVERS=theseus-prod-kafka:29092
SPRING_KAFKA_CONSUMER_GROUP_ID=theseus-api-server-prod
CORE_KAFKA_BOOTSTRAP_SERVERS=theseus-prod-kafka:29092
CORE_KAFKA_CONSUMER_ENABLED=true
CORE_LEGACY_TOOL_GENERATION_CONSUMER_ENABLED=false
CORE_TOOL_PLAN_CONSUMER_ENABLED=true
CORE_KAFKA_TOOL_PLAN_CONSUMER_GROUP_ID=theseus-core-tool-plan-prod
CORE_KAFKA_TOOL_BUILD_CONSUMER_GROUP_ID=theseus-core-tool-build-prod
KAFKA_TOPIC_TOOL_PLAN_REQUEST=theseus.tool-plan.request
KAFKA_TOPIC_TOOL_PLAN_EVENT=theseus.tool-plan.event
KAFKA_TOPIC_TOOL_BUILD_REQUEST=theseus.tool-build.request
KAFKA_TOPIC_TOOL_BUILD_EVENT=theseus.tool-build.event
```

#### Core / Internal API / LLM

```env
AUTH_MODE=spring
SPRING_BOOT_INTERNAL_API_KEY=<SECRET>
SPRING_BOOT_INTERNAL_URL=http://theseus-api-server:8080
SPRING_BOOT_AUTH_VERIFY_URL=http://theseus-api-server:8080/api/internal/auth/verify
SPRING_BOOT_PROJECT_PERMISSIONS_URL=http://theseus-api-server:8080/api/internal/project/permissions
SPRING_BOOT_BILLING_USAGE_URL=http://theseus-api-server:8080/api/internal/billing/usage
SPRING_BOOT_TOOL_PLAN_URL=http://theseus-api-server:8080/api/internal/tool-plan/save
SPRING_BOOT_INTERNAL_HISTORY_MESSAGES_URL=http://theseus-api-server:8080/api/internal/history/messages
SPRING_BOOT_REMOTE_WORKSPACE_CONFIG_URL=http://theseus-api-server:8080/api/internal/remote-workspaces/connection-config
THESEUS_MODEL=<입력 필요>
OPENAI_BASE_URL=<입력 필요>
OPENAI_API_KEY=<SECRET>
ANTHROPIC_API_KEY=<SECRET>
GEMINI_API_KEY=<SECRET>
DEEPSEEK_API_KEY=<SECRET>
OPENWEATHERMAP_API_KEY=<SECRET>
```

#### Remote Workspace / Sandbox

```env
REMOTE_WORKSPACE_KEY_HOST_PATH=/secure/theseus/keys/<SSH_KEY_FILE>.pem
THESEUS_REMOTE_WORKSPACE_FILE_WRITE_OVERRIDE=false
THESEUS_DATA_DIR=/home/appuser/.theseus/data
THESEUS_CUSTOM_TOOLS_HOST_DIR=/opt/theseus/custom_tools
THESEUS_DEBUG_DUMP=true
THESEUS_DEBUG_DUMP_DIR=/var/log/theseus/debug/dumps
THESEUS_DEBUG_DUMP_HOST_DIR=/opt/theseus/debug/dumps
DOCKER_GID=<Docker socket group id>
SANDBOX_IMAGE=theseus-sandbox:py311-tools
SANDBOX_HOST_TEMP_ROOT=/tmp/theseus-sandbox-shared
SANDBOX_CONTAINER_TEMP_ROOT=/tmp/theseus-sandbox-shared
```

### 3-3. 운영 배포 명령

운영 compose 설정 검증:

```bash
docker compose --env-file infra/docker/prod/.env \
  -f infra/docker/prod/docker-compose.prod.yml \
  config --quiet
```

전체 배포:

```bash
docker compose --env-file infra/docker/prod/.env \
  -f infra/docker/prod/docker-compose.prod.yml \
  up -d --build
```

개별 서비스 배포:

```bash
docker compose --env-file infra/docker/prod/.env \
  -f infra/docker/prod/docker-compose.prod.yml \
  up -d --no-deps --build theseus-api-server

docker compose --env-file infra/docker/prod/.env \
  -f infra/docker/prod/docker-compose.prod.yml \
  up -d --no-deps --build theseus-core-server

docker compose --env-file infra/docker/prod/.env \
  -f infra/docker/prod/docker-compose.prod.yml \
  up -d --no-deps --build theseus-frontend theseus-nginx
```

Sandbox image가 필요한 경우:

```bash
docker compose --profile sandbox-build \
  --env-file infra/docker/prod/.env \
  -f infra/docker/prod/docker-compose.prod.yml \
  build theseus-sandbox-image
```

컨테이너 상태 확인:

```bash
docker compose --env-file infra/docker/prod/.env \
  -f infra/docker/prod/docker-compose.prod.yml \
  ps
```

### 3-4. Jenkins 배포

Jenkinsfile 기준:

- Jenkins credentials file id: `theseus-prod-env`
- 운영 env 주입 위치: `infra/docker/prod/.env`
- 배포 branch: `dev`
- MR 또는 컨벤션 브랜치에서는 CI 빌드 수행
- `dev` branch push build에서는 변경된 서비스만 배포

변경 감지 기준:

- `frontend/` 변경: Frontend Docker image build/deploy
- `backend/theseus-api-server/` 변경: API Server Docker image build/deploy
- `backend/theseus-core-server/` 또는 `infra/docker/prod/` 변경: Core Server Docker image build/deploy
- `Jenkinsfile` 변경: 전체 주요 서비스 build/deploy 대상

Jenkins 주요 stage:

1. Checkout
2. Validate Pipeline Context
3. Detect Changes
4. Prepare env file
5. Frontend Build
6. API Server Build
7. Core Server Build
8. Core Server Python Import Smoke Test
9. Core Server Worker Contract
10. Docker Compose Config
11. Deploy Production
12. Container Status

## 4. DB 접속 정보에 필요한 주요 property 파일 목록

| 용도 | 파일 |
| --- | --- |
| API Server 기본 profile | `backend/theseus-api-server/src/main/resources/application.yaml` |
| API Server local datasource/redis/kafka 설정 | `backend/theseus-api-server/src/main/resources/application-local.yml` |
| Core Server 설정 클래스 | `backend/theseus-core-server/src/config.py` |
| Core Server env 예시 | `backend/theseus-core-server/.env.example` |
| 루트 env 예시 | `.env.example` |
| 운영 env 예시 | `infra/docker/prod/.env.example` |
| 운영 compose env 주입 | `infra/docker/prod/docker-compose.prod.yml` |
| 로컬 infra compose | `infra/docker/local/docker-compose.infra.yml` |
| 로컬 API compose | `infra/docker/local/docker-compose.api.yml` |
| 로컬 Core compose | `infra/docker/local/docker-compose.core.yml` |

## 5. 외부 서비스 정보

아래 항목은 제출 및 운영 시 별도 계정/권한/키 발급이 필요하다.

| 서비스 | 사용 목적 | 설정 위치 | 값 |
| --- | --- | --- | --- |
| GitLab | 소스 저장소, MR, Webhook | Jenkins SCM, Git remote | `<입력 필요>` |
| JIRA | 이슈 관리 | MR 본문, 커밋 메시지 | `<입력 필요>` |
| Jenkins | CI/CD | `Jenkinsfile` | Jenkins URL/계정 `<입력 필요>` |
| AWS EC2 | Docker Compose 운영 서버 | 운영 서버 | 접속 정보 `<입력 필요>` |
| AWS RDS MySQL | API Server 영속 DB | `SPRING_DATASOURCE_URL` | Host/User/Password `<입력 필요>` |
| AWS RDS PostgreSQL | Core Server DB/pgvector | `CORE_POSTGRES_*` | Host/User/Password `<입력 필요>` |
| AWS ElastiCache Redis | Refresh token, ToolPlanRun state cache | `SPRING_DATA_REDIS_*` | Host/Password `<입력 필요>` |
| SSAFY SuperApp | 외부 서비스 연계 또는 배포 환경 | 확인 필요 | `<입력 필요>` |
| Kafka | ToolPlan/ToolBuild request/event broker | Docker Compose | `confluentinc/cp-kafka:7.6.1` |
| LLM API | ToolPlan 생성, Tool build, agent 응답 | Core env | API key `<SECRET>` |
| Remote Workspace | SSH 기반 외부 프로젝트/서버 분석 | DB `remote_workspaces`, Core SSH | host/key `<입력 필요>` |
| S3/Object Storage | Object storage optional 설정 | `infra/docker/prod/.env.example` | Access key `<SECRET>` |

## 6. 확인된 주요 기능 흐름

### 6-1. Redis / ElastiCache 사용

API Server가 Redis를 사용한다.

- Refresh token 저장: `backend/theseus-api-server/src/main/java/com/theseus/api/domain/auth/redis/RefreshTokenStore.java`
  - key prefix: `RT:`
- ToolPlanRun 상태 저장: `backend/theseus-api-server/src/main/java/com/theseus/api/domain/toolgeneration/redis/ToolPlanRunStateStore.java`
  - key format: `tool:plan:{runId}:state`

### 6-2. Remote Workspace 접속

Remote Workspace SSH 접속 주체는 Core Server이다.

흐름:

1. API Server가 `remote_workspaces` 테이블에 host, port, username, password/privateKeyPath, basePath 저장
2. Core Server가 API Server internal endpoint에서 설정 조회
3. Core Server가 `paramiko` 기반 SSH 접속 수행

근거:

- API remote workspace service: `backend/theseus-api-server/src/main/java/com/theseus/api/domain/remoteworkspace/service/RemoteWorkspaceService.java`
- Core resolver: `backend/theseus-core-server/src/remote_workspace/resolver.py`
- Core SSH connector: `backend/theseus-core-server/src/remote_workspace/ssh_connector.py`
- SSH key mount: `infra/docker/prod/docker-compose.prod.yml`

## 7. 확인 필요 항목

- 운영 EC2 OS 상세 버전
- 운영 Docker Engine / Docker Compose plugin 버전
- Jenkins URL, credential 설정 상세
- GitLab repository URL, branch protection 정책
- JIRA project URL 및 issue key 목록
- SSAFY SuperApp 연동 방식 및 credential
- 운영 RDS/ElastiCache 실제 엔드포인트와 보안 그룹 설정
- 운영 LLM provider/model 최종 값
- 운영 Remote Workspace 대상 서버 host, username, basePath, SSH key 경로
- 운영 `.env`에 `CORE_TOOL_BUILD_RUN_TIMEOUT_SECONDS=1800` 반영 여부
