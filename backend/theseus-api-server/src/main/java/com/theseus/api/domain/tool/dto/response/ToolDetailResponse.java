package com.theseus.api.domain.tool.dto.response;

import com.theseus.api.domain.tool.entity.Tool;
import com.theseus.api.domain.tool.entity.ToolDraftPhase;
import com.theseus.api.domain.tool.entity.ToolStatus;
import java.time.LocalDateTime;
import lombok.Builder;
import lombok.Getter;

@Getter
@Builder
public class ToolDetailResponse {

	private Long toolId;
	private Long projectId;
	private Long chatSessionId;
	private Long createdByProjectMemberId;
	private Long createdByUserId;
	private String createdByUserName;
	private String fileName;
	private String displayName;
	private String displayDescription;
	private ToolStatus status;
	private ToolDraftPhase draftPhase;
	private Integer toolGrade;
	private String rawMarkdown;
	private String structuredPlanJson;
	private String draftSnapshot;
	private LocalDateTime createdAt;
	private LocalDateTime updatedAt;

	public static ToolDetailResponse createFrom(Tool tool) {
		return ToolDetailResponse.builder()
			.toolId(tool.getId())
			.projectId(tool.getProject().getId())
			.chatSessionId(tool.getChatSession().getId())
			.createdByProjectMemberId(tool.getCreatedByProjectMember().getId())
			.createdByUserId(tool.getCreatedByProjectMember().getUser().getId())
			.createdByUserName(tool.getCreatedByProjectMember().getUser().getName())
			.fileName(tool.getFileName())
			.displayName(tool.getDisplayName())
			.displayDescription(tool.getDisplayDescription())
			.status(tool.getStatus())
			.draftPhase(tool.getDraftPhase())
			.toolGrade(tool.getToolGrade())
			.rawMarkdown(tool.getRawMarkdown())
			.structuredPlanJson(tool.getStructuredPlanJson())
			.draftSnapshot(tool.getDraftSnapshot())
			.createdAt(tool.getCreatedAt())
			.updatedAt(tool.getUpdatedAt())
			.build();
	}
}
