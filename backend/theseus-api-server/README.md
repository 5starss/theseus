# Theseus API 서버

테세우스의 Spring Boot 기반 API 서버입니다.

## 로컬 Kafka Producer 설정

Kafka Producer 설정은 Spring 설정 파일과 환경 변수에서 로드합니다.

- Docker Compose 내부 실행 기준 bootstrap server: `theseus-local-kafka:29092`
- IDE 직접 실행 기준 bootstrap server: `localhost:19092`

`local` profile은 `SPRING_KAFKA_BOOTSTRAP_SERVERS` 환경 변수를 우선 사용하며, 값이 없으면 `localhost:19092`를 기본값으로 사용합니다.
