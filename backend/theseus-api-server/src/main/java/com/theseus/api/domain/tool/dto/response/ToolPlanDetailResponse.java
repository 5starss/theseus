package com.theseus.api.domain.tool.dto.response;

import com.theseus.api.domain.tool.entity.ToolPlan;
import com.theseus.api.domain.tool.entity.ToolPlanMode;
import com.theseus.api.domain.tool.entity.ToolPlanStatus;
import java.time.LocalDateTime;
import lombok.Builder;
import lombok.Getter;

@Getter
@Builder
public class ToolPlanDetailResponse {

	private Long toolPlanId;
	private Long toolPlanGroupId;
	private Long projectId;
	private Long chatSessionId;
	private Long createdByProjectMemberId;
	private Long baseToolPlanId;
	private Long planVersion;
	private ToolPlanStatus status;
	private ToolPlanMode mode;
	private String requestedPrompt;
	private String rawMarkdown;
	private String structuredPlanJson;
	private String planSnapshot;
	private LocalDateTime createdAt;
	private LocalDateTime updatedAt;

	public static ToolPlanDetailResponse createFrom(ToolPlan toolPlan) {
		return ToolPlanDetailResponse.builder()
			.toolPlanId(toolPlan.getId())
			.toolPlanGroupId(toolPlan.getPlanGroup().getId())
			.projectId(toolPlan.getProject().getId())
			.chatSessionId(toolPlan.getChatSession().getId())
			.createdByProjectMemberId(toolPlan.getCreatedByProjectMember().getId())
			.baseToolPlanId(toolPlan.getBaseToolPlan() == null ? null : toolPlan.getBaseToolPlan().getId())
			.planVersion(toolPlan.getPlanVersion())
			.status(toolPlan.getStatus())
			.mode(toolPlan.getMode())
			.requestedPrompt(toolPlan.getRequestedPrompt())
			.rawMarkdown(toolPlan.getRawMarkdown())
			.structuredPlanJson(toolPlan.getStructuredPlanJson())
			.planSnapshot(toolPlan.getPlanSnapshot())
			.createdAt(toolPlan.getCreatedAt())
			.updatedAt(toolPlan.getUpdatedAt())
			.build();
	}
}
