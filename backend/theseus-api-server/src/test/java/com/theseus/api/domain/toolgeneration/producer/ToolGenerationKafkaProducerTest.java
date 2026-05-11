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

	private static final String TOOL_PLAN_REQUEST_TOPIC = "theseus.tool-plan.request";
	private static final String TOOL_PLAN_EVENT_TOPIC = "theseus.tool-plan.event";
	private static final String TOOL_BUILD_REQUEST_TOPIC = "theseus.tool-build.request";
	private static final String TOOL_BUILD_EVENT_TOPIC = "theseus.tool-build.event";

	@Mock
	private KafkaTemplate<String, Object> kafkaTemplate;

	private ToolGenerationKafkaProducer producer;

	@BeforeEach
	void setUp() {
		KafkaTopicProperties kafkaTopicProperties = new KafkaTopicProperties(
			TOOL_PLAN_REQUEST_TOPIC,
			TOOL_PLAN_EVENT_TOPIC,
			TOOL_BUILD_REQUEST_TOPIC,
			TOOL_BUILD_EVENT_TOPIC
		);
		producer = new ToolGenerationKafkaProducer(kafkaTemplate, kafkaTopicProperties);
	}

	@Test
	@DisplayName("ToolPlan request is sent to tool-plan request topic")
	void sendToolPlanRequestSendsToToolPlanRequestTopic() {
		String key = "plan-run-1";
		TestKafkaEvent event = new TestKafkaEvent("plan");
		when(kafkaTemplate.send(TOOL_PLAN_REQUEST_TOPIC, key, event))
			.thenReturn(CompletableFuture.completedFuture(null));

		producer.sendToolPlanRequest(key, event);

		verify(kafkaTemplate).send(TOOL_PLAN_REQUEST_TOPIC, key, event);
	}

	@Test
	@DisplayName("Tool build request is sent to build request topic")
	void sendToolBuildRequestSendsToBuildRequestTopic() {
		String key = "build-run-1";
		TestKafkaEvent event = new TestKafkaEvent("build");
		when(kafkaTemplate.send(TOOL_BUILD_REQUEST_TOPIC, key, event))
			.thenReturn(CompletableFuture.completedFuture(null));

		producer.sendToolBuildRequest(key, event);

		verify(kafkaTemplate).send(TOOL_BUILD_REQUEST_TOPIC, key, event);
	}

	@Test
	@DisplayName("Kafka send failure is not propagated to caller")
	void sendDoesNotThrowWhenKafkaSendCompletesExceptionally() {
		String key = "request-3";
		TestKafkaEvent event = new TestKafkaEvent("failed");
		when(kafkaTemplate.send(TOOL_PLAN_REQUEST_TOPIC, key, event))
			.thenReturn(CompletableFuture.failedFuture(new IllegalStateException("kafka send failed")));

		assertThatCode(() -> producer.sendToolPlanRequest(key, event))
			.doesNotThrowAnyException();
	}

	private record TestKafkaEvent(String type) {
	}
}
