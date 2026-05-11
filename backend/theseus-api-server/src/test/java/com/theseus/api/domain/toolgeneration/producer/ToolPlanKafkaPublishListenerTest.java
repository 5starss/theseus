package com.theseus.api.domain.toolgeneration.producer;

import static org.mockito.Mockito.doThrow;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.verifyNoInteractions;
import static org.mockito.Mockito.when;

import com.theseus.api.domain.toolgeneration.event.ToolPlanKafkaPublishEvent;
import com.theseus.api.domain.toolgeneration.service.ToolPlanGenerationService;
import java.util.concurrent.CompletableFuture;
import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;
import org.mockito.Mock;
import org.mockito.junit.jupiter.MockitoExtension;

@ExtendWith(MockitoExtension.class)
class ToolPlanKafkaPublishListenerTest {

	@Mock
	private ToolGenerationKafkaProducer toolGenerationKafkaProducer;

	@Mock
	private ToolPlanGenerationService toolPlanGenerationService;

	@Test
	@DisplayName("AFTER_COMMIT 이벤트가 발생하면 ToolPlan request producer를 호출한다")
	void publishSendsToolPlanRequest() {
		ToolPlanKafkaPublishListener listener = new ToolPlanKafkaPublishListener(
			toolGenerationKafkaProducer,
			toolPlanGenerationService
		);
		Object payload = new Object();
		when(toolGenerationKafkaProducer.sendToolPlanRequest("run-1", payload))
			.thenReturn(CompletableFuture.completedFuture(null));

		listener.publish(new ToolPlanKafkaPublishEvent("run-1", payload));

		verify(toolGenerationKafkaProducer).sendToolPlanRequest("run-1", payload);
		verifyNoInteractions(toolPlanGenerationService);
	}

	@Test
	@DisplayName("Kafka 발행 실패가 발생하면 ToolPlanRun 실패 처리를 요청한다")
	void publishMarksRunFailedWhenKafkaSendFails() {
		ToolPlanKafkaPublishListener listener = new ToolPlanKafkaPublishListener(
			toolGenerationKafkaProducer,
			toolPlanGenerationService
		);
		Object payload = new Object();
		IllegalStateException exception = new IllegalStateException("kafka send failed");
		when(toolGenerationKafkaProducer.sendToolPlanRequest("run-2", payload))
			.thenReturn(CompletableFuture.failedFuture(exception));

		listener.publish(new ToolPlanKafkaPublishEvent("run-2", payload));

		verify(toolGenerationKafkaProducer).sendToolPlanRequest("run-2", payload);
		verify(toolPlanGenerationService).markRunPublishFailed("run-2", exception);
	}

	@Test
	@DisplayName("Kafka 발행 호출 중 예외가 발생해도 ToolPlanRun 실패 처리를 요청한다")
	void publishMarksRunFailedWhenKafkaSendThrows() {
		ToolPlanKafkaPublishListener listener = new ToolPlanKafkaPublishListener(
			toolGenerationKafkaProducer,
			toolPlanGenerationService
		);
		Object payload = new Object();
		IllegalStateException exception = new IllegalStateException("kafka send failed");
		doThrow(exception).when(toolGenerationKafkaProducer).sendToolPlanRequest("run-3", payload);

		listener.publish(new ToolPlanKafkaPublishEvent("run-3", payload));

		verify(toolGenerationKafkaProducer).sendToolPlanRequest("run-3", payload);
		verify(toolPlanGenerationService).markRunPublishFailed("run-3", exception);
	}
}
