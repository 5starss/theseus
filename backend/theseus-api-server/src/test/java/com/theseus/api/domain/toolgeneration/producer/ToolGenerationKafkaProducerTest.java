package com.theseus.api.domain.toolgeneration.producer;

import static org.assertj.core.api.Assertions.assertThatCode;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.when;

import com.theseus.api.common.kafka.KafkaTopicProperties;
import java.util.concurrent.CompletableFuture;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;
import org.mockito.Mock;
import org.mockito.junit.jupiter.MockitoExtension;
import org.springframework.kafka.core.KafkaTemplate;

@ExtendWith(MockitoExtension.class)
class ToolGenerationKafkaProducerTest {

	private static final String TOOL_GENERATION_REQUEST_TOPIC = "theseus.tool-generation.request";
	private static final String TOOL_REGENERATION_REQUEST_TOPIC = "theseus.tool-regeneration.request";
	private static final String TOOL_GENERATION_EVENT_TOPIC = "theseus.tool-generation.event";

	@Mock
	private KafkaTemplate<String, Object> kafkaTemplate;

	private ToolGenerationKafkaProducer producer;

	@BeforeEach
	void setUp() {
		KafkaTopicProperties kafkaTopicProperties = new KafkaTopicProperties(
			TOOL_GENERATION_REQUEST_TOPIC,
			TOOL_REGENERATION_REQUEST_TOPIC,
			TOOL_GENERATION_EVENT_TOPIC
		);
		producer = new ToolGenerationKafkaProducer(kafkaTemplate, kafkaTopicProperties);
	}

	@Test
	@DisplayName("Tool 생성 요청은 generation request topic으로 발행된다")
	void sendToolGenerationRequestSendsToGenerationRequestTopic() {
		String key = "request-1";
		TestKafkaEvent event = new TestKafkaEvent("generate");
		when(kafkaTemplate.send(TOOL_GENERATION_REQUEST_TOPIC, key, event))
			.thenReturn(CompletableFuture.completedFuture(null));

		producer.sendToolGenerationRequest(key, event);

		verify(kafkaTemplate).send(TOOL_GENERATION_REQUEST_TOPIC, key, event);
	}

	@Test
	@DisplayName("Tool 재생성 요청은 regeneration request topic으로 발행된다")
	void sendToolRegenerationRequestSendsToRegenerationRequestTopic() {
		String key = "request-2";
		TestKafkaEvent event = new TestKafkaEvent("regenerate");
		when(kafkaTemplate.send(TOOL_REGENERATION_REQUEST_TOPIC, key, event))
			.thenReturn(CompletableFuture.completedFuture(null));

		producer.sendToolRegenerationRequest(key, event);

		verify(kafkaTemplate).send(TOOL_REGENERATION_REQUEST_TOPIC, key, event);
	}

	@Test
	@DisplayName("Kafka 발행 실패는 호출부로 예외를 전파하지 않는다")
	void sendDoesNotThrowWhenKafkaSendCompletesExceptionally() {
		String key = "request-3";
		TestKafkaEvent event = new TestKafkaEvent("failed");
		when(kafkaTemplate.send(TOOL_GENERATION_REQUEST_TOPIC, key, event))
			.thenReturn(CompletableFuture.failedFuture(new IllegalStateException("kafka send failed")));

		assertThatCode(() -> producer.sendToolGenerationRequest(key, event))
			.doesNotThrowAnyException();
	}

	private record TestKafkaEvent(String type) {
	}
}
