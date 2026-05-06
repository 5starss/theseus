package com.theseus.api.domain.billing.dto.response;

import com.theseus.api.domain.billing.entity.BillingUsage;
import java.time.LocalDateTime;
import lombok.Builder;
import lombok.Getter;

@Getter
@Builder
public class BillingUsageResponse {

	private Long billingUsageId;
	private Long userId;
	private Long projectId;
	private Long promptTokens;
	private Long completionTokens;
	private Long totalTokens;
	private String modelName;
	private LocalDateTime reportedAt;
	private String idempotencyKey;
	private LocalDateTime createdAt;

	public static BillingUsageResponse createFrom(BillingUsage billingUsage) {
		return BillingUsageResponse.builder()
			.billingUsageId(billingUsage.getId())
			.userId(billingUsage.getUser().getId())
			.projectId(billingUsage.getProject().getId())
			.promptTokens(billingUsage.getPromptTokens())
			.completionTokens(billingUsage.getCompletionTokens())
			.totalTokens(billingUsage.getTotalTokens())
			.modelName(billingUsage.getModelName())
			.reportedAt(billingUsage.getReportedAt())
			.idempotencyKey(billingUsage.getIdempotencyKey())
			.createdAt(billingUsage.getCreatedAt())
			.build();
	}
}
