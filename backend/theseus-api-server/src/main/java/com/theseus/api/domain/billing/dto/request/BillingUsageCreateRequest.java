package com.theseus.api.domain.billing.dto.request;

import com.fasterxml.jackson.annotation.JsonProperty;
import jakarta.validation.Valid;
import jakarta.validation.constraints.NotNull;
import lombok.Getter;

@Getter
public class BillingUsageCreateRequest {

	@NotNull
	@JsonProperty("user_id")
	private Long userId;

	@NotNull
	@JsonProperty("project_id")
	private Long projectId;

	@Valid
	@NotNull
	private BillingUsageMetricsRequest usage;

	private String timestamp;
}
