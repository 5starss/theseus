package com.theseus.api.domain.toolgeneration.event;

import com.theseus.api.domain.project.entity.ProjectRole;
import java.time.LocalDateTime;

public record ToolGenerationRequestEvent(
	String eventType,
	String runId,
	Long projectId,
	Long chatSessionId,
	Long toolId,
	Long requestedByUserId,
	Long requestedByProjectMemberId,
	String prompt,
	String fileName,
	ProjectRole projectRole,
	ToolPermissionPayload toolPermission,
	LocalDateTime requestedAt
) {
}
