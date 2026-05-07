package com.theseus.api.domain.toolgeneration.dto;

import java.time.LocalDateTime;
import lombok.Builder;
import lombok.Getter;

@Getter
@Builder
public class ToolGenerationSseEvent {

	private static final String EVENT_TYPE_CONNECTED = "connected";

	private String eventType;
	private Long projectId;
	private Long chatSessionId;
	private Long toolId;
	private String status;
	private String draftPhase;
	private Integer progressRate;
	private String message;
	private String content;
	private Integer draftVersion;
	private String errorCode;
	private String errorMessage;
	private LocalDateTime updatedAt;

	public static ToolGenerationSseEvent connectedOf(Long projectId, Long chatSessionId, Long toolId) {
		return ToolGenerationSseEvent.builder()
			.eventType(EVENT_TYPE_CONNECTED)
			.projectId(projectId)
			.chatSessionId(chatSessionId)
			.toolId(toolId)
			.message("connected")
			.updatedAt(LocalDateTime.now())
			.build();
	}

	public static ToolGenerationSseEvent createFrom(ToolGenerationState state) {
		return ToolGenerationSseEvent.builder()
			.eventType(state.getEventType())
			.projectId(state.getProjectId())
			.chatSessionId(state.getChatSessionId())
			.toolId(state.getToolId())
			.status(state.getStatus())
			.draftPhase(state.getDraftPhase())
			.progressRate(state.getProgressRate())
			.message(state.getMessage())
			.content(state.getContent())
			.draftVersion(state.getDraftVersion())
			.errorCode(state.getErrorCode())
			.errorMessage(state.getErrorMessage())
			.updatedAt(state.getUpdatedAt())
			.build();
	}
}
