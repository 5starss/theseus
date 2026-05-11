package com.theseus.api.domain.toolgeneration.sse;

import static org.assertj.core.api.Assertions.assertThat;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.Mockito.doThrow;
import static org.mockito.Mockito.verify;

import com.theseus.api.domain.toolgeneration.dto.ToolPlanRunSseEvent;
import java.io.IOException;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;
import org.mockito.Mockito;
import org.springframework.web.servlet.mvc.method.annotation.SseEmitter;

class ToolPlanRunSseEmitterRegistryTest {

	private static final Long PROJECT_ID = 1L;
	private static final Long CHAT_SESSION_ID = 2L;
	private static final String RUN_ID = "run-254";

	private ToolPlanRunSseEmitterRegistry registry;

	@BeforeEach
	void setUp() {
		registry = new ToolPlanRunSseEmitterRegistry();
	}

	@Test
	@DisplayName("Emitter를 등록하고 같은 runId stream key로 이벤트를 전송한다.")
	void registerAndSendToRun() throws Exception {
		// Given
		SseEmitter emitter = Mockito.mock(SseEmitter.class);
		registry.register(PROJECT_ID, CHAT_SESSION_ID, RUN_ID, emitter);

		// When
		registry.sendToRun(PROJECT_ID, CHAT_SESSION_ID, RUN_ID, createEvent("progress"));

		// Then
		verify(emitter).send(any(SseEmitter.SseEventBuilder.class));
		assertThat(registry.count(PROJECT_ID, CHAT_SESSION_ID, RUN_ID)).isEqualTo(1);
	}

	@Test
	@DisplayName("Emitter를 제거하면 같은 runId stream key로 이벤트를 전송하지 않는다.")
	void removeEmitter() {
		// Given
		SseEmitter emitter = Mockito.mock(SseEmitter.class);
		registry.register(PROJECT_ID, CHAT_SESSION_ID, RUN_ID, emitter);

		// When
		registry.remove(PROJECT_ID, CHAT_SESSION_ID, RUN_ID, emitter);

		// Then
		assertThat(registry.count(PROJECT_ID, CHAT_SESSION_ID, RUN_ID)).isZero();
	}

	@Test
	@DisplayName("완료 처리하면 등록된 Emitter를 complete하고 Registry에서 제거한다.")
	void completeEmitters() {
		// Given
		SseEmitter emitter = Mockito.mock(SseEmitter.class);
		registry.register(PROJECT_ID, CHAT_SESSION_ID, RUN_ID, emitter);

		// When
		registry.complete(PROJECT_ID, CHAT_SESSION_ID, RUN_ID);

		// Then
		verify(emitter).complete();
		assertThat(registry.count(PROJECT_ID, CHAT_SESSION_ID, RUN_ID)).isZero();
	}

	@Test
	@DisplayName("SSE 전송에 실패하면 해당 Emitter를 제거한다.")
	void removeEmitterWhenSendFails() throws Exception {
		// Given
		SseEmitter emitter = Mockito.mock(SseEmitter.class);
		doThrow(new IOException("broken pipe"))
			.when(emitter)
			.send(any(SseEmitter.SseEventBuilder.class));
		registry.register(PROJECT_ID, CHAT_SESSION_ID, RUN_ID, emitter);

		// When
		boolean isSent = registry.sendToEmitter(
			PROJECT_ID,
			CHAT_SESSION_ID,
			RUN_ID,
			emitter,
			createEvent("progress")
		);

		// Then
		assertThat(isSent).isFalse();
		assertThat(registry.count(PROJECT_ID, CHAT_SESSION_ID, RUN_ID)).isZero();
	}

	private ToolPlanRunSseEvent createEvent(String eventType) {
		return ToolPlanRunSseEvent.builder()
			.eventType(eventType)
			.projectId(PROJECT_ID)
			.chatSessionId(CHAT_SESSION_ID)
			.runId(RUN_ID)
			.build();
	}
}
