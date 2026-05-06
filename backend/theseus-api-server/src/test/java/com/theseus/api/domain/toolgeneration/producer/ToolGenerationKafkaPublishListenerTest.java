package com.theseus.api.domain.toolgeneration.producer;

import static org.mockito.Mockito.verify;

import com.theseus.api.domain.toolgeneration.event.ToolGenerationKafkaPublishEvent;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;
import org.mockito.Mock;
import org.mockito.junit.jupiter.MockitoExtension;

@ExtendWith(MockitoExtension.class)
class ToolGenerationKafkaPublishListenerTest {

	@Mock
	private ToolGenerationKafkaProducer toolGenerationKafkaProducer;

	@Test
	void publishSendsGenerationRequestWhenEventIsNotRegeneration() {
		ToolGenerationKafkaPublishListener listener = new ToolGenerationKafkaPublishListener(toolGenerationKafkaProducer);
		Object payload = new Object();

		listener.publish(new ToolGenerationKafkaPublishEvent("run-1", payload, false));

		verify(toolGenerationKafkaProducer).sendToolGenerationRequest("run-1", payload);
	}

	@Test
	void publishSendsRegenerationRequestWhenEventIsRegeneration() {
		ToolGenerationKafkaPublishListener listener = new ToolGenerationKafkaPublishListener(toolGenerationKafkaProducer);
		Object payload = new Object();

		listener.publish(new ToolGenerationKafkaPublishEvent("run-2", payload, true));

		verify(toolGenerationKafkaProducer).sendToolRegenerationRequest("run-2", payload);
	}
}
