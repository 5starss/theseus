package com.theseus.api.domain.chat.dto.response;

import com.theseus.api.domain.chat.entity.ChatMessage;
import com.theseus.api.domain.chat.entity.ChatSession;
import com.theseus.api.domain.tool.entity.Tool;
import com.theseus.api.domain.tool.entity.ToolPlan;
import com.theseus.api.domain.tool.entity.ToolPlanGroup;
import com.theseus.api.domain.tool.entity.ToolPlanRun;
import java.time.LocalDateTime;
import java.util.List;
import lombok.Builder;
import lombok.Getter;

@Getter
@Builder
public class ChatSessionDetailResponse {

	private Long sessionId;
	private Long projectId;
	private Long projectMemberId;
	private String title;
	private Boolean isClosed;
	private LocalDateTime closedAt;
	private LocalDateTime createdAt;
	private LocalDateTime updatedAt;
	private List<ChatMessageResponse> messages;
	private CurrentPlanResponse currentPlan;
	private CreatedToolResponse createdTool;

	public static ChatSessionDetailResponse createOf(ChatSession chatSession, List<ChatMessage> messages) {
		return createOf(chatSession, messages, null, null);
	}

	public static ChatSessionDetailResponse createOf(
		ChatSession chatSession,
		List<ChatMessage> messages,
		CurrentPlanResponse currentPlan,
		CreatedToolResponse createdTool
	) {
		return ChatSessionDetailResponse.builder()
			.sessionId(chatSession.getId())
			.projectId(chatSession.getProject().getId())
			.projectMemberId(chatSession.getProjectMember().getId())
			.title(chatSession.getTitle())
			.isClosed(chatSession.isClosed())
			.closedAt(chatSession.getClosedAt())
			.createdAt(chatSession.getCreatedAt())
			.updatedAt(chatSession.getUpdatedAt())
			.messages(messages.stream()
				.map(ChatMessageResponse::createFrom)
				.toList())
			.currentPlan(currentPlan)
			.createdTool(createdTool)
			.build();
	}

	@Getter
	@Builder
	public static class CurrentPlanResponse {

		private String runId;
		private Long toolPlanGroupId;
		private Long toolPlanId;
		private Long planVersion;
		private String status;

		public static CurrentPlanResponse createFrom(ToolPlanRun toolPlanRun) {
			ToolPlan toolPlan = resolveToolPlan(toolPlanRun);
			ToolPlanGroup planGroup = resolvePlanGroup(toolPlanRun, toolPlan);

			return CurrentPlanResponse.builder()
				.runId(toolPlanRun.getRunId())
				.toolPlanGroupId(planGroup == null ? null : planGroup.getId())
				.toolPlanId(toolPlan == null ? null : toolPlan.getId())
				.planVersion(toolPlan == null ? null : toolPlan.getPlanVersion())
				.status(toolPlanRun.getStatus().name())
				.build();
		}

		public static CurrentPlanResponse createFrom(ToolPlan toolPlan) {
			return CurrentPlanResponse.builder()
				.toolPlanGroupId(toolPlan.getPlanGroup().getId())
				.toolPlanId(toolPlan.getId())
				.planVersion(toolPlan.getPlanVersion())
				.status(toolPlan.getStatus().name())
				.build();
		}

		private static ToolPlan resolveToolPlan(ToolPlanRun toolPlanRun) {
			if (toolPlanRun.getResultToolPlan() != null) {
				return toolPlanRun.getResultToolPlan();
			}
			return toolPlanRun.getBaseToolPlan();
		}

		private static ToolPlanGroup resolvePlanGroup(ToolPlanRun toolPlanRun, ToolPlan toolPlan) {
			if (toolPlanRun.getPlanGroup() != null) {
				return toolPlanRun.getPlanGroup();
			}
			if (toolPlan != null) {
				return toolPlan.getPlanGroup();
			}
			return null;
		}
	}

	@Getter
	@Builder
	public static class CreatedToolResponse {

		private Long toolId;
		private Long sourceToolPlanId;
		private String status;

		public static CreatedToolResponse createFrom(Tool tool) {
			return CreatedToolResponse.builder()
				.toolId(tool.getId())
				.sourceToolPlanId(tool.getSourceToolPlan() == null ? null : tool.getSourceToolPlan().getId())
				.status(tool.getStatus().name())
				.build();
		}
	}
}
