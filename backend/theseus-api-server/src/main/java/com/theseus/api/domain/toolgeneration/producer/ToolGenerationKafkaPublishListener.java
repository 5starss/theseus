package com.theseus.api.domain.toolgeneration.producer;

import com.theseus.api.domain.toolgeneration.event.ToolGenerationKafkaPublishEvent;
import lombok.RequiredArgsConstructor;
import org.springframework.stereotype.Component;
import org.springframework.transaction.event.TransactionPhase;
import org.springframework.transaction.event.TransactionalEventListener;

@RequiredArgsConstructor
@Component
public class ToolGenerationKafkaPublishListener {

	private final ToolGenerationKafkaProducer toolGenerationKafkaProducer;

	@TransactionalEventListener(phase = TransactionPhase.AFTER_COMMIT)
	public void publish(ToolGenerationKafkaPublishEvent event) {
		if (event.regeneration()) {
			toolGenerationKafkaProducer.sendToolRegenerationRequest(event.key(), event.payload());
			return;
		}

		toolGenerationKafkaProducer.sendToolGenerationRequest(event.key(), event.payload());
	}
}
