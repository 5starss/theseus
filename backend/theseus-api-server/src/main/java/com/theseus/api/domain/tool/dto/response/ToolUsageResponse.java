package com.theseus.api.domain.tool.dto.response;

import com.theseus.api.domain.project.entity.ProjectMember;
import com.theseus.api.domain.tool.entity.Tool;
import com.theseus.api.domain.tool.entity.ToolUsageLog;
import java.time.LocalDateTime;
import lombok.Builder;
import lombok.Getter;

@Getter
@Builder
public class ToolUsageResponse {

	private Long id;
	private Long toolId;
	private String toolName;
	private Integer level;
	private Long toolCreatorId;
	private String toolCreatorName;
	private String toolCreatorEmployeeNo;
	private Long usedById;
	private String usedByName;
	private String usedByEmployeeNo;
	private String status;
	private LocalDateTime createdAt;
	private LocalDateTime usedAt;
	private String errorMessage;

	public static ToolUsageResponse createFrom(ToolUsageLog usageLog) {
		Tool tool = usageLog.getTool();
		ProjectMember toolCreator = tool.getCreatedByProjectMember();
		ProjectMember usedBy = usageLog.getUsedByProjectMember();

		return ToolUsageResponse.builder()
			.id(usageLog.getId())
			.toolId(tool.getId())
			.toolName(tool.getDisplayName() == null || tool.getDisplayName().isBlank() ? tool.getFileName() : tool.getDisplayName())
			.level(tool.getToolGrade())
			.toolCreatorId(toolCreator.getUser().getId())
			.toolCreatorName(toolCreator.getUser().getName())
			.toolCreatorEmployeeNo(toolCreator.getUser().getEmployeeNumber())
			.usedById(usedBy.getUser().getId())
			.usedByName(usedBy.getUser().getName())
			.usedByEmployeeNo(usedBy.getUser().getEmployeeNumber())
			.status(usageLog.getStatus().name())
			.createdAt(tool.getCreatedAt())
			.usedAt(usageLog.getUsedAt())
			.errorMessage(usageLog.getErrorMessage())
			.build();
	}
}
