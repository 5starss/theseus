package com.theseus.api.domain.toolgeneration.event;

import com.theseus.api.domain.project.entity.ProjectRole;
import com.theseus.api.domain.toolgeneration.dto.request.ToolFeedbackItemRequest;
import java.time.LocalDateTime;
import java.util.List;

public record ToolRegenerationRequestEvent(
	String eventType,
	String runId,
	Long projectId,
	Long chatSessionId,
	Long toolId,
	Long requestedByUserId,
	Long requestedByProjectMemberId,
	Long baseDraftVersion,
	List<ToolFeedbackItemRequest> feedbackItems,
	ToolGenerationDraftPayload baseDraft,
	ProjectRole projectRole,
	ToolPermissionPayload toolPermission,
	LocalDateTime requestedAt
) {
}
