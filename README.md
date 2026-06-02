# Theseus

## 팀 단위 AI Tool 생성 및 자동화를 위한 에이전트 플랫폼

**Theseus**는 팀 단위로 AI Tool을 생성하고, 승인, 권한, 실행 이력 관리를 통해 반복 업무를 안전하게 자동화할 수 있도록 돕는 **에이전트 플랫폼**입니다.

> **AI 활용을 개인의 역량에서 조직의 자산으로**  
> **사람이 바뀌어도, 일하는 방식은 이어집니다**

---

## 프로젝트 개요

기업 내 AI 활용은 빠르게 확산되고 있지만, 실제 업무 현장에서는 여전히 다음과 같은 문제가 발생합니다.

- 좋은 프롬프트와 업무 노하우가 개인에게만 축적됨
- 담당자 휴가, 이동, 퇴사 시 업무 방식이 함께 사라짐
- 같은 업무도 사람마다 다른 방식으로 처리되어 결과가 달라짐
- AI Tool이 내부 시스템에 접근할 때 권한과 실행 이력 관리가 어려움

Theseus는 이러한 문제를 해결하기 위해 자연어 요청을 실행 가능한 **ToolPlan**으로 구조화하고, 관리자 승인 과정을 거쳐 조직이 반복적으로 사용할 수 있는 **Tool**로 전환합니다.

| 항목 | 내용 |
| --- | --- |
| 서비스명 | Theseus |
| 서비스 분야 | 팀 단위 AI Tool 생성 및 업무 자동화 에이전트 플랫폼 |
| 플랫폼 | Web Application |
| 개발 기간 | 2026.03.30 ~ 2026.06.01 |
| 개발 인원 | 5명 |
| 기관 | 삼성 청년 SW·AI 아카데미 14기 |
| 핵심 키워드 | ToolPlan, AI Tool, 승인 기반 실행, 권한 관리, Remote Workspace, Kafka |

---

## 서비스 목표

### 1. 개인의 AI 활용 노하우를 조직의 자산으로 전환

AI를 잘 쓰는 개인의 프롬프트와 업무 방식이 사라지지 않도록 반복 업무를 Tool로 저장하고, 조직 구성원이 함께 재사용할 수 있게 합니다.

### 2. 반복 업무 결과의 일관성 확보

프롬프트는 사람마다 달라질 수 있지만, 조직의 업무 결과는 일관되어야 합니다. Theseus는 검증된 Tool을 기반으로 반복 업무를 수행하여 결과 편차를 줄입니다.

### 3. 승인과 권한 기반의 안전한 AI 실행

AI가 서버, 코드, 문서, 내부 시스템에 접근할 수 있는 환경에서는 통제가 중요합니다. Theseus는 ToolPlan 승인, 프로젝트 멤버 권한, 실행 이력 관리를 통해 조직 차원의 안전장치를 제공합니다.

### 4. 담당자 변경에도 이어지는 업무 연속성

신입 직원이나 새로운 담당자도 기존에 승인된 Tool을 통해 동일한 기준으로 업무를 수행할 수 있습니다. 이를 통해 인수인계 비용을 줄이고 업무 연속성을 높입니다.

---

## 서비스 사용 흐름

```text
사용자 자연어 요청
  -> AI가 ToolPlan 생성
  -> 관리자가 ToolPlan 검토 및 승인
  -> 승인된 Tool 등록
  -> 프로젝트 구성원이 Tool 재사용
  -> 실행 결과 및 사용 이력 관리
```

---

## 핵심 기능

| 기능 | 설명 |
| --- | --- |
| 로그인 / 인증 | JWT 기반 사용자 인증 및 API 접근 제어 |
| 프로젝트 관리 | 조직 또는 팀 단위 프로젝트 생성 및 관리 |
| 멤버 관리 | 프로젝트 멤버, 역할, 레벨, 도구 권한 관리 |
| 채팅 세션 관리 | 프로젝트별 AI 요청과 대화 이력 관리 |
| AI 스트리밍 응답 | AI 응답 및 ToolPlan 생성 과정을 실시간 표시 |
| ToolPlan 생성 | 자연어 요청을 실행 가능한 계획으로 구조화 |
| ToolPlan 승인 | 관리자가 AI가 생성한 실행 계획을 승인 또는 거절 |
| Tool 등록 및 실행 | 승인된 ToolPlan을 재사용 가능한 Tool로 등록하고 실행 |
| 도구 사용 목록 | Tool 호출 이력, 생성자, 사용자, 성공/실패 상태 조회 |
| Remote Workspace | SSH 기반 외부 서버 및 프로젝트 디렉터리 연결 |
| Kafka 이벤트 처리 | API Server와 Core Server 간 비동기 작업 처리 |
| SSE 상태 스트리밍 | Tool 생성 및 실행 상태를 실시간으로 전달 |
| Docker Sandbox | Tool 실행 환경 격리 및 안전한 실행 기반 제공 |
| 내부망 확장 고려 | Local LLM 및 내부망 배포를 고려한 구조 |

