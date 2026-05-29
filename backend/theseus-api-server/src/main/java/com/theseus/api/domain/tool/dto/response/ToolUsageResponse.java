package com.theseus.api.domain.tool.dto.response;

import com.theseus.api.domain.project.entity.ProjectMember;
import com.theseus.api.domain.tool.entity.ToolUsageLog;
import com.theseus.api.domain.tool.entity.ToolUsageStatus;
import java.time.LocalDateTime;
import java.util.List;
import lombok.Builder;
import lombok.Getter;

@Getter
@Builder
public class ToolUsageResponse {

	private Long id;
	private Long toolId;
	private String toolName;
	private Long usedById;
	private String usedByName;
	private String usedByEmployeeNo;
	private long successCount;
	private long failedCount;
	private String status;
	private LocalDateTime usedAt;

	public static ToolUsageResponse createFrom(ProjectMember projectMember, List<ToolUsageLog> usageLogs) {
		ToolUsageLog latestUsageLog = usageLogs.isEmpty() ? null : usageLogs.get(0);

		return ToolUsageResponse.builder()
			.id(projectMember.getId())
			.toolId(latestUsageLog == null ? null : latestUsageLog.getTool().getId())
			.toolName(latestUsageLog == null ? null : resolveToolName(latestUsageLog))
			.usedById(projectMember.getUser().getId())
			.usedByName(projectMember.getUser().getName())
			.usedByEmployeeNo(projectMember.getUser().getEmployeeNumber())
			.successCount(countStatus(usageLogs, ToolUsageStatus.SUCCESS))
			.failedCount(countStatus(usageLogs, ToolUsageStatus.FAILED))
			.status(latestUsageLog == null ? null : latestUsageLog.getStatus().name())
			.usedAt(latestUsageLog == null ? null : latestUsageLog.getUsedAt())
			.build();
	}

	private static String resolveToolName(ToolUsageLog usageLog) {
		String displayName = usageLog.getTool().getDisplayName();
		return displayName == null || displayName.isBlank() ? usageLog.getTool().getFileName() : displayName;
	}

	private static long countStatus(List<ToolUsageLog> usageLogs, ToolUsageStatus status) {
		return usageLogs.stream()
			.filter(usageLog -> status.equals(usageLog.getStatus()))
			.count();
	}
}
