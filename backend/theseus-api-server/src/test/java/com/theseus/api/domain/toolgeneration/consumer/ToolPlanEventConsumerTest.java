package com.theseus.api.domain.toolgeneration.consumer;

import static org.assertj.core.api.Assertions.assertThatCode;
import static org.mockito.Mockito.doThrow;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.verifyNoInteractions;

import com.theseus.api.domain.toolgeneration.event.ToolPlanEvent;
import com.theseus.api.domain.toolgeneration.service.ToolPlanEventService;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;
import org.mockito.Mock;
import org.mockito.junit.jupiter.MockitoExtension;

@ExtendWith(MockitoExtension.class)
class ToolPlanEventConsumerTest {

	@Mock
	private ToolPlanEventService toolPlanEventService;

	private ToolPlanEventConsumer consumer;

	@BeforeEach
	void setUp() {
		consumer = new ToolPlanEventConsumer(toolPlanEventService);
	}

	@Test
	@DisplayName("TOOL_PLAN_COMPLETED 이벤트는 완료 처리 서비스로 위임한다")
	void consumeCompletedEvent() {
		// Given
		ToolPlanEvent event = createEvent("TOOL_PLAN_COMPLETED");

		// When
		consumer.consume(event);

		// Then
		verify(toolPlanEventService).handleCompleted(event);
	}

	@Test
	@DisplayName("TOOL_PLAN_SKIPPED 이벤트는 skipped 처리 서비스로 위임한다")
	void consumeSkippedEvent() {
		// Given
		ToolPlanEvent event = createEvent("TOOL_PLAN_SKIPPED");

		// When
		consumer.consume(event);

		// Then
		verify(toolPlanEventService).handleSkipped(event);
	}

	@Test
	@DisplayName("TOOL_PLAN_FAILED 이벤트는 실패 처리 서비스로 위임한다")
	void consumeFailedEvent() {
		// Given
		ToolPlanEvent event = createEvent("TOOL_PLAN_FAILED");

		// When
		consumer.consume(event);

		// Then
		verify(toolPlanEventService).handleFailed(event);
	}

	@Test
	@DisplayName("progress와 chunk 이벤트는 DB 처리 없이 건너뛴다")
	void consumeProgressAndChunkEvents() {
		// Given
		ToolPlanEvent progressEvent = createEvent("progress");
		ToolPlanEvent chunkEvent = createEvent("chunk");

		// When
		consumer.consume(progressEvent);
		consumer.consume(chunkEvent);

		// Then
		verify(toolPlanEventService).handleProgress(progressEvent);
		verify(toolPlanEventService).handleChunk(chunkEvent);
	}

	@Test
	@DisplayName("알 수 없는 이벤트는 서비스 호출 없이 건너뛴다")
	void skipUnknownEvent() {
		// Given
		ToolPlanEvent event = createEvent("UNKNOWN_EVENT");

		// When
		consumer.consume(event);

		// Then
		verifyNoInteractions(toolPlanEventService);
	}

	@Test
	@DisplayName("서비스 예외가 발생해도 consumer 밖으로 전파하지 않는다")
	void doesNotPropagateServiceException() {
		// Given
		ToolPlanEvent event = createEvent("TOOL_PLAN_COMPLETED");
		doThrow(new IllegalStateException("failed")).when(toolPlanEventService).handleCompleted(event);

		// When & Then
		assertThatCode(() -> consumer.consume(event))
			.doesNotThrowAnyException();
	}

	private ToolPlanEvent createEvent(String eventType) {
		return ToolPlanEvent.builder()
			.eventType(eventType)
			.runId("run-250")
			.eventSequence(1L)
			.projectId(1L)
			.chatSessionId(2L)
			.build();
	}
}