---

## 시스템 아키텍처

Theseus는 사용자 화면, 비즈니스 API, AI Core 서버를 분리하고, Kafka 기반 이벤트 파이프라인을 통해 AI 작업을 비동기적으로 처리합니다.

```text
Frontend(React/Vite)
  -> Nginx
  -> API Server(Spring Boot)
  -> Kafka
  -> Core Server(FastAPI)

API Server  -> MySQL, Redis
Core Server -> PostgreSQL/pgvector, Redis, LLM Provider, Remote Workspace
```

| Zone | 구성 요소 | 설명 |
| --- | --- | --- |
| Theseus Service Zone | React, Vite, Nginx, API Server, SSE Stream | 사용자 화면 제공, API 요청 처리, 실시간 상태 스트리밍 |
| AI Core Zone | Kafka, Core Server, Docker Sandbox, Access/Secret Control | ToolPlan 생성, Tool 실행, 비동기 이벤트 처리, 실행 격리 |
| SSAFY SuperApp Infra | RDS MySQL, RDS PostgreSQL, ElastiCache Redis | 서비스 데이터 저장, AI Core 데이터 저장, 상태 캐싱 |
| External Project Zone | Remote Workspace, SSAFY-STOCK | 외부 프로젝트/운영 서버 연결, 로그, 설정, 배포 상태 점검 |

### 아키텍처 특징

- Frontend는 프로젝트, 채팅, ToolPlan, Tool, 관리자 설정 화면을 제공합니다.
- Nginx는 정적 파일 서빙과 Reverse Proxy 역할을 수행합니다.
- API Server는 인증, 프로젝트, 멤버, ToolPlan 승인, Tool 관리, 실행 이력 관리를 담당합니다.
- Kafka는 API Server와 Core Server 간 비동기 이벤트를 전달합니다.
- Core Server는 LLM 기반 ToolPlan 생성, Tool 실행 오케스트레이션, Remote Workspace 작업을 수행합니다.
- Docker Sandbox는 Tool 실행 환경을 격리하여 안정성을 높입니다.
- Redis는 실행 상태 캐싱, SSE 재연결 복구, 최신 상태 저장에 활용됩니다.
- Remote Workspace는 SSH 기반으로 외부 프로젝트 서버와 연결되어 운영 자동화를 지원합니다.

---

## 서비스 구성

| 서비스명 | 설명 | 주요 기술 |
| --- | --- | --- |
| Frontend | 사용자 화면, 프로젝트/채팅/Tool 관리 UI | React, TypeScript, Vite |
| API Server | 인증, 프로젝트, 멤버, ToolPlan, Tool, 실행 이력 관리 | Spring Boot, MySQL, Redis, Kafka |
| Core Server | AI 응답 생성, ToolPlan 생성, Tool 실행 | FastAPI, PostgreSQL, pgvector, LLM 연동 |
| Kafka | API Server와 Core Server 간 이벤트 전달 | Kafka |
| Redis | 실행 상태 캐싱 및 SSE 상태 복구 | Redis |
| MySQL | 사용자, 프로젝트, Tool, 승인, 이력 데이터 저장 | MySQL |
| PostgreSQL / pgvector | AI Core 데이터 및 벡터 기반 데이터 저장 | PostgreSQL, pgvector |
| Nginx | Reverse Proxy 및 HTTPS 라우팅 | Nginx |
| Jenkins | 빌드 및 배포 자동화 | Jenkins, Docker |
| Remote Workspace | 외부 프로젝트 서버 연결 및 운영 작업 수행 | SSH, Docker, Jenkins, Logs, Config |

---

## 기술 스택

### Frontend

| Category | Stack |
| --- | --- |
| Language | TypeScript |
| Framework | React, Vite |
| Styling | Tailwind CSS |
| State / Data | TanStack Query, Zustand |
| Network | Axios |
| IDE | Visual Studio Code |

### Backend / AI Core

| Category | Stack |
| --- | --- |
| Language | Java 21, Python 3.11 |
| Framework | Spring Boot, FastAPI |
| Security | Spring Security, JWT |
| API Docs | Swagger / OpenAPI |
| Database | MySQL, PostgreSQL, pgvector |
| Cache / State | Redis |
| Messaging | Kafka |
| AI Core | LLM 연동, ToolPlan 생성, Tool 실행 오케스트레이션 |
| IDE | IntelliJ IDEA, Visual Studio Code |

### Infra / DevOps

