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

When the core compose file is included, Docker Compose also builds the
`theseus-sandbox:py311-tools` image from
`backend/theseus-core-server/Dockerfile.sandbox`. Core uses the host Docker
daemon through `/var/run/docker.sock`, so this image tag must exist on the same
Docker host before ToolBuild sandbox validation can run.

The core compose file also runs a short `theseus-core-permissions` init service
that creates and chowns the sandbox temp/custom-tool bind mount directories for
the Core container user. Docker socket access still depends on `DOCKER_GID`
matching the group id of `/var/run/docker.sock` on the host.

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
