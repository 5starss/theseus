package com.theseus.api.domain.toolgeneration.consumer;

import static org.assertj.core.api.Assertions.assertThatCode;
import static org.mockito.Mockito.doThrow;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.verifyNoInteractions;

import com.theseus.api.domain.toolgeneration.event.ToolBuildEvent;
import com.theseus.api.domain.toolgeneration.service.ToolBuildEventService;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;
import org.mockito.Mock;
import org.mockito.junit.jupiter.MockitoExtension;

@ExtendWith(MockitoExtension.class)
class ToolBuildEventConsumerTest {

	@Mock
	private ToolBuildEventService toolBuildEventService;

	private ToolBuildEventConsumer consumer;

	@BeforeEach
	void setUp() {
		consumer = new ToolBuildEventConsumer(toolBuildEventService);
	}

	@Test
	@DisplayName("TOOL_BUILD_COMPLETED 이벤트는 완료 처리 서비스로 위임한다")
	void consumeCompletedEvent() {
		// Given
		ToolBuildEvent event = createEvent("TOOL_BUILD_COMPLETED");

		// When
		consumer.consume(event);

		// Then
		verify(toolBuildEventService).handleCompleted(event);
	}

	@Test
	@DisplayName("TOOL_BUILD_FAILED 이벤트는 실패 처리 서비스로 위임한다")
	void consumeFailedEvent() {
		// Given
		ToolBuildEvent event = createEvent("TOOL_BUILD_FAILED");

		// When
		consumer.consume(event);

		// Then
		verify(toolBuildEventService).handleFailed(event);
	}

	@Test
	@DisplayName("progress와 chunk 이벤트는 DB 처리 없이 건너뛴다")
	void skipProgressAndChunkEvents() {
		// Given
		ToolBuildEvent progressEvent = createEvent("progress");
		ToolBuildEvent chunkEvent = createEvent("chunk");

		// When
		consumer.consume(progressEvent);
		consumer.consume(chunkEvent);

		// Then
		verifyNoInteractions(toolBuildEventService);
	}

	@Test
	@DisplayName("알 수 없는 이벤트는 서비스 호출 없이 건너뛴다")
	void skipUnknownEvent() {
		// Given
		ToolBuildEvent event = createEvent("UNKNOWN_EVENT");

		// When
		consumer.consume(event);

		// Then
		verifyNoInteractions(toolBuildEventService);
	}

	@Test
	@DisplayName("서비스 예외가 발생해도 consumer 밖으로 전파하지 않는다")
	void doesNotPropagateServiceException() {
		// Given
		ToolBuildEvent event = createEvent("TOOL_BUILD_COMPLETED");
		doThrow(new IllegalStateException("failed")).when(toolBuildEventService).handleCompleted(event);

		// When & Then
		assertThatCode(() -> consumer.consume(event))
			.doesNotThrowAnyException();
	}

	private ToolBuildEvent createEvent(String eventType) {
		return ToolBuildEvent.builder()
			.eventType(eventType)
			.runId("build-run-253")
			.eventSequence(1L)
			.projectId(1L)
			.chatSessionId(2L)
			.toolPlanId(3L)
			.build();
	}
}
