package com.theseus.api.common.config.kafka;

import static org.assertj.core.api.Assertions.assertThat;

import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.theseus.api.domain.tool.entity.ToolPlanMode;
import com.theseus.api.domain.toolgeneration.event.ToolPlanGenerationRequestEvent;
import java.nio.charset.StandardCharsets;
import java.time.LocalDateTime;
import java.util.List;
import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;
import org.springframework.kafka.support.serializer.JsonSerializer;

class KafkaProducerConfigTest {

	@Test
	@DisplayName("Kafka request payload serializes LocalDateTime as ISO string")
	void serializeLocalDateTimeAsIsoString() throws Exception {
		// Given
		ObjectMapper objectMapper = new KafkaProducerConfig().createKafkaObjectMapper(new ObjectMapper());
		LocalDateTime requestedAt = LocalDateTime.of(2026, 5, 8, 13, 56, 52, 637765500);
		ToolPlanGenerationRequestEvent event = new ToolPlanGenerationRequestEvent(
			"TOOL_PLAN_REQUESTED",
			ToolPlanMode.PLAN,
			"run-1",
			1L,
			10L,
			3L,
			4L,
			null,
			null,
			"Create an incident recovery guide ToolPlan.",
			List.of(),
			requestedAt
		);
		JsonSerializer<Object> serializer = new JsonSerializer<>(objectMapper);

		// When
		String json = new String(serializer.serialize("theseus.tool-plan.request", event), StandardCharsets.UTF_8);
		JsonNode requestedAtNode = objectMapper.readTree(json).get("requestedAt");

		// Then
		assertThat(requestedAtNode.isTextual()).isTrue();
		assertThat(LocalDateTime.parse(requestedAtNode.asText())).isEqualTo(requestedAt);
		assertThat(json).doesNotContain("\"requestedAt\":[");
	}
}
