# Theseus 시연 시나리오

본 문서는 SSAFY 제출 및 발표 시 Theseus의 핵심 기능을 보여주기 위한 시연 흐름이다. 실제 계정, 프로젝트명, 서버 주소, API key, SSH key는 `<입력 필요>` 또는 `<SECRET>`로 마스킹한다.

## 1. 시연 준비

### 1-1. 서비스 상태 확인

운영 Docker Compose 기준:

```bash
docker compose --env-file infra/docker/prod/.env \
  -f infra/docker/prod/docker-compose.prod.yml \
  ps
```

필수 컨테이너:

- `theseus-prod-nginx`
- `theseus-prod-frontend`
- `theseus-prod-api-server`
- `theseus-prod-core-server`
- `theseus-prod-kafka`
- `theseus-prod-kafka-ui`

API health 확인:

```bash
curl -i <운영 도메인>/api/actuator/health
```

Core health 확인:

```bash
curl -i <운영 도메인>/core/health
```

정확한 health endpoint는 운영 배포 상태에 따라 확인 필요이다.

### 1-2. Kafka topic 확인

```bash
docker exec -it theseus-prod-kafka kafka-topics \
  --bootstrap-server theseus-prod-kafka:29092 \
  --list
```

확인할 topic:

- `theseus.tool-plan.request`
- `theseus.tool-plan.event`
- `theseus.tool-build.request`
- `theseus.tool-build.event`

### 1-3. Remote Workspace 준비

Remote Workspace는 Core Server가 SSH로 접속한다.

필요 정보:

```text
host=<SSAFY-STOCK 서버 Host>
port=22
username=<입력 필요>
privateKeyPath=/home/appuser/.ssh/ssafy-ec2-key.pem
basePath=<분석 대상 프로젝트 경로>
allowWriteExecution=<true 또는 false>
```

운영 compose의 key mount:

```text
${REMOTE_WORKSPACE_KEY_HOST_PATH}:/home/appuser/.ssh/ssafy-ec2-key.pem:ro
```

대상 서버 security group 또는 firewall에서 Core 서버의 SSH 접근을 허용해야 한다.

## 2. 시연 흐름

### 2-1. 로그인

1. 브라우저에서 운영 도메인 접속
   ```text
   https://<운영 도메인>
   ```
2. 로그인 화면에서 계정 입력
   ```text
   사번/이메일: <입력 필요>
   비밀번호: <SECRET>
   ```
3. 로그인 성공 후 프로젝트 목록 화면으로 이동되는지 확인한다.

시연 포인트:

- API Server의 JWT access token 발급
- refresh token은 Redis/ElastiCache에 저장

관련 코드:

- `backend/theseus-api-server/src/main/java/com/theseus/api/domain/auth/redis/RefreshTokenStore.java`

### 2-2. 프로젝트 선택

1. 프로젝트 목록에서 시연용 프로젝트 선택
2. 프로젝트 sidebar 또는 dashboard 진입 확인
3. 현재 사용자 프로젝트 권한 확인

시연 포인트:

- 프로젝트별 member 권한 기반 접근
- Tool 사용/생성/수정/삭제 권한 분리

### 2-3. Remote Workspace 등록 및 연결 테스트

1. 프로젝트 설정 화면 진입
2. Remote Workspace 메뉴 선택
3. SSAFY-STOCK 서버 정보 입력
   ```text
   name=SSAFY-STOCK
   host=<입력 필요>
   port=22
   username=<입력 필요>
   privateKeyPath=/home/appuser/.ssh/ssafy-ec2-key.pem
   basePath=<입력 필요>
   allowWriteExecution=false 또는 true
   ```
4. 연결 테스트 실행
5. 성공 메시지 확인

시연 포인트:

- API Server가 RemoteWorkspace 정보를 DB에 저장
- Core Server가 internal API로 접속 정보를 조회
- Core Server가 `paramiko` 기반 SSH 접속 테스트 수행

관련 코드:

- `backend/theseus-api-server/src/main/java/com/theseus/api/domain/remoteworkspace/service/RemoteWorkspaceService.java`
- `backend/theseus-core-server/src/remote_workspace/resolver.py`
- `backend/theseus-core-server/src/remote_workspace/ssh_connector.py`

### 2-4. ToolPlan 생성 요청

1. 프로젝트 채팅 화면으로 이동
2. PLAN 모드 또는 ToolPlan 생성 요청 입력
3. 예시 프롬프트:
   ```text
   SSAFY-STOCK 서버의 프로젝트 구조를 분석하고, 주식 주문 내역을 조회할 수 있는 ToolPlan을 만들어줘.
   ```
4. 요청 후 진행 상태가 UI에 표시되는지 확인

시연 포인트:

- Frontend -> API Server 요청
- API Server -> Kafka `theseus.tool-plan.request`
- Core Server consumer가 request 처리
- Core Server -> Kafka `theseus.tool-plan.event`
- API Server가 event를 받아 SSE/상태 저장

### 2-5. Kafka / SSE 기반 진행 상태 표시

1. ToolPlan 생성 중 UI에서 진행률 또는 streaming chunk 확인
2. Kafka topic 상태 확인
   ```bash
   docker exec -it theseus-prod-kafka kafka-console-consumer \
     --bootstrap-server theseus-prod-kafka:29092 \
     --topic theseus.tool-plan.event \
     --from-beginning
   ```
