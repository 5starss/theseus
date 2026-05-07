package com.theseus.api.domain.toolgeneration.dto.response;

import com.theseus.api.domain.tool.entity.Tool;
import com.theseus.api.domain.tool.entity.ToolDraftPhase;
import com.theseus.api.domain.tool.entity.ToolStatus;
import com.theseus.api.domain.toolgeneration.dto.ToolGenerationState;
import java.time.LocalDateTime;
import lombok.Builder;
import lombok.Getter;

@Getter
@Builder
public class ToolGenerationStateResponse {

	private static final String EVENT_TYPE_STATE = "state";
	private static final String STATUS_GENERATING = "GENERATING";
	private static final String STATUS_REVIEW = "REVIEW";

	private Long projectId;
	private Long chatSessionId;
	private Long toolId;
	private String eventType;
	private String status;
	private String draftPhase;
	private Integer progressRate;
	private String message;
	private String content;
	private Long draftVersion;
	private String errorCode;
	private String errorMessage;
	private LocalDateTime updatedAt;

	public static ToolGenerationStateResponse createFrom(ToolGenerationState state) {
		return ToolGenerationStateResponse.builder()
			.projectId(state.getProjectId())
			.chatSessionId(state.getChatSessionId())
			.toolId(state.getToolId())
			.eventType(state.getEventType())
			.status(state.getStatus())
			.draftPhase(state.getDraftPhase())
			.progressRate(state.getProgressRate())
			.message(state.getMessage())
			.content(state.getContent())
			.draftVersion(toLong(state.getDraftVersion()))
			.errorCode(state.getErrorCode())
			.errorMessage(state.getErrorMessage())
			.updatedAt(state.getUpdatedAt())
			.build();
	}

	public static ToolGenerationStateResponse createFallbackFrom(Tool tool) {
		return ToolGenerationStateResponse.builder()
			.projectId(tool.getProject().getId())
			.chatSessionId(tool.getChatSession().getId())
			.toolId(tool.getId())
			.eventType(EVENT_TYPE_STATE)
			.status(resolveFallbackStatus(tool))
			.draftPhase(tool.getDraftPhase().name())
			.draftVersion(tool.getDraftVersion())
			.updatedAt(tool.getUpdatedAt())
			.build();
	}

	private static String resolveFallbackStatus(Tool tool) {
		ToolStatus status = tool.getStatus();
		ToolDraftPhase draftPhase = tool.getDraftPhase();

		if (!ToolStatus.DRAFT.equals(status)) {
			return status.name();
		}
		if (ToolDraftPhase.PLAN.equals(draftPhase)) {
			return STATUS_GENERATING;
		}
		if (ToolDraftPhase.REVIEW.equals(draftPhase)) {
			return STATUS_REVIEW;
		}
		return status.name();
	}

	private static Long toLong(Integer value) {
		return value == null ? null : value.longValue();
	}
}
