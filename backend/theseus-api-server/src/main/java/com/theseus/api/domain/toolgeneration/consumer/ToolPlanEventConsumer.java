package com.theseus.api.domain.toolgeneration.consumer;

import com.theseus.api.domain.toolgeneration.event.ToolPlanEvent;
import com.theseus.api.domain.toolgeneration.event.ToolPlanEventType;
import com.theseus.api.domain.toolgeneration.service.ToolPlanEventService;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.kafka.annotation.KafkaListener;
import org.springframework.stereotype.Component;

@Slf4j
@RequiredArgsConstructor
@Component
public class ToolPlanEventConsumer {

	private final ToolPlanEventService toolPlanEventService;

	@KafkaListener(
		topics = "${theseus.kafka.topics.tool-plan-event}",
		containerFactory = "toolPlanKafkaListenerContainerFactory"
	)
	public void consume(ToolPlanEvent event) {
		if (event == null) {
			log.warn(">>>> Empty ToolPlan event skipped.");
			return;
		}

		ToolPlanEventType eventType = event.getEventTypeValue();
		try {
			if (ToolPlanEventType.TOOL_PLAN_COMPLETED.equals(eventType)) {
				toolPlanEventService.handleCompleted(event);
				return;
			}
			if (ToolPlanEventType.TOOL_PLAN_SKIPPED.equals(eventType)) {
				toolPlanEventService.handleSkipped(event);
				return;
			}
			if (ToolPlanEventType.TOOL_PLAN_FAILED.equals(eventType)) {
				toolPlanEventService.handleFailed(event);
				return;
			}
			if (ToolPlanEventType.PROGRESS.equals(eventType) || ToolPlanEventType.CHUNK.equals(eventType)) {
				log.info(
					">>>> ToolPlan progress event skipped for DB handling. runId={}, eventType={}, sequence={}",
					event.getRunId(),
					event.getEventType(),
					event.getEventSequence()
				);
				return;
			}

			log.warn(
				">>>> Unsupported ToolPlan event skipped. runId={}, eventType={}, sequence={}",
				event.getRunId(),
				event.getEventType(),
				event.getEventSequence()
			);
		} catch (Exception exception) {
			log.error(
				">>>> ToolPlan event handling failed. runId={}, eventType={}, sequence={}",
				event.getRunId(),
				event.getEventType(),
				event.getEventSequence(),
				exception
			);
		}
	}
}
