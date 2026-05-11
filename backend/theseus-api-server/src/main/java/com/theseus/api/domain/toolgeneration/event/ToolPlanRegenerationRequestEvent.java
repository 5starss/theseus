package com.theseus.api.domain.toolgeneration.event;

import com.theseus.api.domain.tool.entity.ToolPlanMode;
import com.theseus.api.domain.toolgeneration.dto.request.ToolFeedbackItemRequest;
import java.time.LocalDateTime;
import java.util.List;

public record ToolPlanRegenerationRequestEvent(
	String eventType,
	ToolPlanMode mode,
	String runId,
	Long projectId,
	Long chatSessionId,
	Long baseToolPlanId,
	Long planGroupId,
	Long basePlanVersion,
	ToolPlanBasePlanPayload basePlan,
	List<ToolFeedbackItemRequest> feedbackItems,
	List<ToolPlanHistoryMessagePayload> history,
	LocalDateTime requestedAt
) {
}
