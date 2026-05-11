package com.theseus.api.domain.tool.dto.response;

import com.theseus.api.domain.project.entity.ProjectMember;
import com.theseus.api.domain.tool.entity.Tool;
import com.theseus.api.domain.tool.entity.ToolApproval;
import com.theseus.api.domain.tool.entity.ToolApprovalStatus;
import com.theseus.api.domain.tool.entity.ToolDraftPhase;
import com.theseus.api.domain.tool.entity.ToolPlan;
import com.theseus.api.domain.tool.entity.ToolPlanStatus;
import com.theseus.api.domain.tool.entity.ToolStatus;
import java.time.LocalDateTime;
import lombok.Builder;
import lombok.Getter;

@Getter
@Builder
public class ToolApprovalResponse {

	private Long toolApprovalId;
	private Long projectId;
	private Long toolId;
	private Long toolPlanId;
	private Long planGroupId;
	private Long planVersion;
	private String fileName;
	private String displayName;
	private Integer requestNumber;
	private ToolApprovalStatus approvalStatus;
	private Long requestedByProjectMemberId;
	private Long requestedByUserId;
	private String requestedByUserName;
	private Long reviewedByProjectMemberId;
	private Long reviewedByUserId;
	private String reviewedByUserName;
	private String reviewFeedback;
	private LocalDateTime requestedAt;
	private LocalDateTime reviewedAt;
	private ToolStatus toolStatus;
	private ToolDraftPhase draftPhase;
	private ToolPlanStatus toolPlanStatus;

	public static ToolApprovalResponse createFrom(ToolApproval toolApproval) {
		Tool tool = toolApproval.getTool();
		ToolPlan toolPlan = toolApproval.getToolPlan();
		ProjectMember requestedByProjectMember = toolApproval.getRequestedByProjectMember();
		ProjectMember reviewedByProjectMember = toolApproval.getReviewedByProjectMember();

		return ToolApprovalResponse.builder()
			.toolApprovalId(toolApproval.getId())
			.projectId(resolveProjectId(tool, toolPlan))
			.toolId(tool == null ? null : tool.getId())
			.toolPlanId(toolPlan == null ? null : toolPlan.getId())
			.planGroupId(toolPlan == null ? null : toolPlan.getPlanGroup().getId())
			.planVersion(toolPlan == null ? null : toolPlan.getPlanVersion())
			.fileName(tool == null ? null : tool.getFileName())
			.displayName(tool == null ? null : tool.getDisplayName())
			.requestNumber(toolApproval.getRequestNumber())
			.approvalStatus(toolApproval.getApprovalStatus())
			.requestedByProjectMemberId(requestedByProjectMember.getId())
			.requestedByUserId(requestedByProjectMember.getUser().getId())
			.requestedByUserName(requestedByProjectMember.getUser().getName())
			.reviewedByProjectMemberId(
				reviewedByProjectMember == null
					? null
					: reviewedByProjectMember.getId()
			)
			.reviewedByUserId(
				reviewedByProjectMember == null
					? null
					: reviewedByProjectMember.getUser().getId()
			)
			.reviewedByUserName(
				reviewedByProjectMember == null
					? null
					: reviewedByProjectMember.getUser().getName()
			)
			.reviewFeedback(toolApproval.getReviewFeedback())
			.requestedAt(toolApproval.getRequestedAt())
			.reviewedAt(toolApproval.getReviewedAt())
			.toolStatus(tool == null ? null : tool.getStatus())
			.draftPhase(tool == null ? null : tool.getDraftPhase())
			.toolPlanStatus(toolPlan == null ? null : toolPlan.getStatus())
			.build();
	}

	private static Long resolveProjectId(Tool tool, ToolPlan toolPlan) {
		if (tool != null) {
			return tool.getProject().getId();
		}
		return toolPlan.getProject().getId();
	}
}
