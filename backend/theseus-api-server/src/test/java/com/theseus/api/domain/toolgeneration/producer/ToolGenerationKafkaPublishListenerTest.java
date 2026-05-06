package com.theseus.api.domain.toolgeneration.producer;

import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.verifyNoMoreInteractions;

import com.theseus.api.domain.toolgeneration.event.ToolGenerationKafkaPublishEvent;
import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;
import org.mockito.Mock;
import org.mockito.junit.jupiter.MockitoExtension;

@ExtendWith(MockitoExtension.class)
class ToolGenerationKafkaPublishListenerTest {

	@Mock
	private ToolGenerationKafkaProducer toolGenerationKafkaProducer;

	@Test
	@DisplayName("AFTER_COMMIT 이벤트가 생성 요청이면 generation producer를 호출한다")
	void publishSendsGenerationRequestWhenEventIsNotRegeneration() {
		ToolGenerationKafkaPublishListener listener = new ToolGenerationKafkaPublishListener(toolGenerationKafkaProducer);
		Object payload = new Object();

		listener.publish(new ToolGenerationKafkaPublishEvent("run-1", payload, false));

		verify(toolGenerationKafkaProducer).sendToolGenerationRequest("run-1", payload);
		verifyNoMoreInteractions(toolGenerationKafkaProducer);
	}

	@Test
	@DisplayName("AFTER_COMMIT 이벤트가 재생성 요청이면 regeneration producer를 호출한다")
	void publishSendsRegenerationRequestWhenEventIsRegeneration() {
		ToolGenerationKafkaPublishListener listener = new ToolGenerationKafkaPublishListener(toolGenerationKafkaProducer);
		Object payload = new Object();

		listener.publish(new ToolGenerationKafkaPublishEvent("run-2", payload, true));

		verify(toolGenerationKafkaProducer).sendToolRegenerationRequest("run-2", payload);
		verifyNoMoreInteractions(toolGenerationKafkaProducer);
	}
}
