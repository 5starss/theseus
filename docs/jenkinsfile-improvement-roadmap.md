# Jenkinsfile 개선 로드맵

## 배경

현재 Theseus Jenkins Multibranch Pipeline은 단순한 배포 전략을 사용한다.

- `feature/*`, `fix/*`, MR 빌드는 checkout과 기본 검증만 수행한다.
- `dev` 브랜치 일반 빌드에서만 Jenkins Secret File로 운영 `.env`를 주입한다.
- `dev` 브랜치에서만 production Docker Compose config를 검증한다.
- `dev` 브랜치에서만 `docker compose up -d --build`로 배포한다.

이 전략은 production 배포 초기 안정화 단계에 맞춘 의도적인 선택이다. 현재 production Docker Compose 구성이 새로 추가된 상태이고, 최근 배포 실패도 런타임 패키징, 환경 변수, 타입 힌트 문제처럼 기본 기동 경로에서 발생했다. 따라서 초기에는 서비스별 부분 배포보다 전체 compose 기준 검증과 배포가 더 안전하다.

## 현재 기준

필수 Jenkins Credential:

- `theseus-prod-env`
  - Kind: Secret file
  - 내용: 운영용 `infra/docker/prod/.env`

현재 production compose 파일:

- `infra/docker/prod/docker-compose.prod.yml`
- `infra/docker/prod/.env.example`

현재 production 배포 명령:

```sh
docker compose --env-file infra/docker/prod/.env -f infra/docker/prod/docker-compose.prod.yml up -d --build
```

## 1단계: 전체 Compose 배포 유지, 검증 강화

목표: 배포 방식은 단순하게 유지하면서 런타임 오류를 배포 전에 더 많이 잡는다.

배포 전 검증 단계에 추가할 항목:

- Docker Compose config 검증:
  ```sh
  docker compose --env-file infra/docker/prod/.env -f infra/docker/prod/docker-compose.prod.yml config --quiet
  ```
- Core 서버 Python 문법/import 검증:
  ```sh
  python -m compileall backend/theseus-core-server/src
  python -m compileall backend/theseus-core-server/theseus_engine
  ```
- API 서버 빌드 또는 테스트 검증:
  ```sh
  cd backend/theseus-api-server
  chmod +x ./gradlew
  ./gradlew test
  ```
- Frontend 빌드 검증:
  ```sh
  cd frontend
  npm ci
  npm run build
  ```

완료 조건:

- `feature/*`, `fix/*`, MR 빌드에는 운영 secret을 주입하지 않는다.
- `dev` 빌드에서만 운영 `.env`를 주입한다.
- `dev` 빌드는 compile/build/config 검증 실패 시 배포 전에 중단된다.
- 배포 방식은 전체 `docker compose up -d --build`를 유지한다.

## 2단계: 변경 감지 추가, 배포 분기에는 사용하지 않음

목표: 어떤 영역이 변경되었는지 Jenkins 로그에서 확인할 수 있게 한다.

`Detect Changes` 단계를 추가해 변경 파일을 아래 기준으로 분류한다.

- `backend/theseus-api-server/**` -> API 서버 변경
- `backend/theseus-core-server/**` -> Core 서버 변경
- `frontend/**` -> Frontend 변경
- `infra/docker/prod/**` -> Production 인프라 변경
- `Jenkinsfile` -> Pipeline 변경
- 그 외 공통 문서/설정 변경 -> 아직 배포 최적화 대상 아님

중요 규칙:

- 2단계에서는 변경 감지를 배포 skip 조건으로 사용하지 않는다.
- 변경 감지는 로그, 검증 선택, 향후 부분 배포 준비 용도로만 사용한다.

완료 조건:

- Jenkins 로그에 변경 영역이 명확히 출력된다.
- `dev` 브랜치에서는 여전히 전체 compose 배포가 실행된다.
- MR 빌드는 여전히 배포하지 않는다.

## 3단계: 변경 감지를 검증 단계 선택에만 사용

목표: 불필요한 검증 비용을 줄이되, production 배포는 아직 전체 compose 기준으로 유지한다.

변경 영역에 따라 검증을 선택 실행한다.

- API 변경 -> API Gradle test/build 실행
- Core 변경 -> Python compileall 및 필요한 테스트 실행
- Frontend 변경 -> npm build 실행
- Production 인프라 변경 -> compose config 검증 항상 실행
- 알 수 없는 공통 변경 -> 전체 검증 실행

중요 규칙:

- production 배포 명령은 그대로 유지한다.
  ```sh
  docker compose --env-file infra/docker/prod/.env -f infra/docker/prod/docker-compose.prod.yml up -d --build
  ```

완료 조건:

- 변경된 서비스에 맞는 검증이 선택적으로 실행된다.
- 변경 영역을 판단할 수 없으면 전체 검증으로 fallback한다.
- 검증 성공 후 `dev`에서는 여전히 전체 compose 배포가 실행된다.

## 4단계: 서비스별 부분 배포 도입

목표: production 배포가 안정화된 뒤 변경된 서비스만 배포한다.

서비스별 배포 매핑:

- API 서버 변경:
  ```sh
  docker compose --env-file infra/docker/prod/.env -f infra/docker/prod/docker-compose.prod.yml up -d --no-deps --build theseus-api-server
  ```
- Core 서버 변경:
  ```sh
  docker compose --env-file infra/docker/prod/.env -f infra/docker/prod/docker-compose.prod.yml up -d --no-deps --build theseus-core-server
  ```
- Frontend 변경:
  ```sh
  docker compose --env-file infra/docker/prod/.env -f infra/docker/prod/docker-compose.prod.yml up -d --no-deps --build theseus-frontend
  ```

아래 변경은 항상 전체 compose 배포로 처리한다.

- `infra/docker/prod/**`
- Kafka 설정 변경
- `.env.example` 변경
- Docker network/volume 변경
- 서비스 간 계약 변경
- 변경 영향 범위를 판단하기 어려운 경우

완료 조건:

- 각 서비스별 health/status 확인 기준이 있다.
- 전체 배포 fallback을 유지한다.
- Jenkins 로그에 어떤 서비스를 왜 배포했는지 명확히 남는다.
- 운영자가 필요할 때 수동으로 전체 배포를 강제할 수 있다.

## 5단계: 운영 안정성 보강

목표: 배포 실패 시 원인 파악과 복구가 쉬운 Jenkinsfile로 개선한다.

추가할 항목:

- 배포 후 컨테이너 health/status 확인
- 실패 시 최근 컨테이너 로그 출력:
  ```sh
  docker compose --env-file infra/docker/prod/.env -f infra/docker/prod/docker-compose.prod.yml logs --tail=100
  ```
- 팀 정책상 필요하면 배포 전 수동 승인 단계 추가
- rollback에 필요한 이미지를 지우지 않도록 image cleanup 정책 조정
- rollback 절차 문서 또는 Jenkins parameter 추가

완료 조건:

- 배포 실패 시 Jenkins 로그만으로 기본 원인 파악이 가능하다.
- cleanup이 rollback에 필요한 이미지를 과도하게 삭제하지 않는다.
- 수동 복구 절차가 문서화되어 있다.

## 다음 추천 작업

가장 먼저 1단계를 진행한다.

추천 JIRA 제목:

```text
[CI/CD] Jenkinsfile production validation 단계 보강
```

추천 브랜치:

```text
feat/S14P31A308-XXX/jenkinsfile-prod-validation
```

추천 커밋 메시지:

```text
S14P31A308-XXX [feat]: Jenkinsfile production validation 단계 보강
```
