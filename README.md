# Theseus

Theseus는 프로젝트 분석, ToolPlan 생성, 승인, 도구 실행을 지원하는 AI Agent as a Service 플랫폼입니다. 사용자는 웹 화면에서 프로젝트와 채팅 세션을 관리하고, 원격 워크스페이스를 연결해 AI 에이전트가 코드와 문서를 분석하거나 필요한 작업을 수행하도록 요청할 수 있습니다.

## 주요 기능

- JWT 기반 로그인과 프로젝트별 권한 관리
- 프로젝트 채팅 세션 및 메시지 이력 관리
- AI Agent 스트리밍 응답
- ToolPlan 생성, 재생성, 실행 상태 추적
- 도구 승인 및 프로젝트 범위 도구 관리
- SSH 기반 원격 워크스페이스 연동
- Kafka 기반 API Server와 Core Server 비동기 연동

## 시스템 구성

```text
Frontend(React/Vite)
  -> Nginx
  -> API Server(Spring Boot)
  -> Kafka
  -> Core Server(FastAPI)

API Server  -> MySQL, Redis
Core Server -> PostgreSQL/pgvector, Redis, LLM Provider, Remote Workspace
```

## 저장소 구조

```text
S14P31A308/
├── frontend/                    # React/Vite 프론트엔드
├── backend/
│   ├── theseus-api-server/       # Spring Boot API 서버
│   └── theseus-core-server/      # Python FastAPI AI Core 서버
├── infra/                        # Docker, Nginx, Jenkins, 운영 인프라 설정
├── docs/                         # API, 아키텍처, 운영, 기획 문서
├── exec/                         # 제출/포팅/데모 관련 문서
└── tools/                        # Git hook, 템플릿 등 개발 보조 도구
```

## 기술 스택

| 영역 | 기술 |
| --- | --- |
| Frontend | React, TypeScript, Vite, Tailwind CSS |
| API Server | Java 21, Spring Boot, JPA, Spring Security |
| Core Server | Python 3.11, FastAPI, aiokafka |
| Database | MySQL, PostgreSQL, pgvector |
| Cache/State | Redis |
| Messaging | Kafka |
| Infra | Docker, Docker Compose, Nginx, Jenkins |

## 문서

- 포팅 매뉴얼: `exec/PORTING_MANUAL.md`
- API 개요: `docs/api/api-overview.md`
- 인증 API: `docs/api/auth-api.md`
- Tool API: `docs/api/tool-api.md`
- 시스템 아키텍처: `docs/architecture/system-architecture.md`
- 배포 문서: `docs/operations/deployment.md`
- 트러블슈팅: `docs/operations/troubleshooting.md`

## 로컬 실행 개요

세부 실행 절차와 환경 변수는 포팅 매뉴얼을 기준으로 확인합니다.

```bash
# infra
docker compose -f infra/docker/local/docker-compose.infra.yml up -d

# API server
cd backend/theseus-api-server
./gradlew bootRun

# Core server
cd backend/theseus-core-server
python -m uvicorn src.main:app --host 0.0.0.0 --port 8086

# Frontend
cd frontend
npm ci
npm run dev
```

## 운영 배포

운영 Docker Compose 설정은 `infra/docker/prod/docker-compose.prod.yml`에 있습니다. 운영 환경 변수, 인증서, Jenkins 배포 절차는 `exec/PORTING_MANUAL.md`와 `docs/operations/deployment.md`를 함께 확인합니다.
