from __future__ import annotations

import json
import logging
from typing import Any

from pydantic import BaseModel

from src.config import settings

logger = logging.getLogger(__name__)


class ToolBuildEventPublisher:
    async def publish(self, key: str, event: BaseModel | dict[str, Any]) -> None:
        raise NotImplementedError


class KafkaToolBuildEventPublisher(ToolBuildEventPublisher):
    def __init__(self) -> None:
        self.bootstrap_servers = settings.CORE_KAFKA_BOOTSTRAP_SERVERS
        self.topic = settings.KAFKA_TOPIC_TOOL_BUILD_EVENT
        self._producer = None

    async def start(self) -> None:
        if self._producer is not None:
            return
        from aiokafka import AIOKafkaProducer

        self._producer = AIOKafkaProducer(
            bootstrap_servers=self.bootstrap_servers,
            value_serializer=lambda value: json.dumps(value, ensure_ascii=False).encode("utf-8"),
            key_serializer=lambda value: value.encode("utf-8") if value is not None else None,
        )
        await self._producer.start()
        logger.info("Kafka Tool build event producer started.")

    async def stop(self) -> None:
        if self._producer is None:
            return
        await self._producer.stop()
        self._producer = None
        logger.info("Kafka Tool build event producer stopped.")

    async def publish(self, key: str, event: BaseModel | dict[str, Any]) -> None:
        if self._producer is None:
            await self.start()
        payload = event.model_dump(mode="json", by_alias=True) if isinstance(event, BaseModel) else event
        await self._producer.send_and_wait(self.topic, key=key, value=payload)
