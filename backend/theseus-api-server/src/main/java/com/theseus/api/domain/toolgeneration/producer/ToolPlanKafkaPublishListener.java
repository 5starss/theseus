package com.theseus.api.domain.toolgeneration.producer;

import com.theseus.api.domain.toolgeneration.event.ToolPlanKafkaPublishEvent;
import com.theseus.api.domain.toolgeneration.service.ToolPlanGenerationService;
import lombok.RequiredArgsConstructor;
import org.springframework.stereotype.Component;
import org.springframework.transaction.event.TransactionPhase;
import org.springframework.transaction.event.TransactionalEventListener;

@RequiredArgsConstructor
@Component
public class ToolPlanKafkaPublishListener {

	private final ToolGenerationKafkaProducer toolGenerationKafkaProducer;
	private final ToolPlanGenerationService toolPlanGenerationService;

	@TransactionalEventListener(phase = TransactionPhase.AFTER_COMMIT)
	public void publish(ToolPlanKafkaPublishEvent event) {
		try {
			toolGenerationKafkaProducer.sendToolPlanRequest(event.key(), event.payload())
				.whenComplete((result, exception) -> {
					if (exception != null) {
						toolPlanGenerationService.markRunPublishFailed(event.key(), exception);
					}
				});
		} catch (RuntimeException exception) {
			toolPlanGenerationService.markRunPublishFailed(event.key(), exception);
		}
	}
}
