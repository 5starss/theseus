package com.theseus.api.domain.billing.dto.request;

import com.fasterxml.jackson.annotation.JsonProperty;
import lombok.Getter;

@Getter
public class BillingUsageMetricsRequest {

	@JsonProperty("prompt_tokens")
	private Long promptTokens;

	@JsonProperty("completion_tokens")
	private Long completionTokens;

	@JsonProperty("total_tokens")
	private Long totalTokens;

	@JsonProperty("model_name")
	private String modelName;
}