| Category | Stack |
| --- | --- |
| Containerization | Docker, Docker Compose |
| CI/CD | Jenkins, GitLab Webhook |
| Web / Proxy | Nginx |
| Database / Managed Resource | RDS MySQL, RDS PostgreSQL |
| Cache | Redis / ElastiCache |
| Storage | S3 |
| Deployment | EC2, Linux Server |
| Collaboration | GitLab, Jira, Notion, Mattermost |

---

## 주요 화면

| 화면 | 설명 |
| --- | --- |
| 랜딩 페이지 | 서비스 소개, 주요 가치, 시작 진입점 제공 |
| AI 채팅 및 ToolPlan 생성 | 자연어 요청을 기반으로 ToolPlan 생성 과정을 스트리밍 |
| ToolPlan 승인 관리 | 관리자가 AI 생성 계획을 검토하고 승인 또는 거절 |
| 도구 사용 목록 | Tool 호출 이력, 사용자, 성공/실패 상태 확인 |
| Remote Workspace 관리 | 외부 프로젝트 서버 연결 정보와 작업 환경 관리 |

---

## CI/CD Pipeline

```text
GitLab Push / Merge Request
  -> Jenkins Webhook Trigger
  -> Source Checkout
  -> Frontend / Backend Build
  -> Docker Image Build
  -> Docker Compose 기반 서비스 재배포
  -> Health Check
```

---

## 저장소 구조

```text
S14P31A308/
├── frontend/
├── backend/
│   ├── theseus-api-server/
│   └── theseus-core-server/
├── infra/
├── docs/
├── exec/
└── tools/
```

---

## 프로젝트 산출물

| 구분 | 경로 |
| --- | --- |
| 포팅 매뉴얼 | `exec/PORTING_MANUAL.md` |
| API 개요 | `docs/api/api-overview.md` |
| 인증 API | `docs/api/auth-api.md` |
| Tool API | `docs/api/tool-api.md` |
| 시스템 아키텍처 | `docs/architecture/system-architecture.md` |
| 배포 문서 | `docs/operations/deployment.md` |
| 트러블슈팅 | `docs/operations/troubleshooting.md` |

---

## 팀원 소개

| 이름 | 역할 | 주요 담당 업무 |
| --- | --- | --- |
| 손석우 | Team Leader / Infra / BE | 시스템 아키텍처 및 인프라 구성, Docker Compose 배포 환경, Jenkins/GitLab CI/CD, Nginx Reverse Proxy, Kafka/Redis/RDS/Remote Workspace 연동 |
| 조원혁 | Full Stack | 프로젝트 및 채팅 화면, ToolPlan 생성/승인 UI, Remote Workspace 관리 화면, 랜딩 페이지, 프론트엔드 API 연동 |
| 김대연 | Full Stack | API Server 기능 구현, 프로젝트 및 Tool API, 관리자 설정 및 Tool 관리, 프론트엔드/백엔드 연동, 발표 자료 및 시연 영상 |
| 권대일 | AI | Core Server 주요 기능, LLM 기반 ToolPlan 생성, Tool 실행 오케스트레이션, PostgreSQL/pgvector 기반 AI 데이터 처리, Docker Sandbox 실행 구조 |
| 김선교 | AI | AI Core Server 기능 보완, ToolPlan 생성 흐름 검증, Tool 실행 결과 처리, 시연 시나리오 구성, 서비스 흐름 검증 |

---

## 프로젝트 성과

- 개인의 프롬프트 노하우를 조직이 재사용 가능한 Tool로 전환하는 구조 설계
- ToolPlan 승인 과정을 통해 AI Tool의 무분별한 실행 방지
- 프로젝트 멤버별 권한과 레벨 기반 도구 실행 통제 구현
- Kafka 기반 비동기 구조를 통해 API Server와 AI Core Server의 결합도 완화
- Redis 기반 실행 상태 캐싱으로 SSE 재연결 및 최신 상태 복구 기반 마련
- SSH 기반 Remote Workspace를 통해 외부 서버 운영 업무 자동화 가능성 확보
- 도구 사용 이력 관리를 통해 조직 내 AI Tool 사용 추적 및 감사 로그 기반 마련
- Jenkins, Docker Compose, Nginx 기반 운영 배포 자동화 구성

---

## 마무리

Theseus는 단순히 AI Agent를 실행하는 서비스가 아닙니다.  
조직이 AI를 안전하게 도입하고, 반복 업무를 표준화하며, 담당자가 바뀌어도 업무 방식이 유지되도록 돕는 플랫폼입니다.

> **프롬프트는 사람마다 달라질 수 있지만, 검증된 Tool은 일관된 업무 결과를 만듭니다.**  
> **Theseus는 AI 사용 경험을 조직의 업무 자산으로 바꿉니다.**
