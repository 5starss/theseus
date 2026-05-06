package com.theseus.api.domain.toolgeneration.consumer;

import static org.assertj.core.api.Assertions.assertThatCode;
import static org.mockito.Mockito.doThrow;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.verifyNoInteractions;

import com.theseus.api.domain.toolgeneration.event.ToolGenerationEvent;
import com.theseus.api.domain.toolgeneration.service.ToolGenerationEventService;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;
import org.mockito.Mock;
import org.mockito.junit.jupiter.MockitoExtension;

@ExtendWith(MockitoExtension.class)
class ToolGenerationEventConsumerTest {

	@Mock
	private ToolGenerationEventService toolGenerationEventService;

	private ToolGenerationEventConsumer consumer;

	@BeforeEach
	void setUp() {
		consumer = new ToolGenerationEventConsumer(toolGenerationEventService);
	}

	@Test
	@DisplayName("completed 이벤트를 받으면 완료 처리 서비스로 위임한다.")
	void consumeCompletedEvent() {
		// Given
		ToolGenerationEvent event = createEvent("TOOL_GENERATION_COMPLETED");

		// When
		consumer.consume(event);

		// Then
		verify(toolGenerationEventService).handleCompleted(event);
	}

	@Test
	@DisplayName("failed 이벤트를 받으면 실패 처리 서비스로 위임한다.")
	void consumeFailedEvent() {
		// Given
		ToolGenerationEvent event = createEvent("TOOL_GENERATION_FAILED");

		// When
		consumer.consume(event);

		// Then
		verify(toolGenerationEventService).handleFailed(event);
	}

	@Test
	@DisplayName("progress와 chunk 이벤트는 DB 저장 없이 로그 처리로 건너뛴다.")
	void skipProgressAndChunkEvents() {
		// Given
		ToolGenerationEvent progressEvent = createEvent("progress");
		ToolGenerationEvent chunkEvent = createEvent("chunk");

		// When
		consumer.consume(progressEvent);
		consumer.consume(chunkEvent);

		// Then
		verifyNoInteractions(toolGenerationEventService);
	}

	@Test
	@DisplayName("지원하지 않는 이벤트 타입은 처리 서비스 호출 없이 건너뛴다.")
	void skipUnsupportedEvent() {
		// Given
		ToolGenerationEvent event = createEvent("UNSUPPORTED_EVENT");

		// When
		consumer.consume(event);

		// Then
		verifyNoInteractions(toolGenerationEventService);
	}

	@Test
	@DisplayName("서비스 처리 중 예외가 발생해도 consumer 밖으로 전파하지 않는다.")
	void doesNotPropagateServiceException() {
		// Given
		ToolGenerationEvent event = createEvent("TOOL_GENERATION_COMPLETED");
		doThrow(new IllegalStateException("failed")).when(toolGenerationEventService).handleCompleted(event);

		// When & Then
		assertThatCode(() -> consumer.consume(event))
			.doesNotThrowAnyException();
	}

	private ToolGenerationEvent createEvent(String eventType) {
		return ToolGenerationEvent.builder()
			.eventType(eventType)
			.runId("run-1")
			.projectId(1L)
			.chatSessionId(2L)
			.toolId(3L)
			.build();
	}
}
