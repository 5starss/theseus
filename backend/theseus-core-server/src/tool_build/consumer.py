from __future__ import annotations

import asyncio
import json
import logging

from src.config import settings
from src.tool_build.processor import ToolBuildProcessor
from src.tool_build.publisher import KafkaToolBuildEventPublisher

logger = logging.getLogger(__name__)


class ToolBuildKafkaConsumer:
    def __init__(self) -> None:
        self.bootstrap_servers = settings.CORE_KAFKA_BOOTSTRAP_SERVERS
        self.group_id = settings.CORE_KAFKA_TOOL_BUILD_CONSUMER_GROUP_ID
        self.topic = settings.KAFKA_TOPIC_TOOL_BUILD_REQUEST
        self.publisher = KafkaToolBuildEventPublisher()
        self.processor = ToolBuildProcessor(publisher=self.publisher)
        self._consumer = None
        self._task: asyncio.Task | None = None

    async def start(self) -> None:
        if self._task is not None:
            return
        from aiokafka import AIOKafkaConsumer

        self._consumer = AIOKafkaConsumer(
            self.topic,
            bootstrap_servers=self.bootstrap_servers,
            group_id=self.group_id,
            enable_auto_commit=False,
            auto_offset_reset="earliest",
            value_deserializer=lambda value: json.loads(value.decode("utf-8")),
            key_deserializer=lambda value: value.decode("utf-8") if value else None,
        )
        await self._consumer.start()
        await self.publisher.start()
        self._task = asyncio.create_task(self._consume_loop())
        logger.info(
            "Tool build Kafka consumer started. bootstrap=%s topic=%s group=%s",
            self.bootstrap_servers,
            self.topic,
            self.group_id,
        )

    async def stop(self) -> None:
        if self._task is not None:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
            self._task = None
        if self._consumer is not None:
            await self._consumer.stop()
            self._consumer = None
        await self.publisher.stop()
        logger.info("Tool build Kafka consumer stopped.")

    async def _consume_loop(self) -> None:
        assert self._consumer is not None
        async for message in self._consumer:
            try:
                await self.processor.process_message(message.value)
                await self._consumer.commit()
            except Exception as exc:
                logger.error("Tool build Kafka message handling failed: %s", exc, exc_info=True)


async def start_tool_build_consumer() -> ToolBuildKafkaConsumer | None:
    if not settings.CORE_KAFKA_CONSUMER_ENABLED:
        logger.info("Tool build Kafka consumer is disabled.")
        return None

    consumer = ToolBuildKafkaConsumer()
    await consumer.start()
    return consumer
