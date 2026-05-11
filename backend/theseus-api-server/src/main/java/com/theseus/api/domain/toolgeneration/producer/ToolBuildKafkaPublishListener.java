package com.theseus.api.domain.toolgeneration.producer;

import com.theseus.api.domain.tool.service.ToolApprovalService;
import com.theseus.api.domain.toolgeneration.event.ToolBuildKafkaPublishEvent;
import lombok.RequiredArgsConstructor;
import org.springframework.stereotype.Component;
import org.springframework.transaction.event.TransactionPhase;
import org.springframework.transaction.event.TransactionalEventListener;

@RequiredArgsConstructor
@Component
public class ToolBuildKafkaPublishListener {

	private final ToolGenerationKafkaProducer toolGenerationKafkaProducer;
	private final ToolApprovalService toolApprovalService;

	@TransactionalEventListener(phase = TransactionPhase.AFTER_COMMIT)
	public void publish(ToolBuildKafkaPublishEvent event) {
		try {
			toolGenerationKafkaProducer.sendToolBuildRequest(event.key(), event.payload())
				.whenComplete((result, exception) -> {
					if (exception != null) {
						toolApprovalService.markBuildRunPublishFailed(event.key(), exception);
					}
				});
		} catch (RuntimeException exception) {
			toolApprovalService.markBuildRunPublishFailed(event.key(), exception);
		}
	}
}
