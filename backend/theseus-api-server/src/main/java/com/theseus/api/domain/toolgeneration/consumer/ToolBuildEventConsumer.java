package com.theseus.api.domain.toolgeneration.consumer;

import com.theseus.api.domain.toolgeneration.event.ToolBuildEvent;
import com.theseus.api.domain.toolgeneration.event.ToolBuildEventType;
import com.theseus.api.domain.toolgeneration.service.ToolBuildEventService;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.kafka.annotation.KafkaListener;
import org.springframework.stereotype.Component;

@Slf4j
@RequiredArgsConstructor
@Component
public class ToolBuildEventConsumer {

	private final ToolBuildEventService toolBuildEventService;

	@KafkaListener(
		topics = "${theseus.kafka.topics.tool-build-event}",
		containerFactory = "toolBuildKafkaListenerContainerFactory"
	)
	public void consume(ToolBuildEvent event) {
		if (event == null) {
			log.warn(">>>> Empty ToolBuild event skipped.");
			return;
		}

		ToolBuildEventType eventType = event.getEventTypeValue();
		try {
			if (ToolBuildEventType.TOOL_BUILD_COMPLETED.equals(eventType)) {
				toolBuildEventService.handleCompleted(event);
				return;
			}
			if (ToolBuildEventType.TOOL_BUILD_FAILED.equals(eventType)) {
				toolBuildEventService.handleFailed(event);
				return;
			}
			if (ToolBuildEventType.PROGRESS.equals(eventType) || ToolBuildEventType.CHUNK.equals(eventType)) {
				log.info(
					">>>> ToolBuild progress event skipped for DB handling. runId={}, eventType={}, sequence={}",
					event.getRunId(),
					event.getEventType(),
					event.getEventSequence()
				);
				return;
			}

			log.warn(
				">>>> Unsupported ToolBuild event skipped. runId={}, eventType={}, sequence={}",
				event.getRunId(),
				event.getEventType(),
				event.getEventSequence()
			);
		} catch (Exception exception) {
			log.error(
				">>>> ToolBuild event handling failed. runId={}, eventType={}, sequence={}",
				event.getRunId(),
				event.getEventType(),
				event.getEventSequence(),
				exception
			);
		}
	}
}
