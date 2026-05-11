package com.theseus.api.domain.toolgeneration.event;

import java.time.LocalDateTime;

public record ToolBuildRequestEvent(
	String eventType,
	String runId,
	Long projectId,
	Long chatSessionId,
	Long toolPlanId,
	Long planGroupId,
	Long approvedByProjectMemberId,
	ToolBuildApprovedPlanPayload approvedPlan,
	LocalDateTime requestedAt
) {
}
