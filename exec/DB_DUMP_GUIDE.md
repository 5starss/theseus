# Theseus DB Dump / Restore Guide

본 문서는 Theseus의 MySQL, PostgreSQL 데이터베이스 덤프 생성 및 복원 방법을 정리한다. 실제 운영 접속 정보는 문서에 평문으로 적지 않고 `<입력 필요>`, `<SECRET>` 형태로 작성한다.

## 1. DB 구성

| DB | 사용 주체 | 로컬 구성 | 운영 구성 |
| --- | --- | --- | --- |
| MySQL | API Server | `mysql:8.4`, host `localhost:13306`, DB `theseus` | MySQL 호환 RDS, 접속 정보 확인 필요 |
| PostgreSQL + pgvector | Core Server | `pgvector/pgvector:pg16`, host `localhost:15432`, DB `theseus_core` | PostgreSQL RDS, 접속 정보 확인 필요 |
| Redis | API Server cache/token/state | `redis:7.2-alpine`, host `localhost:16379` | ElastiCache Redis |

근거:

- `infra/docker/local/docker-compose.infra.yml`
- `backend/theseus-api-server/src/main/resources/application-local.yml`
- `backend/theseus-core-server/src/config.py`
- `infra/docker/prod/.env.example`

## 2. MySQL 덤프 생성

### 2-1. 로컬 Docker MySQL 덤프

```bash
docker exec theseus-local-mysql mysqldump \
  -u<MYSQL_USER> \
  -p<MYSQL_PASSWORD> \
  --single-transaction \
  --routines \
  --triggers \
  theseus > theseus_mysql_dump.sql
```

예시의 계정/비밀번호는 실제 로컬 `.env.local`을 확인해서 입력한다.

```text
<MYSQL_USER>=<입력 필요>
<MYSQL_PASSWORD>=<SECRET>
```

### 2-2. 운영 RDS MySQL 덤프

운영 서버 또는 접근 가능한 bastion 환경에서 실행한다.

```bash
mysqldump \
  -h <MYSQL_RDS_HOST> \
  -P 3306 \
  -u <MYSQL_USER> \
  -p \
  --single-transaction \
  --routines \
  --triggers \
  <MYSQL_DATABASE> > theseus_mysql_prod_dump.sql
```

입력 필요:

```text
MYSQL_RDS_HOST=<입력 필요>
MYSQL_USER=<입력 필요>
MYSQL_DATABASE=<입력 필요>
MYSQL_PASSWORD=<SECRET>
```

`mysqldump`가 서버에 없으면 일회성 Docker client를 사용할 수 있다.

```bash
docker run --rm -i mysql:8.4 mysqldump \
  -h <MYSQL_RDS_HOST> \
  -P 3306 \
  -u <MYSQL_USER> \
  -p \
  --single-transaction \
  --routines \
  --triggers \
  <MYSQL_DATABASE> > theseus_mysql_prod_dump.sql
```

## 3. MySQL 복원

### 3-1. 로컬 Docker MySQL 복원

```bash
docker exec -i theseus-local-mysql mysql \
  -u<MYSQL_USER> \
  -p<MYSQL_PASSWORD> \
  theseus < theseus_mysql_dump.sql
```

### 3-2. 운영 RDS MySQL 복원

운영 DB 복원은 반드시 백업과 점검 후 수행한다.

```bash
mysql \
  -h <MYSQL_RDS_HOST> \
  -P 3306 \
  -u <MYSQL_USER> \
  -p \
  <MYSQL_DATABASE> < theseus_mysql_prod_dump.sql
```

주의:

- 운영 복원 전 기존 DB snapshot 또는 별도 dump를 반드시 생성한다.
- 운영 서비스 중 복원 시 데이터 정합성 문제가 발생할 수 있으므로 maintenance window를 확보한다.

## 4. PostgreSQL 덤프 생성

### 4-1. 로컬 Docker PostgreSQL 덤프

```bash
docker exec theseus-local-postgres pg_dump \
  -U <POSTGRES_USER> \
  -d theseus_core \
  -Fc \
  -f /tmp/theseus_core.dump

docker cp theseus-local-postgres:/tmp/theseus_core.dump ./theseus_core.dump
```

입력 필요:

```text
POSTGRES_USER=<입력 필요>
POSTGRES_PASSWORD=<SECRET>
```

비밀번호가 필요한 경우:

```bash
docker exec -e PGPASSWORD=<SECRET> theseus-local-postgres pg_dump \
  -U <POSTGRES_USER> \
  -d theseus_core \
  -Fc \
  -f /tmp/theseus_core.dump
```

### 4-2. 운영 PostgreSQL RDS 덤프

```bash
PGPASSWORD=<SECRET> pg_dump \
  -h <POSTGRES_RDS_HOST> \
  -p 5432 \
  -U <POSTGRES_USER> \
  -d <POSTGRES_DATABASE> \
  -Fc \
  -f theseus_core_prod.dump
```

입력 필요:

```text
POSTGRES_RDS_HOST=<입력 필요>
POSTGRES_USER=<입력 필요>
POSTGRES_DATABASE=<입력 필요>
POSTGRES_PASSWORD=<SECRET>
```

`pg_dump`가 서버에 없으면 일회성 Docker client를 사용할 수 있다.

```bash
docker run --rm -e PGPASSWORD=<SECRET> -v "$PWD:/dump" postgres:16 \
  pg_dump \
  -h <POSTGRES_RDS_HOST> \
  -p 5432 \
  -U <POSTGRES_USER> \
  -d <POSTGRES_DATABASE> \
  -Fc \
  -f /dump/theseus_core_prod.dump
```

## 5. PostgreSQL 복원

### 5-1. 로컬 Docker PostgreSQL 복원

```bash
docker cp ./theseus_core.dump theseus-local-postgres:/tmp/theseus_core.dump

docker exec theseus-local-postgres pg_restore \
  -U <POSTGRES_USER> \
  -d theseus_core \
  --clean \
  --if-exists \
  /tmp/theseus_core.dump
```

### 5-2. 운영 PostgreSQL RDS 복원

```bash
PGPASSWORD=<SECRET> pg_restore \
  -h <POSTGRES_RDS_HOST> \
  -p 5432 \
  -U <POSTGRES_USER> \
  -d <POSTGRES_DATABASE> \
  --clean \
  --if-exists \
  theseus_core_prod.dump
```

주의:

- `--clean --if-exists`는 기존 object를 삭제 후 복원한다.
- 운영 DB 복원 전 snapshot 또는 별도 dump를 반드시 생성한다.
- pgvector extension이 필요한 경우 대상 DB에 extension 설치 여부를 확인한다.

## 6. Redis 백업 참고

Redis는 주로 refresh token과 ToolPlanRun state cache에 사용된다. 영속 원장 DB가 아니므로 제출용 DB dump 대상은 MySQL/PostgreSQL을 우선한다.

필요 시 Redis key 확인:

```bash
redis-cli -h <REDIS_HOST> -p <REDIS_PORT> KEYS "RT:*"
redis-cli -h <REDIS_HOST> -p <REDIS_PORT> KEYS "tool:plan:*:state"
```

운영 ElastiCache 접근은 VPC/security group 제약이 있으므로 접속 경로 확인이 필요하다.

## 7. 확인 필요 항목

- 운영 MySQL RDS host, database, user
- 운영 PostgreSQL RDS host, database, user
- 운영 DB dump 권한 계정
- 운영 서버에 `mysql`, `mysqldump`, `pg_dump`, `pg_restore` 설치 여부
- 운영 DB snapshot 정책
- Redis/ElastiCache 백업 필요 여부
