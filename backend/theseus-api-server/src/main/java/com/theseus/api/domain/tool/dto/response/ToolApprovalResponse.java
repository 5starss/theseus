package com.theseus.api.domain.tool.dto.response;

import com.theseus.api.domain.project.entity.ProjectMember;
import com.theseus.api.domain.tool.entity.Tool;
import com.theseus.api.domain.tool.entity.ToolApproval;
import com.theseus.api.domain.tool.entity.ToolApprovalStatus;
import com.theseus.api.domain.tool.entity.ToolDraftPhase;
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

	public static ToolApprovalResponse createFrom(ToolApproval toolApproval) {
		Tool tool = toolApproval.getTool();
		ProjectMember requestedByProjectMember = toolApproval.getRequestedByProjectMember();
		ProjectMember reviewedByProjectMember = toolApproval.getReviewedByProjectMember();

		return ToolApprovalResponse.builder()
			.toolApprovalId(toolApproval.getId())
			.projectId(tool.getProject().getId())
			.toolId(tool.getId())
			.fileName(tool.getFileName())
			.displayName(tool.getDisplayName())
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
			.toolStatus(tool.getStatus())
			.draftPhase(tool.getDraftPhase())
			.build();
	}
}
