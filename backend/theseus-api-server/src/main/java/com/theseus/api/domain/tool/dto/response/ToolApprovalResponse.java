package com.theseus.api.domain.tool.dto.response;

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
	private Integer requestNumber;
	private ToolApprovalStatus approvalStatus;
	private Long requestedByProjectMemberId;
	private Long reviewedByProjectMemberId;
	private String reviewFeedback;
	private LocalDateTime requestedAt;
	private LocalDateTime reviewedAt;
	private ToolStatus toolStatus;
	private ToolDraftPhase draftPhase;

	public static ToolApprovalResponse createFrom(ToolApproval toolApproval) {
		Tool tool = toolApproval.getTool();

		return ToolApprovalResponse.builder()
			.toolApprovalId(toolApproval.getId())
			.projectId(tool.getProject().getId())
			.toolId(tool.getId())
			.requestNumber(toolApproval.getRequestNumber())
			.approvalStatus(toolApproval.getApprovalStatus())
			.requestedByProjectMemberId(toolApproval.getRequestedByProjectMember().getId())
			.reviewedByProjectMemberId(
				toolApproval.getReviewedByProjectMember() == null
					? null
					: toolApproval.getReviewedByProjectMember().getId()
			)
			.reviewFeedback(toolApproval.getReviewFeedback())
			.requestedAt(toolApproval.getRequestedAt())
			.reviewedAt(toolApproval.getReviewedAt())
			.toolStatus(tool.getStatus())
			.draftPhase(tool.getDraftPhase())
			.build();
	}
}
