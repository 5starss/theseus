# Prod Kafka UI

Prod Kafka UI is configured as a read-only monitoring tool for the Docker Kafka broker.

## Access

The service binds to localhost on the EC2 host by default:

```sh
KAFKA_UI_HOST_PORT=8091
```

Use an SSH tunnel from your workstation:

```sh
ssh -L 8091:127.0.0.1:8091 ubuntu@k14a308.p.ssafy.io
```

Then open:

```text
http://localhost:8091
```

## Security

- The compose mapping uses `127.0.0.1:${KAFKA_UI_HOST_PORT:-8091}:8080`, so Kafka UI is not exposed directly to the public internet.
- `KAFKA_CLUSTERS_0_READONLY=true` is enabled.
- If direct external access is required later, change the port binding deliberately and restrict EC2 security group inbound rules to approved source IPs only.

## Checks

```sh
docker compose --env-file .env -f docker-compose.prod.yml up -d theseus-prod-kafka-ui
docker logs theseus-prod-kafka-ui --tail=100
curl -I http://127.0.0.1:${KAFKA_UI_HOST_PORT:-8091}
```

In the UI, confirm:

- cluster name is `theseus-prod`
- the 7 Theseus topics are visible
- consumer group status is visible