3. Redis에 ToolPlanRun state가 저장되는지 확인 가능
   ```bash
   redis-cli -h <REDIS_HOST> -p <REDIS_PORT> KEYS "tool:plan:*:state"
   ```

시연 포인트:

- 장시간 LLM 작업을 HTTP blocking으로 처리하지 않고 Kafka/SSE로 상태 전달
- Redis/ElastiCache가 ToolPlanRun 진행 상태 캐시 역할 수행

### 2-6. 승인 플로우

1. 생성된 ToolPlan 내용을 확인
2. reviewer 또는 관리자 권한으로 승인 요청/승인 수행
3. 승인 후 ToolBuild 요청이 생성되는지 확인

시연 포인트:

- ToolPlan 생성과 ToolBuild 실행을 분리
- 승인 기반으로 Tool 생성 실행을 통제
- `permissionLevel` 1~5 기반 접근 제어

### 2-7. ToolBuild 및 Tool 실행

1. 승인된 ToolPlan에 대해 ToolBuild 실행
2. ToolBuild 진행 상태 확인
3. 완료 후 도구 목록에서 생성된 Tool 확인
4. Tool access level 표시 확인
5. ADMIN 계정에서 Tool access level 수정
6. 수정 완료 알림 확인

시연 포인트:

- Core Server가 Tool artifact 생성
- sandbox 검증 후 활성화
- DB `tools.tool_grade`와 metadata `permissionLevel` 동기화
- ADMIN이 UI에서 access level 수정 가능

관련 timeout:

```env
CORE_TOOL_BUILD_RUN_TIMEOUT_SECONDS=1800
```

운영 `.env`에 위 값이 들어가 있어야 ToolBuild 실행 timeout이 30분으로 적용된다.

### 2-8. Remote Workspace로 SSAFY-STOCK 서버 분석

1. 채팅에서 Remote Workspace가 연결된 상태로 질문 입력
   ```text
   SSAFY-STOCK 서버의 주문 처리 흐름을 분석하고 주요 API와 DB 테이블을 요약해줘.
   ```
2. Core Server가 remote read 도구를 통해 대상 서버의 파일 구조/내용을 분석
3. 분석 결과가 채팅에 출력되는지 확인

시연 포인트:

- AI가 로컬 코드가 아닌 외부 실행 서버 프로젝트를 SSH 기반으로 분석
- basePath 밖 접근은 차단
- write 도구는 `allowWriteExecution` 정책에 따라 제한

### 2-9. Vite dev server + SSH tunnel로 프론트 수정 즉시 확인

개발 중 운영 API를 바라보며 프론트를 빠르게 확인하는 시나리오이다.

1. API 접근이 필요한 경우 SSH tunnel 구성
   ```bash
   ssh -N -L 8080:<운영 API 내부 Host>:8080 <EC2_USER>@<EC2_HOST>
   ```
2. frontend env 설정
   ```env
   VITE_API_BASE_URL=http://localhost:8080
   ```
3. Vite dev server 실행
   ```bash
   cd frontend
   npm ci
   npm run dev -- --host 127.0.0.1 --port 3000
   ```
4. 브라우저 접속
   ```text
   http://127.0.0.1:3000
   ```

주의:

- SSH tunnel 대상 host/port는 운영 네트워크 구성에 따라 확인 필요이다.
- 5173 포트가 OS 예약 포트로 막히면 3000 등 다른 포트를 사용한다.

### 2-10. Jenkins를 통한 운영 배포

1. GitLab MR 생성
2. Jenkins CI/CD check 통과 확인
3. `dev` branch merge
4. Jenkins가 변경 파일 감지
5. 변경된 서비스만 Docker build/deploy

Jenkinsfile 기준 배포 명령:

```bash
docker compose --env-file infra/docker/prod/.env \
  -f infra/docker/prod/docker-compose.prod.yml \
  up -d --no-deps --build theseus-api-server
```

```bash
docker compose --env-file infra/docker/prod/.env \
  -f infra/docker/prod/docker-compose.prod.yml \
  up -d --no-deps --build theseus-core-server
```

```bash
docker compose --env-file infra/docker/prod/.env \
  -f infra/docker/prod/docker-compose.prod.yml \
  up -d --no-deps --build theseus-frontend theseus-nginx
```

시연 포인트:

- GitLab MR 기반 협업
- Jenkins pipeline 자동 build/test/deploy
- Docker Compose 기반 운영 서비스 재기동

## 3. 발표 시 강조 포인트

- 자연어 요청 -> ToolPlan -> 승인 -> ToolBuild -> Tool 실행으로 이어지는 AI Agent workflow
- Kafka 기반 비동기 ToolPlan/ToolBuild 처리
- SSE 기반 진행 상태 표시
- Redis/ElastiCache 기반 실행 상태 캐시
- Remote Workspace SSH 분석
- sandbox 기반 생성 Tool 검증
- 프로젝트/멤버/Tool access level 기반 권한 제어
- Jenkins + Docker Compose 기반 운영 배포 자동화

## 4. 확인 필요 항목

- 시연 계정과 권한
- 시연용 프로젝트 ID/name
- SSAFY-STOCK Remote Workspace 서버 접속 정보
- 운영 LLM provider/model/API key
- 운영 Redis/Kafka/RDS 접근 가능 여부
- Jenkins job URL 및 GitLab webhook 상태
- ToolBuild timeout 30분 설정 반영 여부
