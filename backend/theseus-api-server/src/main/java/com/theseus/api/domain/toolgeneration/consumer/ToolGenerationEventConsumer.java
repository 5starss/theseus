package com.theseus.api.domain.toolgeneration.consumer;

import com.theseus.api.domain.toolgeneration.event.ToolGenerationEvent;
import com.theseus.api.domain.toolgeneration.event.ToolGenerationEventType;
import com.theseus.api.domain.toolgeneration.service.ToolGenerationEventService;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.kafka.annotation.KafkaListener;
import org.springframework.stereotype.Component;

@Slf4j
@RequiredArgsConstructor
@Component
public class ToolGenerationEventConsumer {

	private final ToolGenerationEventService toolGenerationEventService;

	@KafkaListener(topics = "${theseus.kafka.topics.tool-generation-event}")
	public void consume(ToolGenerationEvent event) {
		if (event == null) {
			log.warn(">>>> Empty Tool generation event skipped.");
			return;
		}

		ToolGenerationEventType eventType = event.getEventTypeValue();
		try {
			if (ToolGenerationEventType.TOOL_GENERATION_COMPLETED.equals(eventType)) {
				toolGenerationEventService.handleCompleted(event);
				return;
			}
			if (ToolGenerationEventType.TOOL_GENERATION_FAILED.equals(eventType)) {
				toolGenerationEventService.handleFailed(event);
				return;
			}
			if (ToolGenerationEventType.PROGRESS.equals(eventType)) {
				toolGenerationEventService.handleProgress(event);
				return;
			}
			if (ToolGenerationEventType.CHUNK.equals(eventType)) {
				toolGenerationEventService.handleChunk(event);
				return;
			}

			log.warn(
				">>>> Unsupported Tool generation event skipped. runId={}, eventType={}, toolId={}",
				event.getRunId(),
				event.getEventType(),
				event.getToolId()
			);
		} catch (Exception exception) {
			log.error(
				">>>> Tool generation event handling failed. runId={}, eventType={}, toolId={}",
				event.getRunId(),
				event.getEventType(),
				event.getToolId(),
				exception
			);
		}
	}
}
