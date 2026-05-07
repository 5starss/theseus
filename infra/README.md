# Infra

Local, development, and production infrastructure configuration lives here.

## Local Docker Compose

Recommended backend development flow:

1. Run local infra with Docker Compose.
2. Run Spring Boot API Server from the IDE.
3. Use the host machine endpoints from the API Server.

Run local infra only:

```bash
docker compose \
  -f infra/docker/local/docker-compose.infra.yml \
  up -d
```

Run the API Server from the IDE with:

```text
SPRING_DATASOURCE_URL=jdbc:mysql://localhost:13306/theseus
SPRING_KAFKA_BOOTSTRAP_SERVERS=localhost:19092
SPRING_DATA_REDIS_HOST=localhost
SPRING_DATA_REDIS_PORT=16379
```

Do not run `theseus-local-api-server` while running the API Server from the IDE,
because both processes use port `8080` by default.

Run the local infra, API server, and core server together only for full Docker integration checks:

```bash
docker compose \
  -f infra/docker/local/docker-compose.infra.yml \
  -f infra/docker/local/docker-compose.api.yml \
  -f infra/docker/local/docker-compose.core.yml \
  up -d
```

Kafka UI:

```text
http://localhost:18080
```

Run Redis only:

```bash
docker compose \
  -f infra/docker/local/docker-compose.infra.yml \
  up -d theseus-local-redis
```

Check Redis:

```bash
docker exec -it theseus-local-redis redis-cli ping
```

Check Kafka topics:

```bash
docker exec -it theseus-local-kafka kafka-topics \
  --bootstrap-server theseus-local-kafka:29092 \
  --list
```

Local Kafka endpoints:

- Container network: `theseus-local-kafka:29092`
- Host machine: `localhost:19092`

Local Redis endpoints:

- Container network: `theseus-local-redis:6379`
- Host machine: `localhost:16379`
