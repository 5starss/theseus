# Theseus API Server

Spring Boot based API Server for Theseus.

## Local Development

Recommended flow:

1. Run MySQL, Kafka, Redis with Docker Compose.
2. Run the API Server from the IDE for debugging and fast restart.
3. Use host machine endpoints from the IDE process.

```text
SPRING_DATASOURCE_URL=jdbc:mysql://localhost:13306/theseus
SPRING_KAFKA_BOOTSTRAP_SERVERS=localhost:19092
SPRING_DATA_REDIS_HOST=localhost
SPRING_DATA_REDIS_PORT=16379
```

Docker Compose internal endpoints are different:

- Kafka: `theseus-local-kafka:29092`
- Redis: `theseus-local-redis:6379`

Use the internal endpoints only when the API Server itself runs as a Docker
container. If the API Server runs from the IDE, use `localhost` endpoints.

Stop the API Server container before starting the API Server from the IDE:

```bash
docker stop theseus-local-api-server
```
