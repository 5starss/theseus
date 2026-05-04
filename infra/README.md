# Infra

Local, development, and production infrastructure configuration lives here.

## Local Docker Compose

Run the local infra, API server, and core server together:

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

Check Kafka topics:

```bash
docker exec -it theseus-local-kafka kafka-topics \
  --bootstrap-server theseus-local-kafka:29092 \
  --list
```

Local Kafka endpoints:

- Container network: `theseus-local-kafka:29092`
- Host machine: `localhost:19092`
