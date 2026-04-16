## Git Hook 설치 (필수)
이 프로젝트는 커밋 메시지에 Jira 이슈 키를 자동으로 붙이기 위해
Git hook을 사용합니다.

  1. 현재 브랜치명에서 Jira 이슈 키 추출 ([A-Z0-9]{2,}-[0-9]+ 패턴 예:S14P-123)
  2. 이슈 키가 없으면 → 아무것도 안 
  3. 커밋 메시지에 이미 이슈 키가 있으면 → 아무것도 안 함
  4. 첫 줄 맨 앞에 이슈키 삽입

  예시:
  브랜치명: feature/S14P-42-login
  커밋 메시지 입력: "로그인 기능 추가"
  → 결과: "S14P-42 로그인 기능 추가"

## 최초 1회 실행

```bash
sh tools/git-hooks/install.sh
```

# Stock Project 로컬 개발 세팅 가이드

우리 프로젝트의 초기 환경 구축 및 실행을 위한 가이드입니다. 팀원 여러분은 아래 순서대로 세팅을 완료해 주세요.

---

## 1. 전제 조건 (Prerequisites)
* **Docker Desktop** 설치 및 실행
* **IntelliJ IDEA** 
* **Java 21** 

---

## 2. 인프라 환경 구축 (Docker)

우리 프로젝트는 마이크로서비스 간의 원활한 통신을 위해 **공통 외부 네트워크**를 
사용합니다. **최초 1회** 아래 명령어를 터미널에서 실행해 주세요.

```bash
# 공통 네트워크 생성 (필수)
docker network create stock-network

# 인프라 컨테이너 실행
cd docker-compose
docker-compose -f docker-compose-infra.yml up -d

```
## 3. 환경변수 세팅
각 서버 모듈의 루트 폴더에 .env 파일을 생성해 주세요.

[파일 위치]

backend/api-gateway/.env

backend/core-api-server/.env

backend/market-server/.env

backend/matcher-server/.env


