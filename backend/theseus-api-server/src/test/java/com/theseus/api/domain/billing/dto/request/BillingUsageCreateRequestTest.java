package com.theseus.api.domain.billing.dto.request;

import static org.assertj.core.api.Assertions.assertThat;

import com.fasterxml.jackson.databind.ObjectMapper;
import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;

class BillingUsageCreateRequestTest {

	@Test
	@DisplayName("Core BillingUsageReport snake_case JSON을 요청 DTO로 역직렬화한다.")
	void deserializeCoreBillingUsageReport() throws Exception {
		// Given
		String payload = """
			{
			  "user_id": 3,
			  "project_id": 7,
			  "usage": {
			    "prompt_tokens": 120,
			    "completion_tokens": 30,
			    "total_tokens": 150,
			    "model_name": "gpt-test"
			  },
			  "timestamp": "2026-05-06T10:20:30"
			}
			""";

		// When
		BillingUsageCreateRequest request = new ObjectMapper().readValue(payload, BillingUsageCreateRequest.class);

		// Then
		assertThat(request.getUserId()).isEqualTo(3L);
		assertThat(request.getProjectId()).isEqualTo(7L);
		assertThat(request.getUsage().getPromptTokens()).isEqualTo(120L);
		assertThat(request.getUsage().getCompletionTokens()).isEqualTo(30L);
		assertThat(request.getUsage().getTotalTokens()).isEqualTo(150L);
		assertThat(request.getUsage().getModelName()).isEqualTo("gpt-test");
		assertThat(request.getTimestamp()).isEqualTo("2026-05-06T10:20:30");
	}
}
