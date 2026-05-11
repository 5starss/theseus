package com.theseus.api.domain.toolgeneration.dto;

import java.time.LocalDateTime;
import lombok.Builder;
import lombok.Getter;

@Getter
@Builder
public class ToolPlanRunSseEvent {

	private static final String EVENT_TYPE_CONNECTED = "connected";

	private String eventType;
	private String runId;
	private Long projectId;
	private Long chatSessionId;
	private Long toolPlanGroupId;
	private Long toolPlanId;
	private Long planVersion;
	private String status;
	private Integer progressRate;
	private String message;
	private String content;
	private String errorCode;
	private String errorMessage;
	private LocalDateTime updatedAt;

	public static ToolPlanRunSseEvent connectedOf(Long projectId, Long chatSessionId, String runId) {
		return ToolPlanRunSseEvent.builder()
			.eventType(EVENT_TYPE_CONNECTED)
			.runId(runId)
			.projectId(projectId)
			.chatSessionId(chatSessionId)
			.message("connected")
			.updatedAt(LocalDateTime.now())
			.build();
	}

	public static ToolPlanRunSseEvent createFrom(ToolPlanRunState state) {
		return ToolPlanRunSseEvent.builder()
			.eventType(state.getEventType())
			.runId(state.getRunId())
			.projectId(state.getProjectId())
			.chatSessionId(state.getChatSessionId())
			.toolPlanGroupId(state.getToolPlanGroupId())
			.toolPlanId(state.getToolPlanId())
			.planVersion(state.getPlanVersion())
			.status(state.getStatus())
			.progressRate(state.getProgressRate())
			.message(state.getMessage())
			.content(state.getContent())
			.errorCode(state.getErrorCode())
			.errorMessage(state.getErrorMessage())
			.updatedAt(state.getUpdatedAt())
			.build();
	}
}
