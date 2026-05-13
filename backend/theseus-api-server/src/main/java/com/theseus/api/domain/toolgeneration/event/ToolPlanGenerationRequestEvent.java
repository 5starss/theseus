package com.theseus.api.domain.toolgeneration.event;

import com.theseus.api.domain.tool.entity.ToolPlanMode;
import java.time.LocalDateTime;
import java.util.List;

public record ToolPlanGenerationRequestEvent(
	String eventType,
	ToolPlanMode mode,
	String runId,
	Long projectId,
	Long chatSessionId,
	Long requestedByUserId,
	Long requestedByProjectMemberId,
	Long remoteWorkspaceId,
	ToolPlanRemoteWorkspacePayload remoteWorkspace,
	String prompt,
	List<ToolPlanHistoryMessagePayload> history,
	LocalDateTime requestedAt
) {
}
