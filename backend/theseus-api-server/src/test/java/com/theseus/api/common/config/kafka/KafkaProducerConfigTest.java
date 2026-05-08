package com.theseus.api.common.config.kafka;

import static org.assertj.core.api.Assertions.assertThat;

import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.theseus.api.domain.project.entity.ProjectRole;
import com.theseus.api.domain.toolgeneration.event.ToolGenerationRequestEvent;
import com.theseus.api.domain.toolgeneration.event.ToolPermissionPayload;
import java.nio.charset.StandardCharsets;
import java.time.LocalDateTime;
import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;
import org.springframework.kafka.support.serializer.JsonSerializer;

class KafkaProducerConfigTest {

	@Test
	@DisplayName("Kafka 요청 payload의 LocalDateTime은 ISO 문자열로 직렬화된다")
	void serializeLocalDateTimeAsIsoString() throws Exception {
		// Given
		ObjectMapper objectMapper = new KafkaProducerConfig().createKafkaObjectMapper(new ObjectMapper());
		LocalDateTime requestedAt = LocalDateTime.of(2026, 5, 8, 13, 56, 52, 637765500);
		ToolGenerationRequestEvent event = new ToolGenerationRequestEvent(
			"TOOL_GENERATION_REQUESTED",
			"run-1",
			1L,
			10L,
			7L,
			3L,
			4L,
			"최근 24시간 장애 로그를 분석하고 자동 복구 가이드를 만드는 Tool을 만들어줘.",
			"incident_recovery_guide",
			ProjectRole.ADMIN,
			new ToolPermissionPayload(true, true, true, false),
			requestedAt
		);
		JsonSerializer<Object> serializer = new JsonSerializer<>(objectMapper);

		// When
		String json = new String(serializer.serialize("theseus.tool-generation.request", event), StandardCharsets.UTF_8);
		JsonNode requestedAtNode = objectMapper.readTree(json).get("requestedAt");

		// Then
		assertThat(requestedAtNode.isTextual()).isTrue();
		assertThat(LocalDateTime.parse(requestedAtNode.asText())).isEqualTo(requestedAt);
		assertThat(json).doesNotContain("\"requestedAt\":[");
	}
}
